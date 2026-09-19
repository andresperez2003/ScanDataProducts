// T019: pantalla de inicio de sesión (spec HU-2, RN-3, RN-6, §7 Usabilidad).
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { login, logout, me, type AuthSession } from "../../lib/api/auth";
import { ApiError } from "../../lib/api/client";
import { renderApp } from "../../test/renderApp";

vi.mock("../../lib/api/auth", () => ({
  me: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  register: vi.fn(),
}));

const SESION: AuthSession = {
  user: { id: "u-1", username: "maria" },
  company: { id: "c-1", name: "Acme S.A." },
};

async function abrirLogin() {
  renderApp("/login");
  return screen.findByRole("form", { name: "Iniciar sesión" });
}

beforeEach(() => {
  vi.mocked(me).mockReset().mockResolvedValue(null);
  vi.mocked(login).mockReset();
  vi.mocked(logout).mockReset();
});

describe("LoginPage", () => {
  it("§7: pide solo usuario y contraseña, nunca la empresa", async () => {
    const formulario = await abrirLogin();

    expect(within(formulario).getAllByRole("textbox")).toHaveLength(1);
    expect(within(formulario).getByLabelText("Usuario")).toBeTruthy();
    expect(within(formulario).getByLabelText("Contraseña")).toBeTruthy();
    expect(within(formulario).queryByLabelText(/empresa/i)).toBeNull();
  });

  it("RN-3: envía exactamente usuario y contraseña, y entra en la app", async () => {
    vi.mocked(login).mockResolvedValue(SESION);
    await abrirLogin();

    await userEvent.type(screen.getByLabelText("Usuario"), "maria");
    await userEvent.type(screen.getByLabelText("Contraseña"), "Trazabilidad#2026");
    await userEvent.click(screen.getByRole("button", { name: "Entrar" }));

    await vi.waitFor(() =>
      expect(login).toHaveBeenCalledWith({ username: "maria", password: "Trazabilidad#2026" }),
    );
    expect(await screen.findByText(/maria · Acme S\.A\./)).toBeTruthy();
  });

  it("RN-6: un 401 muestra el mensaje genérico del servidor sin revelar la causa", async () => {
    vi.mocked(login).mockRejectedValue(
      new ApiError(401, "INVALID_CREDENTIALS", "Usuario o contraseña incorrectos."),
    );
    await abrirLogin();

    await userEvent.type(screen.getByLabelText("Usuario"), "nadie");
    await userEvent.type(screen.getByLabelText("Contraseña"), "x");
    await userEvent.click(screen.getByRole("button", { name: "Entrar" }));

    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).toBe("Usuario o contraseña incorrectos.");
  });

  it("vacío: el formulario vacío se envía y muestra los errores por campo del backend", async () => {
    vi.mocked(login).mockRejectedValue(
      new ApiError(400, "VALIDATION_ERROR", "Hay datos que corregir.", {
        password: "Campo obligatorio.",
      }),
    );
    await abrirLogin();

    await userEvent.click(screen.getByRole("button", { name: "Entrar" }));

    await vi.waitFor(() => expect(login).toHaveBeenCalledWith({ username: "", password: "" }));
    const contrasena = screen.getByLabelText("Contraseña");
    expect(contrasena.getAttribute("aria-invalid")).toBe("true");
    expect(await screen.findByText("Campo obligatorio.")).toBeTruthy();
  });

  it("cargando: mientras se envía, el botón queda deshabilitado", async () => {
    vi.mocked(login).mockReturnValue(new Promise(() => undefined));
    await abrirLogin();

    await userEvent.click(screen.getByRole("button", { name: "Entrar" }));

    const boton = await screen.findByRole("button", { name: "Entrando…" });
    expect(boton.hasAttribute("disabled")).toBe(true);
  });

  it("error: un fallo de red se muestra al usuario", async () => {
    vi.mocked(login).mockRejectedValue(
      new ApiError(0, "NETWORK_ERROR", "No se pudo conectar con el servidor."),
    );
    await abrirLogin();

    await userEvent.click(screen.getByRole("button", { name: "Entrar" }));

    expect((await screen.findByRole("alert")).textContent).toMatch(/No se pudo conectar/);
  });
});

describe("cerrar sesión", () => {
  it("CA-3.2: el botón cierra la sesión y vuelve al login", async () => {
    vi.mocked(me).mockResolvedValue(SESION);
    vi.mocked(logout).mockResolvedValue(undefined);
    renderApp("/");

    await userEvent.click(await screen.findByRole("button", { name: "Cerrar sesión" }));

    expect(logout).toHaveBeenCalled();
    expect(await screen.findByRole("form", { name: "Iniciar sesión" })).toBeTruthy();
  });
});
