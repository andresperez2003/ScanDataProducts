# Tareas: 001 — Cimientos y autenticación

**Spec:** `spec.md` (aprobada) · **Plan:** `plan.md`
**Rama:** `feature/001-cimientos-y-auth`

## Cómo leer esto

- `[P]` = puede ejecutarse en paralelo con las otras `[P]` de su bloque (no tocan los mismos archivos).
- Toda tarea trae su línea de **Verificación**. Si no se puede verificar, está mal escrita.
- Los tests se escriben **antes** que el código de cada tarea y deben verse fallar primero.
- 20 tareas. La constitución ya no limita el número de tareas por feature (registro del 2026-09-19).

---

## Fase A — Backend

### Bloque 0 — Andamiaje

- [x] **T001** `core/config.py`: `Settings` de Pydantic con todas las variables de `.env.example`. La app no arranca si falta una.
      · Verificación: `pytest tests/unit/test_config.py` — un test comprueba que falta `SESSION_SECRET` lanza error al instanciar, y otro que un `.env` completo carga los valores correctos.

### Bloque 1 — Datos

- [x] **T002** Modelos `Company`, `User`, `Session` según §4 del plan, y migración inicial de Alembic. Revisar a mano el archivo generado: `--autogenerate` no detecta el índice parcial de `sessions` ni la FK diferida de `companies.disabled_by`.
      · Verificación: `alembic upgrade head`, `alembic downgrade base` y de nuevo `alembic upgrade head` corren sin error. Las comprobaciones de esquema con `pytest` quedan en T003, que es donde nacen las fixtures de base de datos.

- [x] **T003** `core/db.py`: engine async, `sessionmaker`, dependencia `get_db`. Fixtures de pytest: sesión por test en transacción con rollback, y factoría que crea **dos empresas** con un usuario cada una.
      · Verificación: `pytest tests/integration/test_db_fixture.py tests/integration/test_schema.py` — un test inserta una empresa y otro comprueba que la tabla está vacía, demostrando que el rollback funciona. La factoría devuelve dos `company_id` distintos. `test_schema.py` consulta `pg_indexes` e `information_schema.table_constraints` y comprueba que existen: `UNIQUE(companies.name_normalized)`, `UNIQUE(users.username_normalized)` (global, D-1), el índice parcial de `sessions` y la FK diferida; y `test_ca_1_5_sin_columna_de_texto_plano` comprueba que `users` no tiene ninguna columna de contraseña salvo `password_hash`.

### Bloque 2 — Seguridad

- [x] **T004** `[P]` `core/security.py`: hash y verificación Argon2id, y la función de normalización NFKC + `lower` + colapso de espacios, compartida por búsqueda e inserción, y usada tanto para nombres de empresa como de usuario.
      · Verificación: `pytest tests/unit/test_security.py` — una contraseña de 200 caracteres hashea y verifica; `"  Acme   S.A. "` y `"acme s.a."` normalizan igual; un test mide que la verificación tarda menos de 400 ms.

- [x] **T005** `[P]` `core/security.py`: generación de token de sesión de 32 bytes, su SHA-256, y firma y verificación con `itsdangerous`.
      · Verificación: `pytest tests/unit/test_tokens.py` — una firma manipulada se rechaza; dos tokens generados nunca coinciden; el hash es determinista.

- [x] **T006** `[P]` `core/csrf.py`: emisión de la cookie `csrf_token` y verificación double-submit.
      · Verificación: `pytest tests/unit/test_csrf.py` — coincidencia de cookie y cabecera pasa; ausencia de cabecera, ausencia de cookie y valores distintos fallan.

### Bloque 3 — Acceso a datos

- [x] **T007** Repositorios `company`, `user`, `session`. Toda función de negocio recibe `company_id` como **primer parámetro**.
      · Verificación: `pytest tests/integration/test_repos.py` — cada método devuelve objetos de dominio, no filas de SQLModel; un test busca un usuario de la empresa A pasando el `company_id` de B y obtiene `None`. Además, un test lee el código fuente de `repos/` y falla si alguna función pública que consulta una tabla de negocio no tiene `company_id` como primer parámetro.

### Bloque 4 — Reglas de negocio

- [x] **T008** Errores de dominio en `core/errors.py` y su mapeo único a códigos HTTP.
      · Verificación: `pytest tests/unit/test_errors.py` — toda excepción de dominio tiene mapeo; un test recorre las subclases y falla si alguna no está en la tabla. Ningún módulo de `services/` importa `fastapi`: test que inspecciona los imports.

- [x] **T009** `services/auth.register`: normaliza, crea empresa y usuario en una transacción, traduce `IntegrityError` a `DuplicateCompanyError`.
      · Verificación: `pytest tests/integration/test_register.py` — cubre CA-1.1 a CA-1.4 y los casos borde de mayúsculas y espacios. Un test lanza dos registros concurrentes con el mismo nombre y comprueba que uno recibe `DuplicateCompanyError` y el otro éxito, nunca un error interno.

- [x] **T010** Validador de contraseña de RN-4 (D-5): mínimo 12 caracteres; al menos una mayúscula, una minúscula, un número y un especial de `#$%&*_@`; ningún otro carácter.
      · Verificación: `pytest tests/unit/test_password_policy.py` — 11 caracteres válidos falla y 12 pasa; falla si falta mayúscula, minúscula, número o especial, indicando qué requisito incumple; falla con un espacio (también al inicio o al final), con `ñ` o letra acentuada, y con un símbolo fuera de la lista; una de 200 caracteres válidos pasa.

- [x] **T011** `services/auth.login`: busca al usuario **solo por `username`, sin `company_id`** (única excepción del proyecto, ver plan.md §3), y verifica en tiempo constante con **hash señuelo** cuando no existe.
      · Verificación: `pytest tests/integration/test_login.py` — cubre CA-2.1 a CA-2.4. Un test mide 20 intentos con usuario existente y 20 con inexistente y falla si las medianas difieren en más de 50 ms. Un test de dos empresas confirma que el usuario de la empresa A puede entrar sin mencionar ninguna empresa, y que el `company_id` de la sesión resultante es el correcto.

- ~~**T012** Rate limiting~~ **Retirada (2026-09-19): el bloqueo por intentos fallidos queda fuera de alcance (spec D-4).** El número no se reutiliza, para no renumerar las demás tareas.

- [x] **T012b** Retirar el bloqueo por intentos ya implementado (spec D-4, retirada el 2026-09-19): eliminar `services/rate_limit.py`, `repos/login_attempt.py`, `models/login_attempt.py`, `LoginAttemptData`, `TooManyAttemptsError` y la cabecera `Retry-After`; `login` deja de recibir `client_ip`. La tabla `login_attempts` se elimina con una **migración nueva** (la inicial no se edita).
      · Verificación: `pytest` — un test de `test_schema.py` comprueba que `login_attempts` no existe; un test de `test_login.py` comprueba que tras 6 contraseñas incorrectas seguidas el acceso correcto funciona (D-4). `alembic upgrade head`, `alembic downgrade -1` y `alembic upgrade head` corren sin error.

- [x] **T013** Ciclo de vida de la sesión: creación, renovación de `last_seen_at`, caducidad por inactividad (8h) y absoluta (**15 días**, D-3 revisada), revocación.
      · Verificación: `pytest tests/integration/test_session.py` — CA-3.1 a CA-3.3 y CA-3.5 (sesión de 15 días exactos con actividad constante igual se cierra), el caso borde de dos sesiones simultáneas en dispositivos distintos, la reutilización tras cierre de sesión, y un usuario deshabilitado cuya sesión deja de funcionar en la siguiente petición.

### Bloque 5 — API

- [x] **T014** `core/deps.py`: `get_auth_context` como único origen del `company_id`. Routers `/api/v1/auth/*` con los cuatro endpoints de §5, cookies con sus flags, y verificación CSRF en las operaciones que modifican estado.
      · Verificación: `pytest tests/integration/test_auth_api.py` — cada endpoint con su código de éxito y **cada** código de error del contrato. Un test comprueba que `POST /auth/login` acepta solo `username` y `password`, y que enviar `company_name` en ese cuerpo no tiene efecto. Un test comprueba los flags de las cookies (`HttpOnly`, `SameSite`, y `Secure` según entorno). Un test envía un `company_id` en el cuerpo del registro y comprueba que se ignora (CA-4.3). Un test envía una petición de cierre de sesión sin cabecera CSRF y espera 403.

- [x] **T015** Logging estructurado con `request_id` y `company_id`, y filtro que redacta cualquier clave `password`.
      · Verificación: `pytest tests/integration/test_logging.py` — captura la salida de un registro exitoso y falla si la contraseña aparece en cualquier forma (CA-1.6). Un test comprueba que un error manejado se registra exactamente una vez.

- [x] **T016** Endpoint sonda temporal `/api/v1/_probe` sobre la tabla `probe_items` (plan §4: listar, ver uno, cambiar nombre; migración propia), para verificar el aislamiento antes de que existan features reales. Se elimina al cerrar la spec 002.
      · Verificación: `pytest tests/integration/test_isolation.py` — CA-4.1, CA-4.2 y CA-4.4: el usuario de B pide el recurso de A y recibe **404**, lista y recibe solo lo suyo, e intenta modificarlo y falla sin que el recurso de A cambie.

---

## Fase B — Frontend

- [x] **T017** `lib/api/client.ts` y `lib/api/auth.ts`: `credentials: "include"`, lectura de la cookie `csrf_token` y envío en `X-CSRF-Token`, tipos derivados de los contratos de §5 del plan, traducción del formato de error a errores por campo.
      · Verificación: `npm test` — con servidor simulado, una respuesta 400 con `fields` produce errores por campo; una 401 produce el estado "no autenticado"; toda petición que modifica estado lleva la cabecera CSRF.

- [x] **T018** `[P]` `AuthProvider` y `ProtectedRoute` con TanStack Query sobre `GET /auth/me`.
      · Verificación: `npm test` — sin sesión se redirige a `/login` (CA-3.4); con sesión se renderiza el contenido; el estado de carga no parpadea mostrando la pantalla de login antes de resolver.

- [x] **T019** `[P]` Pantallas de inicio de sesión (**dos** campos: usuario y contraseña, sin empresa) y de registro (tres: empresa, usuario, contraseña), con los cuatro estados obligatorios: cargando, vacío, error y sin permiso.
      · Verificación: `npm test` — el formulario de login envía exactamente usuario y contraseña, y no muestra ni pide el nombre de empresa; un 401 muestra el mensaje genérico sin revelar la causa; un 409 en registro señala el campo de empresa. `npx tsc --noEmit` y `npm run lint` pasan.

---

## Cierre

- [ ] **T020** Verificación de trazabilidad y de constitución.
      · Verificación: todo criterio de aceptación de la spec tiene al menos un test que lo nombra; `pytest --cov=src --cov-fail-under=80` pasa; la revisión de constitución no reporta consultas sin `company_id`.

---

## Tabla de trazabilidad

| Criterio | Tarea | Test |
| --- | --- | --- |
| CA-1.1 – CA-1.4 | T009, T010 | `test_register.py`, `test_password_policy.py` |
| CA-1.5 | T002, T003 | `test_schema.py::test_ca_1_5_sin_columna_de_texto_plano` |
| CA-1.6 | T015 | `test_logging.py::test_ca_1_6_password_no_aparece_en_logs` |
| CA-2.1 – CA-2.4 | T011 | `test_login.py` |
| CA-3.1 – CA-3.3, CA-3.5 | T013 | `test_session.py` |
| CA-3.4 | T018 | `AuthProvider.test.tsx` |
| CA-4.1 – CA-4.4 | T007, T014, T016 | `test_isolation.py` |
| RN-4 | T010 | `test_password_policy.py` |
| RN-6 | T011 | `test_login.py::test_rn_6_mensaje_identico` |
| RN-7 | T013 | `test_session.py::test_rn_7_usuario_deshabilitado` |
| RN-8, RN-9 | T014, T016 | `test_isolation.py` |

---

## Checklist de salida

- [x] Toda tarea tiene criterio de verificación ejecutable
- [x] Ningún criterio de aceptación queda sin tarea
- [x] Las tareas `[P]` de un mismo bloque no tocan los mismos archivos
- [x] Resuelto el conflicto con el límite de tareas (eliminado de la constitución)
