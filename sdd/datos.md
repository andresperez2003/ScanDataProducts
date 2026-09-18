---
paths:
  - "backend/src/models/**/*.py"
  - "backend/alembic/**/*.py"
  - "backend/src/repos/**/*.py"
---

# Datos y migraciones

## Deshabilitación en lugar de borrado

- Nada se borra físicamente. Toda entidad de negocio tiene:

  ```python
  disabled_at: datetime | None = Field(default=None, index=True)
  ```

  `None` significa activa.
- Los listados y los desplegables de creación filtran `disabled_at IS NULL`.
- El histórico y las exportaciones a Excel **incluyen los registros deshabilitados**,
  con su estado visible.
- Un registro deshabilitado no se puede usar en un seguimiento nuevo, pero los
  seguimientos que ya lo referencian siguen siendo válidos y legibles.
- Nunca se emite `DELETE` sobre una tabla de negocio.

## Campos de auditoría

Toda entidad de negocio lleva: `id` (UUID), `company_id`, `created_at`, `created_by`,
`disabled_at`, `disabled_by`.

## Fechas

- Los instantes se almacenan en UTC con zona horaria explícita (`timestamptz`).
- `expiry_date` y `received_date` son `date`, sin hora. No son instantes.

## Migraciones

- Todo cambio de esquema pasa por Alembic. Nada de `create_all()` fuera de los tests.
- Una migración ya aplicada **no se edita jamás**: se añade otra.
- Toda restricción que resuelve un caso borde de la spec vive en la base de datos:
  `UNIQUE`, `CHECK`, `FOREIGN KEY`, índices parciales.
- Revisa siempre el archivo que genera `--autogenerate` antes de aplicarlo:
  no detecta bien índices parciales ni `CHECK`.
