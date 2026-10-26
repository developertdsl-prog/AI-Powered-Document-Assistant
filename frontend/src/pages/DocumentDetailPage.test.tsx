import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import DocumentDetailPage from "@/pages/DocumentDetailPage";
import { getDocument, getDocumentText } from "@/services/documents";
import { ApiError } from "@/services/api";
import type { DocumentRecord } from "@/types/documents";

vi.mock("@/services/documents", () => ({
  getDocument: vi.fn(),
  getDocumentText: vi.fn(),
}));

const getDocumentMock = vi.mocked(getDocument);
const getDocumentTextMock = vi.mocked(getDocumentText);

const readyDocument: DocumentRecord = {
  id: "doc-1",
  original_filename: "report.pdf",
  content_type: "application/pdf",
  file_size_bytes: 2.4 * 1024 * 1024,
  checksum: "abc",
  status: "ready",
  page_count: 2,
  error_message: null,
  created_at: "2026-10-23T09:42:00Z",
  updated_at: "2026-10-23T09:43:00Z",
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/documents/doc-1"]}>
      <Routes>
        <Route
          path="/documents/:documentId"
          element={<DocumentDetailPage />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  getDocumentMock.mockReset();
  getDocumentTextMock.mockReset();
});

describe("DocumentDetailPage", () => {
  it("shows extracted pages and metadata for a ready document", async () => {
    getDocumentMock.mockResolvedValue(readyDocument);
    getDocumentTextMock.mockResolvedValue({
      document_id: "doc-1",
      status: "ready",
      page_count: 2,
      metadata: {
        format: "pdf",
        encoding: null,
        page_count: 2,
      },
      pages: [
        {
          page_number: 1,
          content: "Alpha page text",
          character_count: 15,
          metadata: { width: 612 },
        },
        {
          page_number: 2,
          content: "Beta page text",
          character_count: 14,
          metadata: { width: 612 },
        },
      ],
    });

    renderPage();

    expect(
      await screen.findByRole("heading", { name: "report.pdf" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getByText("Extracted text")).toBeInTheDocument();
    expect(screen.getByText("Alpha page text")).toBeInTheDocument();
    expect(screen.getByText("Beta page text")).toBeInTheDocument();
    expect(screen.getByLabelText("Page 1")).toBeInTheDocument();
    expect(screen.getByText("2.4 MB")).toBeInTheDocument();
  });

  it("shows a processing state without requesting text", async () => {
    getDocumentMock.mockResolvedValue({
      ...readyDocument,
      status: "processing",
      page_count: null,
    });

    renderPage();

    expect(await screen.findByText("Processing")).toBeInTheDocument();
    expect(
      screen.getByText(/text extraction is running/i),
    ).toBeInTheDocument();
    expect(getDocumentTextMock).not.toHaveBeenCalled();
  });

  it("shows the stored failure message", async () => {
    getDocumentMock.mockResolvedValue({
      ...readyDocument,
      status: "failed",
      page_count: null,
      error_message: "The PDF could not be read. The file may be corrupt.",
    });

    renderPage();

    expect(
      await screen.findByText(/processing failed/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/the pdf could not be read/i),
    ).toBeInTheDocument();
    expect(getDocumentTextMock).not.toHaveBeenCalled();
  });

  it("shows a not-found state when the document is missing", async () => {
    getDocumentMock.mockRejectedValue(
      new ApiError("Document not found.", 404, "not_found"),
    );

    renderPage();

    expect(
      await screen.findByRole("heading", { name: /document not found/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });
});
