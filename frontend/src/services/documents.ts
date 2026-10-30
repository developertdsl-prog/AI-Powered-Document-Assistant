import { apiBaseUrl } from "@/config/env";
import type {
  DocumentListResponse,
  DocumentRecord,
  DocumentTextResponse,
} from "@/types/documents";
import { ApiError } from "./api";

interface ErrorEnvelope {
  error?: {
    code?: string;
    message?: string;
  };
}

export interface UploadOptions {
  onProgress?: (percent: number) => void;
  signal?: AbortSignal;
}

function parseJson(text: string): unknown {
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

function errorFromPayload(status: number, payload: unknown): ApiError {
  const envelope = payload as ErrorEnvelope | null;

  return new ApiError(
    envelope?.error?.message ?? `Upload failed with HTTP ${status}.`,
    status,
    envelope?.error?.code ?? "request_failed",
  );
}

/**
 * Upload a document with progress reporting.
 *
 * `fetch` cannot report request upload progress in all browsers, so uploads use
 * XMLHttpRequest. Listing uses `fetch` below.
 */
export function uploadDocument(
  file: File,
  options: UploadOptions = {},
): Promise<DocumentRecord> {
  return new Promise((resolve, reject) => {
    if (options.signal?.aborted) {
      reject(new DOMException("Upload cancelled.", "AbortError"));
      return;
    }

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${apiBaseUrl}/api/documents`);
    xhr.responseType = "text";

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) {
        options.onProgress?.(
          Math.min(100, Math.round((event.loaded / event.total) * 100)),
        );
      }
    };

    xhr.onload = () => {
      const payload = parseJson(xhr.responseText);

      if (xhr.status >= 200 && xhr.status < 300 && payload) {
        resolve(payload as DocumentRecord);
        return;
      }

      reject(errorFromPayload(xhr.status, payload));
    };

    xhr.onerror = () => {
      reject(
        new ApiError(
          "Unable to reach the server. Check that the backend is running.",
          0,
          "network_error",
        ),
      );
    };

    xhr.onabort = () => {
      reject(new DOMException("Upload cancelled.", "AbortError"));
    };

    options.signal?.addEventListener("abort", () => xhr.abort(), {
      once: true,
    });

    const formData = new FormData();
    formData.append("file", file);
    options.onProgress?.(0);
    xhr.send(formData);
  });
}

export interface ListDocumentsOptions {
  /** Case-insensitive substring the filename must contain. */
  query?: string;
}

export async function listDocuments(
  signal?: AbortSignal,
  options: ListDocumentsOptions = {},
): Promise<DocumentListResponse> {
  const params = new URLSearchParams({ limit: "100" });
  const query = options.query?.trim();

  if (query) {
    params.set("q", query);
  }

  const response = await fetch(`${apiBaseUrl}/api/documents?${params}`, {
    signal,
  });

  if (!response.ok) {
    throw await ApiError.fromResponse(response);
  }

  return (await response.json()) as DocumentListResponse;
}

export async function deleteDocument(
  documentId: string,
  signal?: AbortSignal,
): Promise<{ message: string }> {
  const response = await fetch(
    `${apiBaseUrl}/api/documents/${encodeURIComponent(documentId)}`,
    { method: "DELETE", signal },
  );

  if (!response.ok) {
    throw await ApiError.fromResponse(response);
  }

  return (await response.json()) as { message: string };
}

export async function getDocument(
  documentId: string,
  signal?: AbortSignal,
): Promise<DocumentRecord> {
  const response = await fetch(
    `${apiBaseUrl}/api/documents/${encodeURIComponent(documentId)}`,
    { signal },
  );

  if (!response.ok) {
    throw await ApiError.fromResponse(response);
  }

  return (await response.json()) as DocumentRecord;
}

export async function getDocumentText(
  documentId: string,
  signal?: AbortSignal,
): Promise<DocumentTextResponse> {
  const response = await fetch(
    `${apiBaseUrl}/api/documents/${encodeURIComponent(documentId)}/text`,
    { signal },
  );

  if (!response.ok) {
    throw await ApiError.fromResponse(response);
  }

  return (await response.json()) as DocumentTextResponse;
}
