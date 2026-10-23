import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import DocumentsPage from "@/pages/DocumentsPage";
import { listDocuments, uploadDocument } from "@/services/documents";
import { ApiError } from "@/services/api";
import type { DocumentRecord } from "@/types/documents";

vi.mock("@/services/documents", () => ({
  listDocuments: vi.fn(),
  uploadDocument: vi.fn(),
}));

const listDocumentsMock = vi.mocked(listDocuments);
const uploadDocumentMock = vi.mocked(uploadDocument);

const readyDocument: DocumentRecord = {
  id: "doc-1",
  original_filename: "notes.txt",
  content_type: "text/plain",
  file_size_bytes: 18 * 1024,
  checksum: "abc",
  status: "ready",
  page_count: 1,
  error_message: null,
  created_at: "2026-10-23T09:42:00Z",
  updated_at: "2026-10-23T09:42:00Z",
};

function renderPage() {
  return render(
    <MemoryRouter>
      <DocumentsPage />
    </MemoryRouter>,
  );
}

function pdfFile(): File {
  return new File(["%PDF-1.4"], "report.pdf", {
    type: "application/pdf",
  });
}

beforeEach(() => {
  listDocumentsMock.mockReset();
  uploadDocumentMock.mockReset();
});

describe("DocumentsPage", () => {
  it("lists uploaded documents with metadata and status", async () => {
    listDocumentsMock.mockResolvedValue({
      items: [readyDocument],
      total: 1,
    });

    renderPage();

    expect(await screen.findByText("notes.txt")).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getByText(/18 KB/)).toBeInTheDocument();
    expect(screen.getByText(/1 page/)).toBeInTheDocument();
  });

  it("shows an empty state when there are no documents", async () => {
    listDocumentsMock.mockResolvedValue({ items: [], total: 0 });

    renderPage();

    expect(
      await screen.findByText(/no documents yet/i),
    ).toBeInTheDocument();
  });

  it("uploads a selected PDF and refreshes the list", async () => {
    const user = userEvent.setup();
    listDocumentsMock.mockResolvedValue({ items: [], total: 0 });
    uploadDocumentMock.mockImplementation(async (_file, options) => {
      options?.onProgress?.(60);
      return readyDocument;
    });

    renderPage();

    await waitFor(() => expect(listDocumentsMock).toHaveBeenCalledTimes(1));

    await user.upload(
      screen.getByLabelText(/choose document file/i),
      pdfFile(),
    );

    expect(uploadDocumentMock).toHaveBeenCalledTimes(1);
    expect(
      await screen.findByText(/uploaded\. Processing will start automatically/i),
    ).toBeInTheDocument();
    await waitFor(() => expect(listDocumentsMock).toHaveBeenCalledTimes(2));
  });

  it("rejects unsupported files before uploading", async () => {
    listDocumentsMock.mockResolvedValue({ items: [], total: 0 });
    renderPage();

    await waitFor(() => expect(listDocumentsMock).toHaveBeenCalledTimes(1));

    fireEvent.drop(screen.getByTestId("upload-dropzone"), {
      dataTransfer: {
        files: [
          new File(["image"], "photo.png", { type: "image/png" }),
        ],
      },
    });

    expect(
      await screen.findByText(/unsupported format/i),
    ).toBeInTheDocument();
    expect(uploadDocumentMock).not.toHaveBeenCalled();
  });

  it("shows the backend error when an upload fails", async () => {
    const user = userEvent.setup();
    listDocumentsMock.mockResolvedValue({ items: [], total: 0 });
    uploadDocumentMock.mockRejectedValue(
      new ApiError("The uploaded file is not a valid PDF.", 415),
    );

    renderPage();

    await waitFor(() => expect(listDocumentsMock).toHaveBeenCalledTimes(1));

    await user.upload(
      screen.getByLabelText(/choose document file/i),
      pdfFile(),
    );

    expect(
      await screen.findByText(/not a valid PDF/i),
    ).toBeInTheDocument();
  });

  it("recovers from a list failure with retry", async () => {
    const user = userEvent.setup();
    listDocumentsMock
      .mockRejectedValueOnce(new Error("Backend offline"))
      .mockResolvedValueOnce({ items: [], total: 0 });

    renderPage();

    expect(
      await screen.findByText(/couldn't load documents/i),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /try again/i }));

    expect(
      await screen.findByText(/no documents yet/i),
    ).toBeInTheDocument();
  });
});
