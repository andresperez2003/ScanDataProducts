# Trazabilidad de Lotes

Aplicación multi-tenant para registrar seguimientos de lote y fecha de vencimiento
de productos por proveedor. Backend FastAPI. Desarrollo dirigido por specs.

## Comandos

- Base de datos: `docker compose up -d db`
- Migraciones: `cd backend && alembic upgrade head`
- Nueva migración: `cd backend && alembic revision --autogenerate -m "..."`
- API local: `cd backend && uvicorn src.main:app --reload`
- Tests: `cd backend && pytest`
- Un test: `cd backend && pytest tests/integration/test_auth.py::test_nombre -q`
- Cobertura: `cd backend && pytest --cov=src --cov-fail-under=80`
- Lint y tipos: `cd backend && ruff check . && ruff format --check . && mypy --strict src`

## Estructura

- `backend/src/routers/` — traducción HTTP. Sin lógica de negocio.
- `backend/src/services/` — reglas de negocio. No importa fastapi.
- `backend/src/repos/` — acceso a datos. Devuelve objetos de dominio.
- `backend/src/models/` — entidades SQLModel y schemas Pydantic.
- `backend/src/core/` — config, errores, sesión, dependencias.
- `specs/NNN-nombre/` — spec.md, plan.md y tasks.md de cada feature.
- `sdd/constitution.md` — las reglas completas del proyecto.

## Flujo de trabajo

El orden es spec → plan → tasks → código. Nunca se salta un paso.

- No escribas código que no corresponda a una tarea de un `tasks.md`.
- Si algo falta o está ambiguo en la spec, detente y pregúntame. No lo inventes.
- Los tests se derivan de `spec.md`, nunca del código ya escrito.
- Antes de crear un helper, schema o componente, busca uno equivalente.
- Instala solo las dependencias necesarias. Si falta una, detente y pregunta.
- Trabaja una feature a la vez, en su rama: `feature/NNN-nombre`.

## Las reglas que más se incumplen

1. **Aislamiento entre empresas.** Ninguna consulta toca una tabla de negocio sin filtrar
   por el `company_id` de la sesión. El `company_id` nunca llega desde el cliente.
   Los repositorios lo reciben como primer parámetro obligatorio.
2. **Nada se borra.** Se marca `disabled_at`. Los listados filtran `disabled_at IS NULL`;
   el histórico y las exportaciones incluyen todo.
3. `HTTPException` solo en `backend/src/routers/`. Los servicios lanzan excepciones de dominio.
4. Una migración aplicada no se edita nunca; se añade otra.
5. Función ≤ 50 líneas, archivo ≤ 500.

