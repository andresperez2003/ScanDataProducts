// T019: pantalla de registro (spec HU-1, CA-1.1 a CA-1.4, RN-3).
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { me, register, type AuthSession } from "../../lib/api/auth";
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

async function abrirRegistro() {
  renderApp("/register");
  return screen.findByRole("form", { name: "Registrar empresa" });
}

async function rellenarYEnviar() {
  await userEvent.type(screen.getByLabelText("Empresa"), "Acme S.A.");
  await userEvent.type(screen.getByLabelText("Usuario"), "maria");
  await userEvent.type(screen.getByLabelText("Contraseña"), "Trazabilidad#2026");
  await userEvent.click(screen.getByRole("button", { name: "Registrar" }));
}

function campoMarcado(etiqueta: string): boolean {
  return screen.getByLabelText(etiqueta).getAttribute("aria-invalid") === "true";
}

beforeEach(() => {
  vi.mocked(me).mockReset().mockResolvedValue(null);
  vi.mocked(register).mockReset();
});

describe("RegisterPage", () => {
  it("pide empresa, usuario y contraseña", async () => {
    const formulario = await abrirRegistro();

    expect(within(formulario).getByLabelText("Empresa")).toBeTruthy();
    expect(within(formulario).getByLabelText("Usuario")).toBeTruthy();
    expect(within(formulario).getByLabelText("Contraseña")).toBeTruthy();
  });

  it("CA-1.1: envía los tres campos y queda con la sesión iniciada", async () => {
    vi.mocked(register).mockResolvedValue(SESION);
    await abrirRegistro();

    await rellenarYEnviar();

    await vi.waitFor(() =>
      expect(register).toHaveBeenCalledWith({
        company_name: "Acme S.A.",
        username: "maria",
        password: "Trazabilidad#2026",
      }),
    );
    expect(await screen.findByText(/maria · Acme S\.A\./)).toBeTruthy();
  });

  it("CA-1.2: un 409 de empresa señala el campo de empresa", async () => {
    vi.mocked(register).mockRejectedValue(
      new ApiError(409, "COMPANY_NAME_TAKEN", "Ese nombre de empresa ya está en uso."),
    );
    await abrirRegistro();

    await rellenarYEnviar();

    expect(await screen.findByText("Ese nombre de empresa ya está en uso.")).toBeTruthy();
    expect(campoMarcado("Empresa")).toBe(true);
    expect(campoMarcado("Usuario")).toBe(false);
  });

  it("RN-3: un 409 de usuario señala el campo de usuario", async () => {
    vi.mocked(register).mockRejectedValue(
      new ApiError(409, "USERNAME_TAKEN", "Ese nombre de usuario ya está en uso."),
    );
    await abrirRegistro();

    await rellenarYEnviar();

    expect(await screen.findByText("Ese nombre de usuario ya está en uso.")).toBeTruthy();
    expect(campoMarcado("Usuario")).toBe(true);
    expect(campoMarcado("Empresa")).toBe(false);
  });

  it("CA-1.3 y CA-1.4: los errores por campo del backend se muestran en su campo", async () => {
    vi.mocked(register).mockRejectedValue(
      new ApiError(400, "VALIDATION_ERROR", "Hay datos que corregir.", {
        company_name: "Campo obligatorio.",
        password: "Debe tener al menos 12 caracteres.",
      }),
    );
    await abrirRegistro();

    await userEvent.click(screen.getByRole("button", { name: "Registrar" }));

    expect(await screen.findByText("Debe tener al menos 12 caracteres.")).toBeTruthy();
    expect(campoMarcado("Empresa")).toBe(true);
    expect(campoMarcado("Contraseña")).toBe(true);
    expect(campoMarcado("Usuario")).toBe(false);
  });

  it("cargando: mientras se envía, el botón queda deshabilitado", async () => {
    vi.mocked(register).mockReturnValue(new Promise(() => undefined));
    await abrirRegistro();

    await userEvent.click(screen.getByRole("button", { name: "Registrar" }));

    const boton = await screen.findByRole("button", { name: "Registrando…" });
    expect(boton.hasAttribute("disabled")).toBe(true);
  });
});
