---
paths:
  - "backend/src/routers/**/*.py"
  - "backend/src/services/**/*.py"
  - "backend/src/repos/**/*.py"
---

# Capas del backend

Dependencias en una sola dirección: `routers/` → `services/` → `repos/`.

## routers/

- Traducen HTTP y nada más: validan la entrada con un schema, obtienen el `company_id`
  de la sesión, llaman a un servicio, devuelven la respuesta.
- `HTTPException` solo aparece aquí.
- Sin lógica condicional de negocio. Un `if` que decide una regla del dominio va al servicio.
- Todas las rutas bajo `/api/v1`.
- Toda operación que modifica estado exige token CSRF.

## services/

- Contienen las reglas de negocio. **No importan `fastapi` ni nada de HTTP.**
- Lanzan excepciones de dominio de `core/errors.py`, nunca `HTTPException`.
- Reciben y propagan `company_id` explícitamente.
- Deshabilitar una entidad es una operación del servicio, con su propio método.

## repos/

- Único lugar donde se construyen consultas.
- Devuelven objetos de dominio, no filas del ORM ni sesiones.
- Primer parámetro siempre `company_id`.
- Sin reglas de negocio: filtran, leen y escriben.

## Prohibido

- Que un router importe algo de `repos/`.
- Que un servicio importe `fastapi`, `Request` o `Response`.
- Que un repositorio decida qué es un error de negocio.
