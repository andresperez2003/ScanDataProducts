// Sesión actual a partir de GET /auth/me, gestionada con TanStack Query.
import { useQuery } from "@tanstack/react-query";
import { createContext, useContext, type ReactNode } from "react";

import { me, type AuthSession } from "../../lib/api/auth";

export const SESSION_QUERY_KEY = ["auth", "me"] as const;

export type AuthStatus = "loading" | "authenticated" | "anonymous" | "error";

export interface AuthState {
  status: AuthStatus;
  session: AuthSession | null;
  error: Error | null;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const query = useQuery({ queryKey: SESSION_QUERY_KEY, queryFn: me, retry: false });

  let status: AuthStatus = "loading";
  if (query.isError) status = "error";
  else if (query.isSuccess) status = query.data ? "authenticated" : "anonymous";

  const value: AuthState = {
    status,
    session: query.data ?? null,
    error: query.error,
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const value = useContext(AuthContext);
  if (value === null) throw new Error("useAuth debe usarse dentro de <AuthProvider>.");
  return value;
}
