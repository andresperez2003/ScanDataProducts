// T017: cliente de la API de autenticación (plan §5; spec CA-1.3, CA-2.2, CA-3.4, §7).
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { login, logout, me, register } from "./auth";
import { ApiError } from "./client";

const SESION = {
  user: { id: "u-1", username: "maria" },
  company: { id: "c-1", name: "Acme S.A." },
};

function respuesta(status: number, cuerpo?: unknown): Response {
  if (cuerpo === undefined) return new Response(null, { status });
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function error(status: number, code: string, fields: Record<string, string> = {}) {
  return respuesta(status, { error: { code, message: `mensaje ${code}`, fields } });
}

function servidor(...respuestas: Response[]) {
  const fetchSimulado = vi.fn<typeof fetch>();
  for (const r of respuestas) fetchSimulado.mockResolvedValueOnce(r);
  vi.stubGlobal("fetch", fetchSimulado);
  return fetchSimulado;
}

function peticion(fetchSimulado: ReturnType<typeof servidor>, n = 0) {
  const llamada = fetchSimulado.mock.calls[n];
  if (!llamada) throw new Error(`no hubo petición ${n}`);
  const [url, init] = llamada;
  return { url: String(url), init: init ?? {}, headers: new Headers(init?.headers) };
}

function ponerCookieCsrf(valor: string) {
  document.cookie = `csrf_token=${valor}; path=/`;
}

beforeEach(() => {
  document.cookie = "csrf_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("register", () => {
  it("CA-1.1: envía los tres campos y devuelve la sesión", async () => {
    const fetchSimulado = servidor(respuesta(201, SESION));

    const sesion = await register({
      company_name: "Acme S.A.",
      username: "maria",
      password: "Trazabilidad#2026",
    });

    expect(sesion).toEqual(SESION);
    const { url, init } = peticion(fetchSimulado);
    expect(url).toBe("/api/v1/auth/register");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({
      company_name: "Acme S.A.",
      username: "maria",
      password: "Trazabilidad#2026",
    });
  });

  it("CA-1.3: un 400 con fields produce errores por campo", async () => {
    servidor(error(400, "VALIDATION_ERROR", { company_name: "Campo obligatorio." }));

    const fallo = await register({ company_name: "", username: "m", password: "x" }).catch(
      (e: unknown) => e,
    );

    expect(fallo).toBeInstanceOf(ApiError);
    const apiError = fallo as ApiError;
    expect(apiError.status).toBe(400);
    expect(apiError.code).toBe("VALIDATION_ERROR");
    expect(apiError.fields).toEqual({ company_name: "Campo obligatorio." });
  });
});

describe("login", () => {
  it("RN-3: envía exactamente usuario y contraseña", async () => {
    const fetchSimulado = servidor(respuesta(200, SESION));

    await login({ username: "maria", password: "Trazabilidad#2026" });

    const { url, init } = peticion(fetchSimulado);
    expect(url).toBe("/api/v1/auth/login");
    expect(JSON.parse(String(init.body))).toEqual({
      username: "maria",
      password: "Trazabilidad#2026",
    });
  });

  it("CA-2.2: un 401 se convierte en error con el mensaje del servidor", async () => {
    servidor(error(401, "INVALID_CREDENTIALS"));

    const fallo = await login({ username: "maria", password: "mala" }).catch(
      (e: unknown) => e as ApiError,
    );

    expect(fallo).toMatchObject({
      status: 401,
      code: "INVALID_CREDENTIALS",
      message: "mensaje INVALID_CREDENTIALS",
      fields: {},
    });
  });
});

describe("me", () => {
  it("CA-3.1: con sesión devuelve la sesión actual", async () => {
    servidor(respuesta(200, SESION));

    expect(await me()).toEqual(SESION);
  });

  it("CA-3.4: un 401 produce el estado no autenticado", async () => {
    servidor(error(401, "NOT_AUTHENTICATED"));

    expect(await me()).toBeNull();
  });

  it("un error distinto de 401 no se confunde con 'no autenticado'", async () => {
    servidor(respuesta(500, "<html>error</html>"));

    await expect(me()).rejects.toBeInstanceOf(ApiError);
  });
});

describe("logout", () => {
  it("CA-3.2: un 204 se resuelve sin cuerpo", async () => {
    servidor(respuesta(204));

    await expect(logout()).resolves.toBeUndefined();
  });
});

describe("protección CSRF y cookies (§7)", () => {
  it("toda petición que modifica estado lleva la cabecera CSRF", async () => {
    ponerCookieCsrf("valor-csrf");
    const fetchSimulado = servidor(
      respuesta(201, SESION),
      respuesta(200, SESION),
      respuesta(204),
    );

    await register({ company_name: "A", username: "b", password: "c" });
    await login({ username: "b", password: "c" });
    await logout();

    for (const n of [0, 1, 2]) {
      expect(peticion(fetchSimulado, n).headers.get("X-CSRF-Token")).toBe("valor-csrf");
    }
  });

  it("toda petición envía las cookies (credentials: include)", async () => {
    const fetchSimulado = servidor(respuesta(200, SESION), respuesta(204));

    await me();
    await logout();

    expect(peticion(fetchSimulado, 0).init.credentials).toBe("include");
    expect(peticion(fetchSimulado, 1).init.credentials).toBe("include");
  });
});

describe("respuestas inesperadas", () => {
  it("un error sin el formato del contrato no rompe el cliente", async () => {
    servidor(respuesta(502, "<html>bad gateway</html>"));

    const fallo = await login({ username: "a", password: "b" }).catch(
      (e: unknown) => e as ApiError,
    );

    expect(fallo).toMatchObject({ status: 502, code: "UNEXPECTED_ERROR", fields: {} });
  });

  it("un fallo de red se convierte en ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(new TypeError("red")));

    const fallo = await me().catch((e: unknown) => e as ApiError);

    expect(fallo).toMatchObject({ status: 0, code: "NETWORK_ERROR" });
  });
});
