# Plan técnico: 002 — Catálogo: productos y proveedores

**Spec de origen:** `specs/002-catalogo-productos-proveedores/spec.md` (borrador)
**Fecha:** 2026-09-19
**Depende de:** `001-cimientos-y-auth` (ya implementada) — reutiliza su autenticación,
`get_auth_context`, patrón de errores de dominio y convenciones de esquema.
**Alcance:** solo backend. Las decisiones y la estructura de frontend se retiraron el
2026-09-20 al aplazarse el frontend hasta cerrar el backend.

## 1. Enfoque en una frase

Dos tablas nuevas (`suppliers`, `products`), en capas idénticas a las de 001
(`routers/` → `services/` → `repos/`), con paginación y búsqueda por `ILIKE` sobre un
nombre normalizado, y la unicidad de nombre/SKU de producto resuelta con una columna
computada que agrupa "sin proveedor" como si fuera un proveedor más.

## 2. Stack y decisiones

| Decisión | Elección | Motivo | Alternativa descartada |
| --- | --- | --- | --- |
| Runtime, framework, ORM, BD, migraciones | Los mismos de 001 (Python 3.14, FastAPI, SQLModel, Alembic, PostgreSQL) | Ya elegidos y en uso; esta spec no introduce necesidades nuevas de stack | — |
| Normalización de nombre | Reutilizar `normalize_name` (NFKC + lower + colapso de espacios), **movida** de `core/security.py` a `core/normalize.py` | Ya no es exclusiva de auth: la usan proveedores y productos. Dejarla en `security.py` sería un import cruzado sin sentido de capas | Duplicar la función en `services/catalog`: viola "antes de crear un helper, se busca uno equivalente" (constitución §7) |
| Unicidad de producto sin proveedor | Columna generada `supplier_key` = `COALESCE(supplier_id, '00000000-0000-0000-0000-000000000000'::uuid)`, e índice único parcial sobre `(company_id, supplier_key, name_normalized) WHERE disabled_at IS NULL` | Un índice único normal sobre `(company_id, supplier_id, name_normalized)` no funciona: en SQL, dos `NULL` nunca son iguales, así que dos productos sin proveedor con el mismo nombre no violarían la restricción (D-1, D-2, CA-3.3) | Forzar `supplier_id` a un valor no nulo con un proveedor "ninguno" fijo por empresa: ensucia el modelo con una fila que no es un proveedor real |
| Búsqueda | `ILIKE '%término_normalizado%'` sobre `name_normalized` (y `sku_normalized` en productos), sin índice de texto completo | Con el límite de §7 de la spec (10 000 registros activos por empresa) un `ILIKE` sin índice cumple el `< 1 s p95` sin infraestructura extra | `pg_trgm` + índice GIN: mejor a mayor escala, pero es una extensión de Postgres que no hace falta todavía — se revisita si el volumen crece |
| Paginación | `page` (base 1) y `page_size` (por defecto y máximo 20, spec §7 D-6) como query params; respuesta `{ items, total, page, page_size }` | Envoltorio simple y consistente entre `suppliers` y `products`, con un solo tipo genérico | Cursor-based: resuelve mejor listas que cambian mientras se pagina, mejora que no hace falta a este volumen |
| Deshabilitar / rehabilitar | Un endpoint dedicado por acción (`POST .../disable`, `POST .../enable`), no un `PATCH` de estado | `capas.md`: "deshabilitar es una operación explícita del dominio, con su propio método"; un endpoint propio hace explícita la operación también en la API, igual que su propio método de servicio | `PATCH` genérico con `{ disabled: true }`: mezclaría la edición de datos con un cambio de estado que tiene sus propias reglas de conflicto (D-3, D-4) |

## 3. Estructura

```
backend/src/
├─ core/
│  └─ normalize.py          # normalize_name, movida desde security.py (T002)
├─ models/
│  ├─ supplier.py           # tabla suppliers
│  ├─ product.py            # tabla products, incluida la columna generada supplier_key
│  ├─ domain.py             # + SupplierData, ProductData
│  └─ schemas/
│     └─ catalog.py         # request/response de §5, y el envoltorio Page[T]
├─ repos/
│  ├─ supplier.py
│  └─ product.py
├─ services/
│  ├─ suppliers.py          # alta, edición, disable, enable
│  └─ products.py           # alta, edición (valida proveedor activo), disable, enable
└─ routers/
   ├─ suppliers.py          # /api/v1/suppliers
   └─ products.py           # /api/v1/products

backend/tests/
├─ unit/
│  └─ test_normalize.py     # movido junto con la función (antes cubierto en test_security.py)
└─ integration/
   ├─ test_suppliers_api.py
   ├─ test_products_api.py
   └─ test_catalog_isolation.py   # CA-5.1 a CA-5.4 para ambos recursos

```

## 4. Modelo de datos

### `suppliers`

| Campo | Tipo | Nulo | Restricción |
| --- | --- | --- | --- |
| id | UUID | no | PK, `gen_random_uuid()` |
| company_id | UUID | no | FK → `companies.id`, índice |
| name | text | no | tal como lo escribió el usuario |
| name_normalized | text | no | `normalize_name(name)` |
| created_at | timestamptz | no | `now()` |
| created_by | UUID | no | FK → `users.id` |
| disabled_at | timestamptz | sí | `null` = activo |
| disabled_by | UUID | sí | FK → `users.id` |

Índice único parcial: `(company_id, name_normalized) WHERE disabled_at IS NULL` — implementa
RN-1 y CA-1.2/CA-1.5/CA-1.7 en la base de datos, igual que `companies.name_normalized` en 001.

### `products`

| Campo | Tipo | Nulo | Restricción |
| --- | --- | --- | --- |
| id | UUID | no | PK |
| company_id | UUID | no | FK → `companies.id`, índice |
| supplier_id | UUID | sí | FK → `suppliers.id`, índice; `null` = sin proveedor (D-1) |
| supplier_key | UUID | no | **generada**: `COALESCE(supplier_id, '00000000-0000-0000-0000-000000000000')`. Solo existe para poder indexar; nunca se lee ni se escribe desde el código |
| name | text | no | tal como lo escribió el usuario |
| name_normalized | text | no | `normalize_name(name)` |
| sku | text | sí | tal como lo escribió el usuario; vacío = sin SKU |
| sku_normalized | text | sí | `normalize_name(sku)`; `null` cuando `sku` es `null` |
| created_at | timestamptz | no | `now()` |
| created_by | UUID | no | FK → `users.id` |
| disabled_at | timestamptz | sí | `null` = activo |
| disabled_by | UUID | sí | FK → `users.id` |

Dos índices únicos parciales:
- `(company_id, supplier_key, name_normalized) WHERE disabled_at IS NULL` — RN-2, D-1, D-2, CA-3.1 a CA-3.3.
- `(company_id, supplier_key, sku_normalized) WHERE disabled_at IS NULL AND sku_normalized IS NOT NULL` — RN-3, CA-3.8, CA-3.9, y el caso borde de dos SKU vacíos.

**Por qué una columna generada y no una expresión directa en el índice.** Postgres permite
índices sobre expresiones sin declarar una columna, pero `supplier_key` se usa también para
filtrar y para el `ORDER BY` estable del listado; declararla como columna generada
almacenada evita repetir el `COALESCE` en cada consulta y en el índice a la vez.

**Validación de proveedor activo (RN-4, CA-3.6).** No vive en una `CHECK` de base de datos
—un `CHECK` no puede consultar otra tabla—: el servicio (`services/products.py`) comprueba
que el proveedor exista, sea de la misma empresa y tenga `disabled_at IS NULL` antes de
asignarlo, en el alta y en cada edición que cambie `supplier_id`.

## 5. Contratos de API

Mismo formato de error que 001. Todas las rutas bajo `/api/v1`.

### `GET /api/v1/suppliers`

Query: `search` (opcional), `page` (por defecto 1), `page_size` (por defecto 20, máximo 20).
Solo activos salvo `include_disabled=true`.

| Código | Cuándo | Cuerpo |
| --- | --- | --- |
| 200 | siempre que la empresa tenga sesión válida | `{ "items": [SupplierOut], "total": n, "page": n, "page_size": n }` |

### `POST /api/v1/suppliers`

```json
{ "name": "Acme S.A." }
```

| Código | Cuándo | Cuerpo |
| --- | --- | --- |
| 201 | creado | `SupplierOut` |
| 400 | nombre vacío | `code: VALIDATION_ERROR`, `fields` |
| 409 | nombre ya usado por un proveedor activo | `code: SUPPLIER_NAME_TAKEN` |

### `GET /api/v1/suppliers/{id}`

| Código | Cuándo | Cuerpo |
| --- | --- | --- |
| 200 | el proveedor es de mi empresa | `SupplierOut` |
| 404 | no existe o es de otra empresa | `code: NOT_FOUND`, idéntico en ambos casos (RN-8) |

> Añadido el 2026-09-19, fuera del plan original y con autorización explícita.
> Motivo: CA-5.1 exige solicitar un proveedor o producto "por su identificador" y
> recibir "no encontrado" — un criterio distinto de CA-5.4, que cubre editar,
> deshabilitar y rehabilitar. Sin este endpoint, CA-5.1 no era comprobable tal
> como está escrito. Es además el sexto endpoint que `tasks.md` T010 ya contaba
> para productos, donde el plan solo definía cinco.

### `PATCH /api/v1/suppliers/{id}`

Mismo cuerpo y códigos que el alta, más `404` (`NOT_FOUND`) si el proveedor no es de mi
empresa o no existe.

### `POST /api/v1/suppliers/{id}/disable` · `POST /api/v1/suppliers/{id}/enable`

| Código | Cuándo | Cuerpo |
| --- | --- | --- |
| 204 | operación aplicada | — |
| 404 | no es mío o no existe | `code: NOT_FOUND` |
| 409 | rehabilitar choca con un nombre activo (D-4) | `code: SUPPLIER_NAME_TAKEN` — solo en `enable` |

### `GET /api/v1/products`

Query: `search`, `supplier_id` (opcional, CA-4.5), `page`, `page_size`, `include_disabled`.
`SupplierOut` embebido o `null` (§7, "consistencia": siempre el nombre actual, nunca copiado).

### `GET /api/v1/products/{id}`

Mismos códigos que `GET /api/v1/suppliers/{id}`, con `ProductOut`. Añadido por el
mismo motivo y con la misma autorización.

### `POST /api/v1/products` · `PATCH /api/v1/products/{id}`

```json
{ "name": "Tornillo 5mm", "supplier_id": "…-o-null", "sku": "…-o-null" }
```

| Código | Cuándo | Cuerpo |
| --- | --- | --- |
| 201 / 200 | creado / editado | `ProductOut` |
| 400 | nombre vacío, o `supplier_id` de un proveedor deshabilitado | `code: VALIDATION_ERROR`, `fields: {"supplier_id": "…"}` en el segundo caso |
| 404 | `supplier_id` no existe o no es de mi empresa (RN-8: indistinguible de deshabilitado ajeno) | `code: NOT_FOUND` |
| 409 | nombre o SKU ya usado en ese proveedor | `code: PRODUCT_NAME_TAKEN` / `PRODUCT_SKU_TAKEN` |

### `POST /api/v1/products/{id}/disable` · `POST /api/v1/products/{id}/enable`

Igual forma que el de proveedores; `enable` puede responder `409` con
`PRODUCT_NAME_TAKEN` o `PRODUCT_SKU_TAKEN`.

## 6. Trazabilidad

| Criterio | Dónde se cumple |
| --- | --- |
| CA-1.1 a CA-1.5 | `services/suppliers.py` + índice único parcial de `suppliers` |
| CA-1.6 | `services/products.py` no valida contra proveedores deshabilitados en alta, solo en asignación; el proveedor deshabilitado sigue en la fila de `products` |
| CA-1.7, CA-1.8 | `services/suppliers.py.enable`, mismo índice que el alta |
| CA-2.1 a CA-2.4 | `GET /suppliers`, repo con `ILIKE` + `LIMIT/OFFSET` + filtro `disabled_at IS NULL` |
| CA-3.1 a CA-3.5 | índice único parcial de `products` sobre `supplier_key` |
| CA-3.6 | `services/products.py`, comprobación explícita de proveedor activo |
| CA-3.7 | `services/products.py.update`, misma validación que el alta |
| CA-3.8, CA-3.9 | segundo índice único parcial de `products` |
| CA-3.10 a CA-3.12 | `services/products.py.disable/enable` |
| CA-4.1 a CA-4.5 | `GET /products`, incluye `supplier_id` en el filtro y el nombre del proveedor embebido |
| CA-5.1 a CA-5.4 | `company_id` de `get_auth_context` como primer parámetro de cada repo; `test_catalog_isolation.py` |
| RN-1 a RN-8 | ver §4 y §5 |

## 7. Riesgos

| Riesgo | Impacto | Mitigación |
| --- | --- | --- |
| Alta simultánea del mismo nombre (mismo proveedor o ambos sin proveedor) | Error interno en vez de conflicto claro | Igual que `DuplicateCompanyError` en 001: el `INSERT` falla por el índice único, el servicio traduce `IntegrityError` a `DuplicateSupplierNameError`/`DuplicateProductNameError`/`DuplicateProductSkuError`, nunca un 500 |
| `ILIKE '%…%'` no usa el índice de unicidad (que es por igualdad, no por substring) | Con mucho volumen, la búsqueda se vuelve lenta | Aceptado al volumen de §7 (10 000 filas); si crece, se añade `pg_trgm` en una spec de mantenimiento |
| Mover `normalize_name` a `core/normalize.py` rompe imports existentes de `security.py` en 001 | Tests de 001 fallan tras el cambio | T002 corre la suite completa de `backend/tests/` antes de dar la tarea por cerrada, no solo los tests nuevos |
| `--autogenerate` no detecta bien la columna generada `supplier_key` ni los índices parciales que la usan | Migración incompleta | Revisión manual obligatoria del archivo generado (T001), igual que con `sessions` en 001 |
| Un producto con proveedor deshabilitado después de creado sigue editable en campos que no son `supplier_id` | Ninguno: es el comportamiento decidido (D-3) | Test explícito que confirma que editar solo el nombre de un producto así no falla |

## 8. Checklist de salida

- [x] Toda decisión trae motivo y alternativa descartada
- [x] El modelo de datos cubre todos los casos borde de §5 de la spec
- [x] Cada criterio de aceptación aparece en la tabla de trazabilidad
- [x] Los códigos de error están decididos, no implícitos
- [x] Nada contradice la spec
- [x] La reutilización de `normalize_name` está declarada, no repetida
