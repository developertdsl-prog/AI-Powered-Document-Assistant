import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { clearAuthToken, getAuthToken, onUnauthorized } from "@/lib/auth";
import { ApiError } from "@/services/api";
import {
  fetchCurrentUser,
  loginAccount,
  registerAccount,
} from "@/services/auth";
import type { RegisterInput, UserRecord } from "@/types/auth";
import { AuthContext, type AuthStatus } from "./AuthContext";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserRecord | null>(null);
  const [status, setStatus] = useState<AuthStatus>(() =>
    getAuthToken() ? "loading" : "anonymous",
  );

  // Restore the session from a stored token exactly once on mount.
  useEffect(() => {
    if (!getAuthToken()) {
      return;
    }

    let active = true;

    fetchCurrentUser()
      .then((record) => {
        if (!active) {
          return;
        }

        setUser(record);
        setStatus("authenticated");
      })
      .catch((error: unknown) => {
        if (!active) {
          return;
        }

        // Only a token the server rejected ends the session; a network
        // failure keeps the stored token so a reload can retry it.
        if (error instanceof ApiError && error.status === 401) {
          clearAuthToken();
        }

        setUser(null);
        setStatus("anonymous");
      });

    return () => {
      active = false;
    };
  }, []);

  // Any protected request that answers 401 ends the session everywhere.
  useEffect(
    () =>
      onUnauthorized(() => {
        setUser(null);
        setStatus("anonymous");
      }),
    [],
  );

  const login = useCallback(async (email: string, password: string) => {
    const record = await loginAccount(email, password);

    setUser(record);
    setStatus("authenticated");
  }, []);

  const register = useCallback(async (input: RegisterInput) => {
    await registerAccount(input);

    // Registration does not issue a token, so sign in with the new
    // credentials to avoid a second trip through the login form.
    const record = await loginAccount(input.email, input.password);

    setUser(record);
    setStatus("authenticated");
  }, []);

  const logout = useCallback(() => {
    clearAuthToken();
    setUser(null);
    setStatus("anonymous");
  }, []);

  const value = useMemo(
    () => ({ status, user, login, register, logout }),
    [status, user, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
