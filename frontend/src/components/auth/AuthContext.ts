import { createContext, useContext } from "react";
import type { RegisterInput, UserRecord } from "@/types/auth";

/**
 * `loading` only lasts while a stored token is being verified, so the route
 * guard can show a spinner instead of flashing the login page at a user
 * whose session is still valid.
 */
export type AuthStatus = "loading" | "authenticated" | "anonymous";

export interface AuthContextValue {
  status: AuthStatus;
  user: UserRecord | null;
  login: (email: string, password: string) => Promise<void>;
  register: (input: RegisterInput) => Promise<void>;
  logout: () => void;
}

/**
 * Kept in its own module so `AuthProvider.tsx` exports only a component and
 * hot reload keeps working.
 */
export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider.");
  }

  return context;
}
