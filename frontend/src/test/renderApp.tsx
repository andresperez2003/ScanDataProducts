// Utilidad de tests: la app completa en memoria, en una ruta concreta.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { App } from "../App";
import { AuthProvider } from "../features/auth/AuthProvider";

export function renderApp(ruta: string) {
  const clienteQuery = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={clienteQuery}>
      <AuthProvider>
        <MemoryRouter initialEntries={[ruta]}>
          <App />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}
