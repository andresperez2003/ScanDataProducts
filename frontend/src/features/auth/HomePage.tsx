// Portada protegida mínima: quién eres y cómo cerrar sesión (CA-3.2).
// Las features 002+ añadirán aquí su contenido.
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { logout } from "../../lib/api/auth";
import { SESSION_QUERY_KEY, useAuth } from "./AuthProvider";
import { formErrors } from "./formErrors";

export function HomePage() {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const salida = useMutation({
    mutationFn: () => logout(),
    // Sin sesión en caché, ProtectedRoute lleva a /login.
    onSuccess: () => queryClient.setQueryData(SESSION_QUERY_KEY, null),
  });
  const { general } = formErrors(salida.error);

  if (!session) return null;
  return (
    <main>
      <p>
        {session.user.username} · {session.company.name}
      </p>
      {general ? <p role="alert">{general}</p> : null}
      <button type="button" onClick={() => salida.mutate()} disabled={salida.isPending}>
        Cerrar sesión
      </button>
    </main>
  );
}
