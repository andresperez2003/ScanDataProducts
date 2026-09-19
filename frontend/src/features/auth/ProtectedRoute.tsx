// Área protegida: sin sesión, redirige a /login sin exponer datos (CA-3.4).
import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "./AuthProvider";

export function ProtectedRoute() {
  const { status, error } = useAuth();

  // Mientras se comprueba la sesión no se muestra ni el contenido ni el login.
  if (status === "loading") return <p role="status">Cargando…</p>;
  if (status === "error") {
    return (
      <p role="alert">
        No se pudo comprobar la sesión. {error?.message ?? ""}
      </p>
    );
  }
  if (status === "anonymous") return <Navigate to="/login" replace />;
  return <Outlet />;
}
