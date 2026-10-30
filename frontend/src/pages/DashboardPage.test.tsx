import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import DashboardPage from "@/pages/DashboardPage";
import { listDocuments } from "@/services/documents";
import { listConversations } from "@/services/conversations";
import { ApiError } from "@/services/api";
import type { DocumentRecord } from "@/types/documents";
import type { ConversationRecord } from "@/types/conversations";

vi.mock("@/services/documents", () => ({
  listDocuments: vi.fn(),
  uploadDocument: vi.fn(),
  deleteDocument: vi.fn(),
}));

vi.mock("@/services/conversations", () => ({
  listConversations: vi.fn(),
}));

vi.mock("@/components/HealthStatusCard", () => ({
  HealthStatusCard: () => <div>System status placeholder</div>,
}));

const listDocumentsMock = vi.mocked(listDocuments);
const listConversationsMock = vi.mocked(listConversations);

const readyDocument: DocumentRecord = {
  id: "doc-1",
  original_filename: "handbook.pdf",
  content_type: "application/pdf",
  file_size_bytes: 2_516_582,
  checksum: "abc",
  status: "ready",
  page_count: 24,
  error_message: null,
  created_at: "2026-10-23T09:42:00Z",
  updated_at: "2026-10-23T09:42:00Z",
};

const processingDocument: DocumentRecord = {
  id: "doc-2",
  original_filename: "Meeting notes.txt",
  content_type: "text/plain",
  file_size_bytes: 18 * 1024,
  checksum: "def",
  status: "processing",
  page_count: null,
  error_message: null,
  created_at: "2026-10-23T10:00:00Z",
  updated_at: "2026-10-23T10:00:00Z",
};

const conversation: ConversationRecord = {
  id: "conv-1",
  document_id: "doc-1",
  title: "Q4 revenue breakdown",
  created_at: "2026-10-23T09:40:00Z",
  updated_at: "2026-10-23T09:42:00Z",
};

function renderPage() {
  return render(
    <MemoryRouter>
      <DashboardPage />
      <LocationProbe />
    </MemoryRouter>,
  );
}

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname}</div>;
}

beforeEach(() => {
  listDocumentsMock.mockReset();
  listConversationsMock.mockReset();
  listDocumentsMock.mockResolvedValue({ items: [], total: 0 });
  listConversationsMock.mockResolvedValue({ items: [], total: 0 });
});

describe("DashboardPage", () => {
  it("renders live document and conversation records", async () => {
    listDocumentsMock.mockResolvedValue({
      items: [readyDocument, processingDocument],
      total: 2,
    });
    listConversationsMock.mockResolvedValue({
      items: [conversation],
      total: 1,
    });

    renderPage();

    expect(await screen.findByText("handbook.pdf")).toBeInTheDocument();
    expect(screen.getByText("Meeting notes.txt")).toBeInTheDocument();
    expect(screen.getByText(/24 pages/)).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getByText("Processing")).toBeInTheDocument();

    expect(screen.getByText("1 ready · 1 processing")).toBeInTheDocument();
    expect(screen.getByText("Q4 revenue breakdown")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /resume/i })).toBeInTheDocument();
  });

  it("shows empty states before anything was uploaded", async () => {
    renderPage();

    expect(await screen.findByText(/no documents yet/i)).toBeInTheDocument();
    expect(
      await screen.findByText(/no conversations yet/i),
    ).toBeInTheDocument();
    expect(screen.getByText("No processing errors")).toBeInTheDocument();
  });

  it("recovers from a load failure with retry", async () => {
    const user = userEvent.setup();
    listDocumentsMock
      .mockRejectedValueOnce(new ApiError("Backend offline", 503))
      .mockResolvedValue({ items: [], total: 0 });

    renderPage();

    expect(
      await screen.findByText(/couldn't load the dashboard/i),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /try again/i }));

    expect(await screen.findByText(/no documents yet/i)).toBeInTheDocument();
  });

  it("navigates to the document library from the upload button", async () => {
    const user = userEvent.setup();

    renderPage();
    expect(
      await screen.findByRole("heading", { level: 1, name: "Dashboard" }),
    ).toBeInTheDocument();

    await user.click(screen.getAllByRole("button", { name: /upload document/i })[0]);

    expect(screen.getByTestId("location")).toHaveTextContent("/documents");
  });
});
