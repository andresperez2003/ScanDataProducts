# Tareas: 002 — Catálogo: productos y proveedores

**Spec:** `spec.md` (aprobada) · **Plan:** `plan.md`
**Rama:** `feature/002-catalogo-productos-proveedores`

## Cómo leer esto

- `[P]` = puede ejecutarse en paralelo con las otras `[P]` de su bloque (no tocan los
  mismos archivos).
- Toda tarea trae su línea de **Verificación**. Si no se puede verificar, está mal escrita.
- Los tests se escriben **antes** que el código de cada tarea y deben verse fallar primero.
- Sin límite de tareas (eliminado de la constitución el 2026-09-19).
- **Solo backend.** La Fase B (frontend) se retiró el 2026-09-20 al aplazarse el
  frontend hasta cerrar el backend. Sus tareas T012–T015 llegaron a implementarse,
  pero nunca se commitearon: no quedan en el historial de git.

---

## Backend

### Bloque 0 — Base compartida

- [x] **T001** Modelos `Supplier` y `Product` (SQLModel) según plan §4, y migración de
      Alembic. Incluye la columna generada `supplier_key` y los dos índices únicos
      parciales de `products`, y el de `suppliers`. Revisar a mano el archivo generado:
      `--autogenerate` no maneja bien columnas generadas ni índices parciales sobre ellas.
      · Verificación: `alembic upgrade head` y `alembic downgrade base` corren sin error.
      `tests/integration/test_catalog_schema.py` consulta `pg_indexes` y comprueba que
      existen los tres índices únicos parciales descritos en plan §4, con su condición
      `WHERE` exacta.

- [x] **T002** Mover `normalize_name` de `core/security.py` a `core/normalize.py`
      (plan §2) y actualizar todos sus usos en `services/auth.py` y donde corresponda.
      · Verificación: `pytest backend/tests/` completo sigue en verde (no solo los tests
      nuevos: este movimiento no debe romper 001). `tests/unit/test_normalize.py` cubre
      los mismos casos que antes probaba `test_security.py` para esta función.

- [x] **T003** `[P]` Errores de dominio nuevos en `core/errors.py`: `DuplicateSupplierNameError`
      (`SUPPLIER_NAME_TAKEN`), `DuplicateProductNameError` (`PRODUCT_NAME_TAKEN`),
      `DuplicateProductSkuError` (`PRODUCT_SKU_TAKEN`), y su entrada en `HTTP_STATUS`.
      · Verificación: `pytest tests/unit/test_errors.py` — las tres heredan de
      `DomainError`, todas mapean a 409, y el test que recorre las subclases (ya existente)
      sigue pasando sin tener que tocarlo a mano.

### Bloque 1 — Acceso a datos

- [x] **T004** `repos/supplier.py`: `create`, `get`, `list` (paginado + búsqueda + filtro
      activos/histórico), `update`, `disable`, `enable`. `company_id` como primer
      parámetro en cada método (constitución, principio 1).
      · Verificación: `pytest tests/integration/test_suppliers_api.py` en su parte de
      repositorio — `test_ca_2_1_pagina_con_total`, `test_ca_2_2_busqueda_parcial`,
      `test_ca_2_4_solo_activos_por_defecto`. Un test busca con el `company_id` de otra
      empresa y obtiene una lista vacía, nunca los de la empresa correcta.

- [x] **T005** `repos/product.py`: mismos métodos que T004, más filtro por `supplier_id`
      (CA-4.5) y el `JOIN` a `suppliers` para embeber su nombre en el listado sin copiarlo
      (plan §7, "consistencia").
      · Verificación: `pytest tests/integration/test_products_api.py` en su parte de
      repositorio — `test_ca_4_1_pagina_con_proveedor_embebido`,
      `test_ca_4_2_busqueda_por_nombre_o_sku`, `test_ca_4_5_filtro_por_proveedor`.

### Bloque 2 — Reglas de negocio

- [x] **T006** `services/suppliers.py`: alta y edición normalizan el nombre y traducen
      `IntegrityError` a `DuplicateSupplierNameError` (nunca un 500); `disable` y `enable`,
      con `enable` verificando el mismo conflicto que un alta (D-4).
      · Verificación: `pytest tests/integration/test_suppliers_api.py` — `test_ca_1_1` a
      `test_ca_1_8` de la tabla de trazabilidad. Un test da de alta dos proveedores con el
      mismo nombre en paralelo y comprueba que uno recibe `SUPPLIER_NAME_TAKEN` y el otro
      éxito, igual que `test_register.py` en 001.

- [x] **T007** `services/products.py`: alta y edición normalizan nombre y SKU, comprueban
      que `supplier_id` (si viene) exista, sea de mi empresa y esté activo — si no, error
      de validación con `fields: {"supplier_id": …}` (RN-4, CA-3.6), nunca un 500 ni un
      404 que revele si el proveedor es de otra empresa cuando en realidad está
      deshabilitado. `disable` y `enable` con la misma lógica de conflicto que T006.
      · Verificación: `pytest tests/integration/test_products_api.py` — `test_ca_3_1` a
      `test_ca_3_12`. Un test edita solo el nombre de un producto cuyo proveedor fue
      deshabilitado después de creado, y comprueba que **no** falla (D-3, plan §7 riesgos).

### Bloque 3 — API

- [x] **T008** `schemas/catalog.py`: `SupplierIn/Out`, `ProductIn/Out`, y el envoltorio
      genérico de paginación (`Page`) usado por ambos listados.
      · Verificación: `mypy --strict` pasa; un test de esquema comprueba que un `ProductOut`
      serializa `supplier: SupplierOut | None`, nunca un `supplier_id` suelto.

- [x] **T009** `[P]` `routers/suppliers.py`: los cinco endpoints de plan §5, con
      `get_auth_context` como único origen del `company_id`.
      · Verificación: `pytest tests/integration/test_suppliers_api.py` completo — cada
      código de éxito y **cada** código de error del contrato de plan §5.

- [x] **T010** `[P]` `routers/products.py`: los seis endpoints de plan §5.
      · Verificación: `pytest tests/integration/test_products_api.py` completo, mismo
      criterio que T009.

- [x] **T011** Tests de aislamiento entre empresas para ambos recursos, siguiendo el
      patrón de `test_isolation.py` de 001 (tests.md: "no es opcional en ningún endpoint").
      · Verificación: `tests/integration/test_catalog_isolation.py` —
      `test_ca_5_1_no_encontrado_de_otra_empresa`, `test_ca_5_2_listado_solo_propio`,
      `test_ca_5_3_company_id_del_cuerpo_se_ignora`, `test_ca_5_4_modificar_ajeno_falla`,
      para `suppliers` y para `products`.

---

## Cierre

- [x] **T016** Verificación de trazabilidad y de constitución.
      · Verificación: todo criterio de aceptación de la spec tiene al menos un test que lo
      nombra; `pytest --cov=src --cov-fail-under=80` pasa; la revisión de constitución no
      reporta consultas sin `company_id` en ninguno de los archivos nuevos.

- [x] **T017** Retirar la sonda temporal de 001: migración que hace `DROP` de
      `probe_items`, y eliminación de `models/probe_item.py`, `repos/probe_item.py`,
      `services/probe.py`, `routers/probe.py`, `models/schemas/probe.py`, `ProbeItemData`
      de `models/domain.py`, su registro en `models/__init__.py` y `main.py`, y
      `tests/integration/test_isolation.py`. Va **después** de T011, que es quien pasa a
      cubrir el aislamiento con recursos de negocio reales.
      · Verificación: `pytest backend/tests/` completo en verde sin `test_isolation.py`;
      `grep -ri probe backend/src` no devuelve nada; `alembic upgrade head` y
      `alembic downgrade base` corren sin error.

      > Tarea añadida el 2026-09-19, fuera del `tasks.md` original y con autorización
      > explícita. Motivo: 001 dejó `probe_items` y `/api/v1/_probe` declarados como
      > temporales "hasta cerrar la spec 002" en seis archivos
      > (`models/probe_item.py:13`, `repos/probe_item.py:1`, `services/probe.py:3`,
      > `routers/probe.py:3`, `main.py:42`, `models/domain.py:52`), pero ninguna tarea
      > de 002 lo retiraba.

---

## Tabla de trazabilidad

| Criterio | Tarea | Test |
| --- | --- | --- |
| CA-1.1 – CA-1.5 | T006 | `test_suppliers_api.py` |
| CA-1.6 | T007 | `test_products_api.py::test_ca_1_6_proveedor_deshabilitado_se_conserva_en_producto` |
| CA-1.7, CA-1.8 | T006 | `test_suppliers_api.py` |
| CA-2.1 – CA-2.4 | T004, T009 | `test_suppliers_api.py` |
| CA-3.1 – CA-3.12 | T001, T007 | `test_products_api.py` |
| CA-4.1 – CA-4.5 | T005, T010 | `test_products_api.py` |
| CA-5.1 – CA-5.4 | T004, T005, T011 | `test_catalog_isolation.py` |
| RN-1 | T001, T006 | `test_catalog_schema.py`, `test_suppliers_api.py` |
| RN-2, RN-3 | T001, T007 | `test_catalog_schema.py`, `test_products_api.py` |
| RN-4 | T007 | `test_products_api.py::test_rn_4_proveedor_debe_estar_activo` |
| RN-5 | T007 | `test_products_api.py::test_rn_5_deshabilitar_proveedor_no_afecta_productos` |
| RN-6 | T006, T007 | ambos: nada usa `DELETE` |
| RN-7, RN-8 | T004, T005, T011 | `test_catalog_isolation.py` |

---

## Checklist de salida

- [x] Toda tarea tiene criterio de verificación ejecutable
- [x] Ningún criterio de aceptación queda sin tarea
- [x] Las tareas `[P]` de un mismo bloque no tocan los mismos archivos
- [x] `spec.md` pasó de "borrador" a "aprobada" antes de empezar T001
