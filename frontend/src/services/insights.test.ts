import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { extractInsights, generateSummary } from "./insights";
import type {
  ExtractionResponse,
  SummaryResponse,
} from "@/types/insights";
import { clearAuthToken, setAuthToken } from "@/lib/auth";

const fetchMock = vi.fn<typeof fetch>();

const summary: SummaryResponse = {
  document_id: "doc-1",
  length: "concise",
  summary: "Refunds are issued within 14 days of purchase.",
  provider: "extractive",
  source_chunks: 3,
  truncated: false,
  generated_at: "2026-10-23T09:42:00Z",
};

const extraction: ExtractionResponse = {
  document_id: "doc-1",
  key_points: ["Refunds are issued within 14 days of purchase."],
  dates: ["2026-03-04"],
  names: ["Ada Lovelace"],
  fields: [{ name: "owner", value: "Ada Lovelace", found: true }],
  provider: "extractive",
  source_chunks: 3,
  truncated: false,
  generated_at: "2026-10-23T09:42:00Z",
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  setAuthToken("token-123");
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  clearAuthToken();
  vi.unstubAllGlobals();
});

describe("generateSummary", () => {
  it("posts the requested length to the summaries endpoint", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, summary));

    const payload = await generateSummary("doc-1", "detailed");

    expect(payload.summary).toBe(summary.summary);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/documents/doc-1/summaries");
    expect(init?.method).toBe("POST");
    expect(init?.headers).toMatchObject({
      "Content-Type": "application/json",
      Authorization: "Bearer token-123",
    });
    expect(JSON.parse(String(init?.body))).toEqual({ length: "detailed" });
  });

  it("forwards an abort signal", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, summary));
    const controller = new AbortController();

    await generateSummary("doc-1", "concise", controller.signal);

    const [, init] = fetchMock.mock.calls[0];
    expect(init?.signal).toBe(controller.signal);
  });
});

describe("extractInsights", () => {
  it("sends fields and converts maxItems to max_items", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, extraction));

    const payload = await extractInsights("doc-1", {
      fields: ["owner", "due date"],
      maxItems: 5,
    });

    expect(payload.fields[0].found).toBe(true);
    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse(String(init?.body))).toEqual({
      fields: ["owner", "due date"],
      max_items: 5,
    });
  });

  it("sends an empty body when no options are given", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, extraction));

    await extractInsights("doc-1");

    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse(String(init?.body))).toEqual({});
  });

  it("skips an empty field list", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, extraction));

    await extractInsights("doc-1", { fields: [] });

    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse(String(init?.body))).toEqual({});
  });

  it("surfaces provider failures as API errors", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(503, {
        error: { code: "service_unavailable", message: "Provider is down." },
      }),
    );

    await expect(extractInsights("doc-1")).rejects.toMatchObject({
      status: 503,
      code: "service_unavailable",
      message: "Provider is down.",
    });
  });
});
