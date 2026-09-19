import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { AuthSession } from "../../lib/api/auth";
import { SESSION_QUERY_KEY } from "./AuthProvider";

/**
 * Envío de login o registro: al tener éxito guarda la sesión devuelta en la
 * caché de `/auth/me`, sin otra petición. No navega: las pantallas redirigen
 * cuando el estado pasa a "authenticated" (ver `RedirectIfAuthenticated`), así
 * `ProtectedRoute` nunca ve un estado anterior al de la sesión nueva.
 */
export function useSessionMutation<T>(enviar: (datos: T) => Promise<AuthSession>) {
  const queryClient = useQueryClient();
  return useMutation({
    // Solo los datos: TanStack pasa además su propio contexto como 2.º argumento.
    mutationFn: (datos: T) => enviar(datos),
    onSuccess: (sesion) => {
      queryClient.setQueryData(SESSION_QUERY_KEY, sesion);
    },
  });
}
