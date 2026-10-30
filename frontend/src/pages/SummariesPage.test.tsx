import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SummariesPage from "@/pages/SummariesPage";
import { listDocuments } from "@/services/documents";
import { extractInsights, generateSummary } from "@/services/insights";
import { ApiError } from "@/services/api";
import type { DocumentRecord } from "@/types/documents";
import type {
  ExtractionResponse,
  SummaryResponse,
} from "@/types/insights";

vi.mock("@/services/insights", () => ({
  generateSummary: vi.fn(),
  extractInsights: vi.fn(),
}));

vi.mock("@/services/documents", () => ({
  listDocuments: vi.fn(),
}));

const listDocumentsMock = vi.mocked(listDocuments);
const generateSummaryMock = vi.mocked(generateSummary);
const extractInsightsMock = vi.mocked(extractInsights);

const readyDocument: DocumentRecord = {
  id: "doc-1",
  original_filename: "handbook.pdf",
  content_type: "application/pdf",
  file_size_bytes: 2048,
  checksum: "abc",
  status: "ready",
  page_count: 3,
  error_message: null,
  created_at: "2026-10-28T09:00:00Z",
  updated_at: "2026-10-28T09:00:00Z",
};

const secondDocument: DocumentRecord = {
  ...readyDocument,
  id: "doc-2",
  original_filename: "terms.txt",
};

const pendingDocument: DocumentRecord = {
  ...readyDocument,
  id: "doc-3",
  original_filename: "uploading.pdf",
  status: "processing",
};

const summary: SummaryResponse = {
  document_id: "doc-1",
  length: "concise",
  summary: "Refunds are issued within 14 days of purchase.",
  provider: "extractive",
  source_chunks: 2,
  truncated: true,
  generated_at: "2026-10-29T10:00:00Z",
};

const extraction: ExtractionResponse = {
  document_id: "doc-1",
  key_points: ["Refunds are issued within 14 days of purchase."],
  dates: ["2026-03-03"],
  names: ["Acme Corp"],
  fields: [
    { name: "Invoice number", value: "INV-2024-015", found: true },
    { name: "Due date", value: null, found: false },
  ],
  provider: "extractive",
  source_chunks: 1,
  truncated: false,
  generated_at: "2026-10-29T10:00:00Z",
};

function renderPage() {
  return render(<SummariesPage />);
}

beforeEach(() => {
  vi.clearAllMocks();
  listDocumentsMock.mockResolvedValue({ items: [readyDocument], total: 1 });
});

describe("SummariesPage", () => {
  it("shows an empty state when there are no ready documents", async () => {
    listDocumentsMock.mockResolvedValue({ items: [pendingDocument], total: 1 });

    renderPage();

    expect(await screen.findByText("No ready documents yet")).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("generates a concise summary for the selected document", async () => {
    generateSummaryMock.mockResolvedValue(summary);
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: /generate summary/i }));

    expect(generateSummaryMock).toHaveBeenCalledWith("doc-1", "concise");
    expect(
      await screen.findByText("Refunds are issued within 14 days of purchase."),
    ).toBeInTheDocument();
    expect(screen.getByText(/Generated from 2 passages/)).toBeInTheDocument();
    expect(screen.getByText(/only its first/)).toBeInTheDocument();
  });

  it("asks for a detailed summary when that length is chosen", async () => {
    generateSummaryMock.mockResolvedValue({ ...summary, length: "detailed" });
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Detailed" }));
    await user.click(screen.getByRole("button", { name: /generate summary/i }));

    expect(generateSummaryMock).toHaveBeenCalledWith("doc-1", "detailed");
    expect(
      await screen.findByText("Refunds are issued within 14 days of purchase."),
    ).toBeInTheDocument();
  });

  it("extracts insights and renders every collection", async () => {
    extractInsightsMock.mockResolvedValue(extraction);
    const user = userEvent.setup();
    renderPage();

    await user.type(
      await screen.findByPlaceholderText(
        "Comma separated, e.g. Invoice number, Due date",
      ),
      "Invoice number, Due date",
    );
    await user.click(screen.getByRole("button", { name: /extract insights/i }));

    expect(extractInsightsMock).toHaveBeenCalledWith("doc-1", {
      fields: ["Invoice number", "Due date"],
    });
    expect(
      await screen.findByText("Refunds are issued within 14 days of purchase."),
    ).toBeInTheDocument();
    expect(screen.getByText("2026-03-03")).toBeInTheDocument();
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("INV-2024-015")).toBeInTheDocument();
    expect(screen.getByText("Not found")).toBeInTheDocument();
  });

  it("surfaces backend errors from a failed summary", async () => {
    generateSummaryMock.mockRejectedValue(
      new ApiError("The summary provider is unavailable.", 503),
    );
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: /generate summary/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The summary provider is unavailable.",
    );
  });

  it("clears the results when a different document is chosen", async () => {
    listDocumentsMock.mockResolvedValue({
      items: [readyDocument, secondDocument],
      total: 2,
    });
    generateSummaryMock.mockResolvedValue(summary);
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: /generate summary/i }));
    await screen.findByText("Refunds are issued within 14 days of purchase.");

    await user.selectOptions(screen.getByRole("combobox"), "doc-2");

    await waitFor(() => {
      expect(
        screen.queryByText("Refunds are issued within 14 days of purchase."),
      ).not.toBeInTheDocument();
    });
    expect(
      screen.getByText(/Choose a length and generate a summary/),
    ).toBeInTheDocument();
  });

  it("reports a failed document list instead of an empty page", async () => {
    listDocumentsMock.mockRejectedValue(
      new ApiError("Documents could not be loaded.", 500),
    );

    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Documents could not be loaded.",
    );
  });
});
