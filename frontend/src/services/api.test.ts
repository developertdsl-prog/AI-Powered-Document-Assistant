import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, isAbortError, protectedApiError } from "./api";
import { clearAuthToken, onUnauthorized, setAuthToken } from "@/lib/auth";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  clearAuthToken();
  vi.unstubAllGlobals();
});

describe("ApiError.fromResponse", () => {
  it("reads the error envelope from the backend", async () => {
    const error = await ApiError.fromResponse(
      jsonResponse(409, {
        error: {
          code: "document_not_ready",
          message: "The document is still processing.",
        },
      }),
    );

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(409);
    expect(error.code).toBe("document_not_ready");
    expect(error.message).toBe("The document is still processing.");
  });

  it("falls back to a generic message when the body is not JSON", async () => {
    const error = await ApiError.fromResponse(
      new Response("boom", { status: 500 }),
    );

    expect(error.status).toBe(500);
    expect(error.code).toBe("request_failed");
    expect(error.message).toBe("Request failed with HTTP 500.");
  });

  it("falls back when the envelope carries no message", async () => {
    const error = await ApiError.fromResponse(jsonResponse(502, {}));

    expect(error.status).toBe(502);
    expect(error.code).toBe("request_failed");
    expect(error.message).toBe("Request failed with HTTP 502.");
  });
});

describe("protectedApiError", () => {
  it("ends the local session when the backend answers 401", async () => {
    setAuthToken("expired-token");
    const listener = vi.fn();
    const unsubscribe = onUnauthorized(listener);

    const error = await protectedApiError(
      jsonResponse(401, {
        error: { code: "unauthorized", message: "Token rejected." },
      }),
    );

    expect(error.code).toBe("unauthorized");
    expect(window.localStorage.getItem("document-assistant-token")).toBeNull();
    expect(listener).toHaveBeenCalledTimes(1);
    unsubscribe();
  });

  it("keeps the session for failures that are not 401", async () => {
    setAuthToken("valid-token");

    const error = await protectedApiError(
      jsonResponse(503, {
        error: { code: "service_unavailable", message: "Provider down." },
      }),
    );

    expect(error.status).toBe(503);
    expect(window.localStorage.getItem("document-assistant-token")).toBe(
      "valid-token",
    );
  });
});

describe("isAbortError", () => {
  it("recognises aborts and ignores other failures", () => {
    expect(isAbortError(new DOMException("stopped", "AbortError"))).toBe(true);
    expect(isAbortError(new TypeError("network down"))).toBe(false);
    expect(isAbortError("AbortError")).toBe(false);
  });
});
