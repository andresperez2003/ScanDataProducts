---
paths:
  - "frontend/src/**/*.{ts,tsx}"
---

# Frontend

## Estructura

- `features/<modulo>/` — una carpeta por módulo: `auth`, `products`, `suppliers`, `tracing`, `profile`.
  Dentro: componentes, hooks y tipos de ese módulo.
- `components/` — solo lo compartido de verdad por dos o más módulos.
- `lib/api/` — **único lugar desde el que se llama a la API.** Un archivo por recurso,
  con los tipos de request y response derivados de los contratos de `plan.md`.

## Reglas

- TypeScript estricto. Ningún `any`. Ningún `// @ts-ignore` sin comentario que lo justifique.
- Ningún componente supera 200 líneas. Si crece, se extrae.
- El frontend **no replica reglas de negocio**. No decide si un lote es válido ni si un
  producto puede usarse: lo valida el backend y la UI refleja la respuesta.
- Los desplegables de productos y proveedores se llenan desde la API, filtrando activos.
  Nunca se escriben opciones a mano.
- Todo formulario refleja los errores de validación que devuelve el backend, campo por campo.
- Las fechas se muestran en la zona local del navegador; se envían al backend en ISO 8601.
- La cookie de sesión es `HttpOnly`: el frontend nunca lee ni guarda el token.
  Las peticiones van con `credentials: "include"` y el token CSRF en la cabecera.
- Estados que toda vista con datos debe manejar: cargando, vacío, error y sin permiso.
  Una vista que solo maneja el caso feliz está incompleta.
