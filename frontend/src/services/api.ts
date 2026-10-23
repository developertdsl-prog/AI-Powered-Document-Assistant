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

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}
