import { apiBaseUrl } from "@/config/env";
import type {
  ExtractionOptions,
  ExtractionResponse,
  SummaryLength,
  SummaryResponse,
} from "@/types/insights";
import { ApiError } from "./api";

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, init);

  if (!response.ok) {
    throw await ApiError.fromResponse(response);
  }

  return (await response.json()) as T;
}

export function generateSummary(
  documentId: string,
  length: SummaryLength,
  signal?: AbortSignal,
): Promise<SummaryResponse> {
  return request<SummaryResponse>(
    `/api/documents/${encodeURIComponent(documentId)}/summaries`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ length }),
      signal,
    },
  );
}

export function extractInsights(
  documentId: string,
  options: ExtractionOptions = {},
  signal?: AbortSignal,
): Promise<ExtractionResponse> {
  const body: Record<string, unknown> = {};

  if (options.fields && options.fields.length > 0) {
    body.fields = options.fields;
  }
  if (options.maxItems !== undefined) {
    body.max_items = options.maxItems;
  }

  return request<ExtractionResponse>(
    `/api/documents/${encodeURIComponent(documentId)}/extractions`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    },
  );
}
