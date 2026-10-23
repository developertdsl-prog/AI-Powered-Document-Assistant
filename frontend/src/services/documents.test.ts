import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { uploadDocument } from "./documents";
import type { DocumentRecord } from "@/types/documents";

const record: DocumentRecord = {
  id: "doc-1",
  original_filename: "report.pdf",
  content_type: "application/pdf",
  file_size_bytes: 8,
  checksum: "abc",
  status: "pending",
  page_count: null,
  error_message: null,
  created_at: "2026-10-23T09:42:00Z",
  updated_at: "2026-10-23T09:42:00Z",
};

class FakeXMLHttpRequest {
  static instances: FakeXMLHttpRequest[] = [];

  upload: { onprogress: ((event: ProgressEvent) => void) | null } = {
    onprogress: null,
  };
  status = 0;
  responseText = "";
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;
  open = vi.fn();
  send = vi.fn();

  constructor() {
    FakeXMLHttpRequest.instances.push(this);
  }

  abort() {
    this.onabort?.();
  }
}

function pdfFile(): File {
  return new File(["%PDF-1.4"], "report.pdf", {
    type: "application/pdf",
  });
}

beforeEach(() => {
  FakeXMLHttpRequest.instances = [];
  vi.stubGlobal("XMLHttpRequest", FakeXMLHttpRequest);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("uploadDocument", () => {
  it("posts multipart data and reports progress", async () => {
    const onProgress = vi.fn();
    const promise = uploadDocument(pdfFile(), { onProgress });
    const xhr = FakeXMLHttpRequest.instances[0];

    expect(xhr.open).toHaveBeenCalledWith(
      "POST",
      expect.stringContaining("/api/documents"),
    );
    expect(xhr.send).toHaveBeenCalledWith(expect.any(FormData));
    expect(onProgress).toHaveBeenCalledWith(0);

    xhr.upload.onprogress?.({
      lengthComputable: true,
      loaded: 42,
      total: 100,
    } as ProgressEvent);
    expect(onProgress).toHaveBeenCalledWith(42);

    xhr.status = 201;
    xhr.responseText = JSON.stringify(record);
    xhr.onload?.();

    await expect(promise).resolves.toMatchObject({ id: "doc-1" });
  });

  it("rejects with the API error envelope", async () => {
    const promise = uploadDocument(pdfFile());
    const xhr = FakeXMLHttpRequest.instances[0];

    xhr.status = 415;
    xhr.responseText = JSON.stringify({
      error: {
        code: "unsupported_media_type",
        message: "The file is not a valid PDF.",
      },
    });
    xhr.onload?.();

    await expect(promise).rejects.toMatchObject({
      status: 415,
      code: "unsupported_media_type",
      message: "The file is not a valid PDF.",
    });
  });

  it("can be cancelled with an AbortSignal", async () => {
    const controller = new AbortController();
    const promise = uploadDocument(pdfFile(), {
      signal: controller.signal,
    });

    controller.abort();

    await expect(promise).rejects.toMatchObject({ name: "AbortError" });
  });
});
