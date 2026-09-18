# Constitución del proyecto — Trazabilidad de Lotes

**Vigente desde:** 2026-09-18
**Stack:** Python 3.12 · FastAPI · SQLModel · Alembic · PostgreSQL · React + Vite · pytest
**Contexto:** proyecto nuevo, multi-tenant, desarrollo en solitario, arquitectura en capas.

> Estas reglas no se negocian por feature. Si una estorba de verdad, se cambia aquí
> y se anota en el registro del final — nunca se ignora en silencio.

---

## Principios

### 1. Aislamiento entre empresas

Este es el principio más importante del proyecto. Una fuga de datos entre empresas es el peor fallo posible aquí.

- Toda tabla de negocio tiene `company_id` no nulo, con índice.
- **Ninguna consulta a una tabla de negocio se ejecuta sin filtrar por el `company_id` de la sesión.** Sin excepciones.
- El `company_id` **nunca** se acepta desde el cliente: ni en el cuerpo, ni en la query, ni en la ruta. Siempre sale de la sesión autenticada.
- Los repositorios reciben `company_id` como primer parámetro obligatorio. No lo leen de un contexto global ni de una variable de módulo.
- Todo test de integración de un endpoint incluye un caso "usuario de otra empresa", que debe responder **404** (no 403: un 403 confirma que el recurso existe).

### 2. Tests

- Todo endpoint tiene al menos un test de integración contra Postgres real, nunca contra mocks del repositorio.
- Toda regla de negocio tiene un test unitario con caso positivo y caso negativo.
- **Los tests se derivan de `spec.md`, nunca del código ya escrito.**
- El nombre de cada test lleva el identificador del criterio o regla que cubre: `test_ca_1_2_...`, `test_rn_3_...`.
- La cobertura de `backend/src/` no baja del 80 %. El hook de pre-commit lo bloquea.
- Modificar un test para que pase exige explicarlo en el mensaje del commit.

### 3. Capas

- Backend en tres capas, con dependencias en una sola dirección: `routers/` → `services/` → `repos/`.
- `services/` y el dominio **no importan `fastapi`** ni nada de HTTP. Si un servicio necesita FastAPI, la responsabilidad está mal ubicada.
- `repos/` devuelve objetos de dominio, no filas del ORM ni sesiones.
- `routers/` no contiene lógica condicional de negocio: valida entrada, llama a un servicio, traduce la respuesta.
- El frontend nunca replica una regla de negocio: la valida el backend y la UI solo refleja el resultado.

### 4. Datos

- **Nada se borra.** Toda entidad de negocio tiene `disabled_at: datetime | None`, donde `None` significa activa.
- Deshabilitar es una operación explícita del dominio, no un `UPDATE` suelto desde un router.
- Toda consulta de listado filtra `disabled_at IS NULL` salvo que la spec pida explícitamente incluir el histórico.
- Un registro deshabilitado sigue siendo legible en el histórico y en las exportaciones; solo desaparece de los desplegables de creación.
- Una migración ya aplicada **no se edita jamás**: se añade otra.
- Todo cambio de esquema pasa por Alembic. Nada de `create_all()` fuera de los tests.
- Toda restricción que resuelve un caso borde de la spec vive en la base de datos (`UNIQUE`, `CHECK`, `FK`), no solo en el código.

### 5. Errores

- Los errores de dominio son excepciones propias en `core/errors.py`, heredando de una base común.
- `HTTPException` solo aparece en `routers/`. Un servicio que la lanza es un bug.
- Prohibidos `except:` y `except Exception:` sin relanzar.
- Cada excepción de dominio tiene su mapeo a código HTTP declarado en un único lugar.
- Un caso previsto nunca se responde con 500.
- Los mensajes de error que llegan al cliente no revelan si un recurso de otra empresa existe.

### 6. Tamaño, estilo y dependencias

- `ruff check`, `ruff format --check` y `mypy --strict` pasan antes de cada commit (backend). `eslint` y `tsc --noEmit` en el frontend.
- Función: máximo **50 líneas**. Archivo: máximo **500**. Al superarlo se extrae, no se silencia el linter.
- Ningún `# type: ignore` ni `// @ts-ignore` sin un comentario que explique por qué.
- Sin campos opcionales en los modelos salvo justificación escrita en `plan.md`.
- Ninguna dependencia nueva entra sin estar justificada en `plan.md`: qué resuelve y qué alternativa se descartó.
- Si hace falta una librería que no está declarada, **el trabajo se detiene y se pregunta**. No se instala por iniciativa propia.

### 7. Alcance y reutilización

- Solo se escribe código que corresponda a una tarea de `tasks.md`. Nada "de paso", nada "ya que estaba".
- Un endpoint, campo, pantalla o modelo que no esté en `spec.md` no se crea. Si falta, se detiene el trabajo y se corrige la spec primero.
- Antes de crear un helper, schema o componente, se busca uno equivalente. Crear un duplicado exige decir por qué en el commit.
- Si una feature necesita más de 15 tareas por fase (backend/frontend), se parte en dos specs.

---

## Convenciones fijas

| Área | Regla |
| --- | --- |
| **Contraseñas** | Hash con Argon2id, parámetros en configuración. Nunca se almacenan ni se registran en claro, ni aparecen en logs, trazas o mensajes de error. El endpoint de login responde igual ante usuario inexistente y contraseña incorrecta, y en el mismo tiempo. |
| **Sesión** | Cookie firmada `HttpOnly`, `Secure`, `SameSite=Lax`. El identificador de sesión nunca es accesible desde JavaScript. Toda petición que modifica estado exige token CSRF. La sesión caduca por inactividad según configuración. |
| **Secretos** | Ninguna credencial en el código ni en git. Toda configuración llega por variables de entorno y se valida con `Settings` de Pydantic al arrancar: si falta una, la app no levanta. `.env` en `.gitignore`, `.env.example` versionado. |
| **Async** | Endpoints, servicios y repositorios son `async`. Prohibido llamar código bloqueante dentro de una corrutina; si es inevitable, `run_in_threadpool` con comentario que lo justifique. |
| **Versionado de API** | Todas las rutas bajo `/api/v1`. Romper un contrato publicado exige `/api/v2`; añadir un campo opcional no lo rompe. |
| **Observabilidad** | Logging estructurado en JSON con `request_id` y `company_id` en cada petición. Todo error manejado se registra **una sola vez**, donde se traduce a HTTP. Prohibido `print`. |
| **Fechas** | Todo instante se almacena en UTC con zona horaria explícita. Las fechas de vencimiento e ingreso son fechas sin hora (`date`), no instantes. La conversión a zona local ocurre solo en el frontend. |
| **Frontend** | TypeScript en modo estricto. Ninguna llamada a la API fuera de `frontend/src/lib/api/`. El estado del servidor se gestiona con una capa de datos, no con `useEffect` a mano. Ningún componente supera 200 líneas. |

---

## Cómo se hace cumplir

Automatizado en `.pre-commit-config.yaml`: ruff, ruff-format, mypy strict y `pytest --cov-fail-under=80`.

Lo que no se automatiza — aislamiento entre empresas, capas, alcance, reutilización — se verifica al cerrar cada feature:

```
Revisa el código nuevo contra docs/sdd/constitution.md.
Presta atención especial al principio 1: busca cualquier consulta,
repositorio o servicio que acceda a datos sin filtrar por company_id.
Reporta cada incumplimiento con archivo, línea y principio violado.
No corrijas nada todavía, solo lista.
```

---

## Fuera de alcance del proyecto

- No hay panel de administración global entre empresas.
- No hay roles ni permisos dentro de una empresa: todos sus usuarios ven y editan lo mismo.
- No hay facturación, inventario ni control de stock. Esto registra trazabilidad, no existencias.
- No hay notificaciones ni alertas de vencimiento en la primera versión.
- No hay app móvil nativa.

---

## Registro de cambios

| Fecha | Cambio | Motivo |
| --- | --- | --- |
| 2026-09-18 | Límite de 15 tareas por fase, no global | Permitir features backend + frontend completos sin partir innecesariamente; primera aplicación en 001-cimientos-y-auth (10 backend + 10 frontend) |
| 2026-09-18 | Versión inicial | — |
