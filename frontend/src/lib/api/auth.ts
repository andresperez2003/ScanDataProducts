// /api/v1/auth: tipos derivados de los contratos de plan §5.
import { ApiError, apiRequest } from "./client";

const BASE = "/api/v1/auth";

export interface User {
  id: string;
  username: string;
}

export interface Company {
  id: string;
  name: string;
}

export interface AuthSession {
  user: User;
  company: Company;
}

export interface RegisterRequest {
  company_name: string;
  username: string;
  password: string;
}

/** Solo usuario y contraseña: el login nunca pide la empresa (RN-3). */
export interface LoginRequest {
  username: string;
  password: string;
}

export function register(datos: RegisterRequest): Promise<AuthSession> {
  return apiRequest<AuthSession>("POST", `${BASE}/register`, datos);
}

export function login(datos: LoginRequest): Promise<AuthSession> {
  return apiRequest<AuthSession>("POST", `${BASE}/login`, datos);
}

export async function logout(): Promise<void> {
  await apiRequest<undefined>("POST", `${BASE}/logout`);
}

/** Sesión actual, o `null` si no la hay: el estado "no autenticado" (CA-3.4). */
export async function me(): Promise<AuthSession | null> {
  try {
    return await apiRequest<AuthSession>("GET", `${BASE}/me`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}
