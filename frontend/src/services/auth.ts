import { apiBaseUrl } from "@/config/env";
import { authHeaders, setAuthToken } from "@/lib/auth";
import type { RegisterInput, UserRecord } from "@/types/auth";
import { ApiError } from "./api";

interface TokenResponse {
  access_token: string;
  token_type: string;
}

async function jsonError(response: Response): Promise<ApiError> {
  return ApiError.fromResponse(response);
}

/**
 * Create an account. Authentication failures here are the user's input
 * (duplicate email, weak password), so they never end the local session.
 */
export async function registerAccount(
  input: RegisterInput,
): Promise<UserRecord> {
  const response = await fetch(`${apiBaseUrl}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    throw await jsonError(response);
  }

  return (await response.json()) as UserRecord;
}

/** Exchange credentials for a token and return the signed-in account. */
export async function loginAccount(
  email: string,
  password: string,
): Promise<UserRecord> {
  const response = await fetch(`${apiBaseUrl}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    throw await jsonError(response);
  }

  const token = (await response.json()) as TokenResponse;
  setAuthToken(token.access_token);

  return fetchCurrentUser();
}

/** Load the account behind the stored token. */
export async function fetchCurrentUser(
  signal?: AbortSignal,
): Promise<UserRecord> {
  const response = await fetch(`${apiBaseUrl}/api/auth/me`, {
    headers: authHeaders(),
    signal,
  });

  if (!response.ok) {
    throw await jsonError(response);
  }

  return (await response.json()) as UserRecord;
}
