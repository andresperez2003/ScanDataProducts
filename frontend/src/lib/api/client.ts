// Único punto desde el que el frontend llama a la API (sdd/frontend.md).

const CSRF_COOKIE = "csrf_token";
const CSRF_HEADER = "X-CSRF-Token";
const SAFE_METHODS = new Set(["GET", "HEAD"]);

/** Formato único de error del backend (plan §5). */
export interface ApiErrorBody {
  error: { code: string; message: string; fields: Record<string, string> };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields: Record<string, string>;

  constructor(status: number, code: string, message: string, fields: Record<string, string> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

function readCookie(name: string): string | null {
  for (const parte of document.cookie.split("; ")) {
    const [clave, ...valor] = parte.split("=");
    if (clave === name) return decodeURIComponent(valor.join("="));
  }
  return null;
}

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  if (typeof value !== "object" || value === null || !("error" in value)) return false;
  const error: unknown = value.error;
  return typeof error === "object" && error !== null && "code" in error && "message" in error;
}

async function toApiError(response: Response): Promise<ApiError> {
  const cuerpo: unknown = await response.json().catch(() => null);
  if (isApiErrorBody(cuerpo)) {
    const { code, message, fields } = cuerpo.error;
    return new ApiError(response.status, code, message, fields ?? {});
  }
  return new ApiError(response.status, "UNEXPECTED_ERROR", "Respuesta inesperada del servidor.");
}

/**
 * Petición a la API con la cookie de sesión y, si modifica estado, la cabecera
 * CSRF copiada de la cookie `csrf_token` (double-submit, plan §2).
 */
export async function apiRequest<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers = new Headers();
  if (body !== undefined) headers.set("Content-Type", "application/json");
  const csrf = readCookie(CSRF_COOKIE);
  if (!SAFE_METHODS.has(method) && csrf) headers.set(CSRF_HEADER, csrf);

  let response: Response;
  try {
    response = await fetch(path, {
      method,
      headers,
      credentials: "include",
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "No se pudo conectar con el servidor.");
  }

  if (!response.ok) throw await toApiError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
