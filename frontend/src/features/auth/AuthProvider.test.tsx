// T018: sesión actual y rutas protegidas (spec CA-3.1, CA-3.4; sdd/frontend.md).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { me, type AuthSession } from "../../lib/api/auth";
import { ApiError } from "../../lib/api/client";
import { AuthProvider, useAuth } from "./AuthProvider";
import { ProtectedRoute } from "./ProtectedRoute";

vi.mock("../../lib/api/auth", () => ({ me: vi.fn() }));
const meSimulado = vi.mocked(me);

const SESION: AuthSession = {
  user: { id: "u-1", username: "maria" },
  company: { id: "c-1", name: "Acme S.A." },
};

const pantallaLogin = vi.fn(() => <p>Pantalla de login</p>);

function Privado() {
  const { session } = useAuth();
  return <p>Hola {session?.user.username}</p>;
}

function PantallaLogin() {
  return pantallaLogin();
}

function renderizar() {
  const clienteQuery = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={clienteQuery}>
      <AuthProvider>
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route path="/login" element={<PantallaLogin />} />
            <Route element={<ProtectedRoute />}>
              <Route path="/" element={<Privado />} />
            </Route>
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  meSimulado.mockReset();
  pantallaLogin.mockClear();
});

describe("ProtectedRoute", () => {
  it("CA-3.4: sin sesión redirige a /login sin mostrar el contenido", async () => {
    meSimulado.mockResolvedValue(null);

    renderizar();

    expect(await screen.findByText("Pantalla de login")).toBeTruthy();
    expect(screen.queryByText(/Hola/)).toBeNull();
  });

  it("CA-3.1: con sesión renderiza el contenido con los datos de la sesión", async () => {
    meSimulado.mockResolvedValue(SESION);

    renderizar();

    expect(await screen.findByText("Hola maria")).toBeTruthy();
  });

  it("mientras carga no parpadea mostrando la pantalla de login", async () => {
    let resolver: (sesion: AuthSession) => void = () => undefined;
    meSimulado.mockReturnValue(
      new Promise((ok) => {
        resolver = ok;
      }),
    );

    renderizar();

    expect(screen.getByRole("status").textContent).toMatch(/Cargando/);
    resolver(SESION);
    expect(await screen.findByText("Hola maria")).toBeTruthy();
    expect(pantallaLogin).not.toHaveBeenCalled();
  });

  it("si no se puede comprobar la sesión muestra el error, sin redirigir", async () => {
    meSimulado.mockRejectedValue(new ApiError(0, "NETWORK_ERROR", "Sin conexión."));

    renderizar();

    expect((await screen.findByRole("alert")).textContent).toMatch(/Sin conexión/);
    expect(pantallaLogin).not.toHaveBeenCalled();
  });
});
