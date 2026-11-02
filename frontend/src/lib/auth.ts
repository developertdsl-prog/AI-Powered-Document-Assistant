const TOKEN_KEY = "document-assistant-token";

type UnauthorizedListener = () => void;

const unauthorizedListeners = new Set<UnauthorizedListener>();

export function getAuthToken(): string | null {
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setAuthToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearAuthToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}

/** Headers every authenticated request must carry. */
export function authHeaders(): Record<string, string> {
  const token = getAuthToken();

  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Subscribe to sessions that end because the backend rejected the token.
 * The auth provider uses this to flip back to anonymous, which makes the
 * route guard send the user to the login page.
 *
 * Returns the unsubscribe function.
 */
export function onUnauthorized(listener: UnauthorizedListener): () => void {
  unauthorizedListeners.add(listener);

  return () => {
    unauthorizedListeners.delete(listener);
  };
}

/** End the local session after the backend answered 401. */
export function handleUnauthorized(): void {
  clearAuthToken();

  for (const listener of unauthorizedListeners) {
    listener();
  }
}
