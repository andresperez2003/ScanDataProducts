import { ApiError } from "../../lib/api/client";

export interface FormErrors {
  /** Error de cada campo, tal como lo devuelve el backend. */
  fields: Record<string, string>;
  /** Error que no pertenece a ningún campo (401, red, inesperado). */
  general: string | null;
}

const SIN_ERRORES: FormErrors = { fields: {}, general: null };

/**
 * Traduce la respuesta de error a lo que muestra el formulario. No decide
 * ninguna regla: solo coloca el mensaje del backend en su sitio.
 * `codeToField` asocia códigos de error sin `fields` (p. ej. un 409) a su campo.
 */
export function formErrors(
  error: unknown,
  codeToField: Record<string, string> = {},
): FormErrors {
  if (error === null || error === undefined) return SIN_ERRORES;
  if (!(error instanceof ApiError)) {
    return { fields: {}, general: "Ha ocurrido un error inesperado." };
  }
  const fields = { ...error.fields };
  const campo = codeToField[error.code];
  if (campo) fields[campo] = error.message;
  return {
    fields,
    general: Object.keys(fields).length > 0 ? null : error.message,
  };
}
