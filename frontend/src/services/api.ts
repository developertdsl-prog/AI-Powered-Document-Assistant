import { handleUnauthorized } from "@/lib/auth";

interface ErrorEnvelope {
  error?: {
    code?: string;
    message?: string;
  };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(message: string, status: number, code = "request_failed") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }

  static async fromResponse(response: Response): Promise<ApiError> {
    let payload: ErrorEnvelope | null;

    try {
      payload = (await response.json()) as ErrorEnvelope;
    } catch {
      payload = null;
    }

    return new ApiError(
      payload?.error?.message ?? `Request failed with HTTP ${response.status}.`,
      response.status,
      payload?.error?.code ?? "request_failed",
    );
  }
}

/**
 * Build the error for a failed protected request.
 *
 * A 401 means the stored token was rejected (expired, revoked, or forged),
 * so the local session is ended and the auth guard can redirect to login.
 * Authentication endpoints build their errors with {@link ApiError}
 * directly, because a failed login must not look like an expired session.
 */
export async function protectedApiError(response: Response): Promise<ApiError> {
  const error = await ApiError.fromResponse(response);

  if (error.status === 401) {
    handleUnauthorized();
  }

  return error;
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}
