// Pantallas públicas (login, registro): con sesión, se entra directamente en la app.
import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "./AuthProvider";

export function RedirectIfAuthenticated() {
  const { status } = useAuth();
  if (status === "authenticated") return <Navigate to="/" replace />;
  return <Outlet />;
}
