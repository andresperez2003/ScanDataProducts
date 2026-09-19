// Rutas de la aplicación.
import { Navigate, Route, Routes } from "react-router-dom";

import { HomePage } from "./features/auth/HomePage";
import { LoginPage } from "./features/auth/LoginPage";
import { ProtectedRoute } from "./features/auth/ProtectedRoute";
import { RedirectIfAuthenticated } from "./features/auth/RedirectIfAuthenticated";
import { RegisterPage } from "./features/auth/RegisterPage";

export function App() {
  return (
    <Routes>
      <Route element={<RedirectIfAuthenticated />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>
      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<HomePage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
