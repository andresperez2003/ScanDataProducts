# Plan técnico: 001 — Cimientos y autenticación

**Spec de origen:** `specs/001-cimientos-y-auth/spec.md` (aprobada)
**Fecha:** 2026-09-18 · revisado el 2026-09-18 tras corrección de D-1 y D-3 en la spec

## 1. Enfoque en una frase

Sesiones de servidor identificadas por un token opaco en cookie firmada `HttpOnly`. El login busca al usuario **por su nombre, único en todo el sistema** y de ahí obtiene su empresa; a partir de ese momento, el `company_id` se resuelve siempre desde la sesión y se inyecta como dependencia obligatoria en cada endpoint.

## 2. Stack y decisiones

| Decisión | Elección | Motivo | Alternativa descartada |
| --- | --- | --- | --- |
| Runtime | Python 3.14.7 | Tipado moderno (`X \| None`, genéricos nativos) que `mypy --strict` aprovecha; es la versión instalada (constitución, registro del 2026-09-19) | 3.12: no instalada en la máquina de desarrollo |
| Framework | FastAPI | Validación con Pydantic y dependencias inyectables, que es el mecanismo con el que se hace obligatorio el `company_id` | Django: trae ORM, auth y admin que chocan con la arquitectura en capas de la constitución |
| ORM | SQLModel | Una sola definición para tabla y schema, sobre SQLAlchemy 2 async | SQLAlchemy puro: más verboso; Tortoise: ecosistema menor |
| BD | PostgreSQL 16 | Índices únicos sobre expresiones normalizadas y `timestamptz` real; mismo motor en dev y producción | SQLite: no reproduce los índices parciales ni el manejo de zonas horarias que este diseño usa |
| Migraciones | Alembic | Estándar con SQLAlchemy; migraciones versionadas y revisables | Migraciones a mano: sin trazabilidad |
| Hash de contraseña | `argon2-cffi` (Argon2id) | Ganador del Password Hashing Competition, resistente a GPU y a ataques de memoria; parámetros ajustables al presupuesto de 1 s de §7 | bcrypt: límite de 72 bytes rompe el caso borde de contraseña de 200 caracteres |
| Firma de cookie | `itsdangerous` | Firma HMAC de la cookie de sesión, sin almacenar el secreto en el cliente | JWT: estado en el cliente, revocación imposible sin lista negra — incompatible con CA-3.2 |
| Sesión | Tabla en BD, token opaco de 32 bytes, guardado como SHA-256 | Revocable al instante (CA-3.2, RN-7) y un volcado de BD no permite suplantar sesiones | Sesión en cookie firmada sin estado: no se puede revocar |
| CSRF | Double-submit cookie | Sin estado en servidor, encaja con SPA en otro origen | Token en sesión: obliga a una consulta extra por petición |
| Frontend | React 18 + Vite + TypeScript | Decidido por el usuario | — |
| Datos en frontend | TanStack Query | El estado de servidor se gestiona en una capa, no con `useEffect` (constitución, convenciones de frontend) | `useEffect` a mano: prohibido por la constitución |
| Tests | pytest + httpx.ASGITransport | Tests de integración contra la app real y Postgres real | TestClient síncrono: no ejercita el camino async |

**Coste de Argon2id.** Los parámetros se calibran en T004 para que la verificación tarde entre 150 ms y 300 ms en la máquina de desarrollo. Valores de partida: `time_cost=3`, `memory_cost=65536` (64 MiB), `parallelism=4`. **Calibrado en T004 (2026-09-19):** con los de partida la verificación tardaba ~38 ms (16 núcleos); se fijan `time_cost=8`, `memory_cost=131072` (128 MiB), `parallelism=4`, que dan ~183 ms de mediana y ~200 ms de máximo. Se descartó 256 MiB con `time_cost=4` (mismo tiempo, el doble de memoria por inicio de sesión). Es el único punto donde §7 ("login < 1 s en p95") puede incumplirse.

## 3. Estructura

```
backend/
├─ alembic/
│  ├─ versions/             # una migración por cambio de esquema; nunca se edita una aplicada
│  └─ env.py
├─ src/
│  ├─ main.py               # app, middlewares, routers
│  ├─ core/
│  │  ├─ config.py          # Settings (Pydantic), falla al arrancar si falta algo
│  │  ├─ db.py              # engine async, sessionmaker, dependencia get_db
│  │  ├─ errors.py          # excepciones de dominio + mapeo a HTTP
│  │  ├─ security.py        # hash de contraseñas, generación y hash de tokens, hash señuelo
│  │  ├─ csrf.py            # emisión y verificación double-submit
│  │  ├─ deps.py            # get_auth_context (único origen de company_id)
│  │  └─ logging.py         # structlog con request_id y company_id
│  ├─ models/
│  │  ├─ company.py  user.py  session.py
│  │  └─ schemas/
│  │     └─ auth.py         # request/response de §5
│  ├─ repos/
│  │  ├─ company.py
│  │  ├─ user.py            # get_by_username (global, sin company_id: ver nota más abajo)
│  │  └─ session.py
│  ├─ services/
│  │  └─ auth.py            # register, login, logout, revoke
│  └─ routers/
│     └─ auth.py            # /api/v1/auth/*
└─ tests/
   ├─ conftest.py           # fixtures: sesión con rollback, factoría de dos empresas
   ├─ unit/
   │  ├─ test_config.py  test_security.py  test_tokens.py
   │  ├─ test_csrf.py  test_errors.py  test_password_policy.py
   └─ integration/
      ├─ test_db_fixture.py  test_schema.py  test_repos.py  test_register.py
      ├─ test_login.py  test_session.py
      ├─ test_auth_api.py  test_logging.py  test_isolation.py

frontend/src/
├─ lib/api/
│  ├─ client.ts             # fetch con credentials:"include" + cabecera CSRF
│  └─ auth.ts               # register, login, logout, me
├─ features/auth/
│  ├─ LoginPage.tsx  RegisterPage.tsx
│  ├─ AuthProvider.tsx      # sesión actual, estados de carga
│  └─ ProtectedRoute.tsx
└─ App.tsx                  # rutas
```

> **Qué faltaba en la versión anterior:** la carpeta `alembic/` (las migraciones ya se mencionaban en el plan y en T003, pero no aparecían en el árbol) y `tests/`, que existe desde T002 pero no estaba dibujada. También se corrige que `repos/` tenía la rama del árbol mal cerrada.

**Excepción al principio de aislamiento, declarada aquí a propósito.** `repos/user.py` tiene un método, `get_by_username(username: str)`, que **no** recibe `company_id`: es la única consulta de todo el sistema que no lo lleva, porque el login es precisamente lo que determina a qué empresa pertenece el usuario — exigir `company_id` antes de saberlo es imposible. Todas las demás funciones de `repos/`, sin excepción, sí lo reciben como primer parámetro. Este método vive marcado con un comentario `# EXCEPCIÓN: ver plan.md §3` para que no se copie como patrón en otras features.

## 4. Modelo de datos

### `companies`

| Campo | Tipo | Nulo | Restricción |
| --- | --- | --- | --- |
| id | UUID | no | PK, `gen_random_uuid()` |
| name | text | no | tal como lo escribió el usuario |
| name_normalized | text | no | **UNIQUE**; `lower(trim(regexp_replace(name,'\s+',' ','g')))` |
| created_at | timestamptz | no | `now()` |
| disabled_at | timestamptz | sí | `null` = activa |
| disabled_by | UUID | sí | FK → `users.id`, `DEFERRABLE INITIALLY DEFERRED` |

`name_normalized` lo calcula el servicio, no la base de datos, para que la misma función se use al buscar y al insertar. Resuelve el caso borde de mayúsculas y espacios de §5 y, por ser `UNIQUE`, también el de registro simultáneo (CA-1.2 y §5, fila 3): el segundo `INSERT` falla con violación de unicidad y el servicio la traduce a `DuplicateCompanyError`, nunca a un 500.

### `users`

| Campo | Tipo | Nulo | Restricción |
| --- | --- | --- | --- |
| id | UUID | no | PK |
| company_id | UUID | no | FK → `companies.id`, índice |
| username | text | no | tal como lo escribió el usuario |
| username_normalized | text | no | **UNIQUE**; misma función que `name_normalized` (NFKC + `lower` + recorte y colapso de espacios) |
| password_hash | text | no | Argon2id codificado (incluye sal y parámetros) |
| created_at | timestamptz | no | `now()` |
| created_by | UUID | sí | `null` en el usuario que se autorregistra |
| disabled_at | timestamptz | sí | `null` = activo |
| disabled_by | UUID | sí | FK → `users.id` |

**`UNIQUE (username_normalized)`, global** — implementa D-1 y RN-3 en la base de datos. Ya no es compuesta con `company_id`: dos usuarios de empresas distintas no pueden compartir nombre. `company_id` sigue siendo `NOT NULL` con su propio índice, porque todo usuario pertenece a una empresa (RN-1); simplemente ya no forma parte de esta restricción de unicidad.

### `sessions`

| Campo | Tipo | Nulo | Restricción |
| --- | --- | --- | --- |
| id | UUID | no | PK |
| user_id | UUID | no | FK → `users.id`, índice |
| company_id | UUID | no | desnormalizado: evita un JOIN en cada petición (§7, < 50 ms) |
| token_hash | bytea | no | **UNIQUE**, SHA-256 del token de 32 bytes |
| created_at | timestamptz | no | |
| last_seen_at | timestamptz | no | se renueva en cada petición (D-3) |
| absolute_expires_at | timestamptz | no | `created_at + 15 días` (D-3, revisado) |
| revoked_at | timestamptz | sí | cierre de sesión (CA-3.2) |

Índice parcial `WHERE revoked_at IS NULL` sobre `token_hash` para la búsqueda de cada petición. El token en claro nunca se almacena: un volcado de BD no permite suplantar sesiones.

### `login_attempts` (retirada)

La migración inicial la creó para el bloqueo por intentos, que quedó fuera de alcance (spec D-4, 2026-09-19). Como una migración aplicada no se edita, **se elimina con una migración nueva** (T012b).

### `probe_items` (temporal, T016)

Tabla de prueba para verificar el aislamiento antes de que existan entidades reales. **Se elimina en la spec 002 con una migración nueva**, junto con su endpoint.

| Campo | Tipo | Nulo | Restricción |
| --- | --- | --- | --- |
| id | UUID | no | PK |
| company_id | UUID | no | FK → `companies.id`, índice |
| name | text | no | |
| created_at | timestamptz | no | `now()` |
| created_by | UUID | no | FK → `users.id` |
| disabled_at | timestamptz | sí | `null` = activo |
| disabled_by | UUID | sí | FK → `users.id` |

Endpoints (solo para tests): `GET /api/v1/_probe` (listar), `GET /api/v1/_probe/{id}` (ver uno), `PATCH /api/v1/_probe/{id}` (cambiar `name`). Su migración va aparte de la inicial, para poder revertirla sola en la 002.

### Notas de esquema

- La FK circular `companies.disabled_by` ↔ `users.company_id` se declara `DEFERRABLE INITIALLY DEFERRED` para permitir crear empresa y primer usuario en la misma transacción (CA-1.1).
- `sessions` no lleva `disabled_at`: no es entidad de negocio.

## 5. Contratos de API

Todas las rutas bajo `/api/v1`. Formato de error único:

```json
{ "error": { "code": "INVALID_CREDENTIALS", "message": "...", "fields": {} } }
```

Errores comunes a cualquier endpoint (añadidos en T008, 2026-09-19):

| Código | Cuándo | Cuerpo |
| --- | --- | --- |
| 403 | operación que modifica estado sin token CSRF válido | `code: CSRF_FAILED` |
| 404 | recurso inexistente **o de otra empresa**, indistinguibles (RN-9) | `code: NOT_FOUND`, mensaje siempre idéntico |

### `POST /api/v1/auth/register`

```json
{ "company_name": "Acme S.A.", "username": "admin", "password": "..." }
```

| Código | Cuándo | Cuerpo |
| --- | --- | --- |
| 201 | creado, sesión iniciada | `{ "user": {...}, "company": {...} }` + cookies `session` y `csrf_token` |
| 400 | campo vacío o contraseña inválida | `code: VALIDATION_ERROR`, `fields` con el detalle por campo |
| 409 | nombre de empresa ya en uso | `code: COMPANY_NAME_TAKEN` |
| 409 | nombre de usuario ya en uso en todo el sistema (RN-3; añadido en T008) | `code: USERNAME_TAKEN` |

### `POST /api/v1/auth/login`

Solo dos campos. **Sin `company_name`**: el usuario es único en todo el sistema, así que basta para encontrarlo y de él se obtiene su empresa.

```json
{ "username": "admin", "password": "..." }
```

| Código | Cuándo | Cuerpo |
| --- | --- | --- |
| 200 | credenciales correctas, usuario activo | `{ "user": {...}, "company": {...} }` + cookies |
| 401 | usuario inexistente, contraseña incorrecta o usuario deshabilitado | `code: INVALID_CREDENTIALS`, siempre el mismo mensaje (RN-6, CA-2.2/2.3/2.4) |

**Tiempo constante (CA-2.3).** Si el usuario no existe, el servicio **igualmente verifica la contraseña contra un hash señuelo** fijo, generado al arrancar. Sin esto, la diferencia de tiempo de respuesta revela qué usuarios existen y CA-2.3 falla aunque el mensaje sea idéntico.

### `POST /api/v1/auth/logout`

Requiere sesión y token CSRF. `204` siempre que la sesión sea válida; marca `revoked_at`.

### `GET /api/v1/auth/me`

| Código | Cuándo | Cuerpo |
| --- | --- | --- |
| 200 | sesión válida | `{ "user": { "id", "username" }, "company": { "id", "name" } }` |
| 401 | sin sesión, caducada, revocada o usuario deshabilitado | `code: NOT_AUTHENTICATED` |

### Cookies

| Cookie | Flags | Contenido |
| --- | --- | --- |
| `session` | `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/` | token de 32 bytes firmado con `itsdangerous` |
| `csrf_token` | `Secure`, `SameSite=Lax`, **sin** `HttpOnly` | valor aleatorio que el frontend copia a la cabecera `X-CSRF-Token` |

`Secure` se desactiva solo cuando `ENVIRONMENT=development`, para poder trabajar en `http://localhost`.

### Dependencia de aislamiento

```python
async def get_auth_context(...) -> AuthContext: ...   # -> user_id, company_id
```

Es la única forma de obtener el `company_id`. Ningún schema de entrada de ninguna feature lo acepta (CA-4.3, RN-8). Toda función de repositorio lo recibe como primer parámetro.

## 6. Trazabilidad

| Criterio | Dónde se cumple |
| --- | --- |
| CA-1.1 | `auth.register` en una transacción, FK diferida |
| CA-1.2 | `UNIQUE(name_normalized)` + traducción de `IntegrityError` |
| CA-1.3, CA-1.4 | schema `RegisterRequest` + validador de contraseña |
| CA-1.5 | columna `password_hash`; test que verifica que no existe columna de texto plano |
| CA-1.6 | filtro de structlog que redacta claves `password` |
| CA-2.1 | `auth.login` → creación de sesión |
| CA-2.2, CA-2.3, CA-2.4 | rama única de fallo + hash señuelo, búsqueda de usuario global |
| CA-3.1 | cookie persistente + `GET /auth/me` |
| CA-3.2 | `revoked_at` + índice parcial |
| CA-3.3 | `last_seen_at` (inactividad de 8h) |
| CA-3.5 | `absolute_expires_at` = `created_at + 15 días` |
| CA-3.4 | `ProtectedRoute` en frontend + 401 del backend |
| CA-4.1 a CA-4.4 | `get_auth_context` + `company_id` obligatorio en repos; endpoint sonda de test |
| RN-1 a RN-9 | ver §4 y §5 |

## 7. Riesgos

| Riesgo | Impacto | Mitigación |
| --- | --- | --- |
| Argon2id mal calibrado supera el presupuesto de 1 s | Login lento, §7 incumplido | T004 mide y ajusta; test que falla si la verificación supera 400 ms |
| Se olvida el hash señuelo | CA-2.3 pasa por mensaje pero falla por tiempo | Test explícito que compara tiempos de usuario existente e inexistente |
| `--autogenerate` no detecta índices parciales ni la FK diferida | Migración incompleta | Revisión manual obligatoria del archivo generado (T003) |
| Normalización Unicode inconsistente | Dos empresas "iguales" coexisten | Normalizar con NFKC antes de `lower()`, en una única función compartida |
| CSRF mal implementado con SPA en otro origen | Peticiones rechazadas o protección inútil | Test de integración que envía sin cabecera y espera 403 |

## 8. Checklist de salida

- [x] Toda decisión trae motivo y alternativa descartada
- [x] El modelo de datos cubre todos los casos borde de §5 de la spec
- [x] Cada criterio de aceptación aparece en la tabla de trazabilidad
- [x] Los códigos de error están decididos, no implícitos
- [x] Nada contradice la spec
- [x] Sin bloqueo por intentos fallidos: fuera de alcance (spec D-4, retirada el 2026-09-19)
