import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import ChatPage from "@/pages/ChatPage";
import {
  createConversation,
  getConversation,
  listConversations,
  sendMessage,
} from "@/services/conversations";
import { listDocuments } from "@/services/documents";
import { ApiError } from "@/services/api";
import type { DocumentRecord } from "@/types/documents";
import type {
  ChatMessage,
  ConversationRecord,
} from "@/types/conversations";

vi.mock("@/services/conversations", () => ({
  listConversations: vi.fn(),
  getConversation: vi.fn(),
  createConversation: vi.fn(),
  sendMessage: vi.fn(),
}));

vi.mock("@/services/documents", () => ({
  listDocuments: vi.fn(),
}));

const listConversationsMock = vi.mocked(listConversations);
const getConversationMock = vi.mocked(getConversation);
const createConversationMock = vi.mocked(createConversation);
const sendMessageMock = vi.mocked(sendMessage);
const listDocumentsMock = vi.mocked(listDocuments);

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

const conversation: ConversationRecord = {
  id: "conv-1",
  document_id: "doc-1",
  title: "Refund policy",
  created_at: "2026-10-28T10:00:00Z",
  updated_at: "2026-10-28T10:05:00Z",
};

function buildMessage(overrides: Partial<ChatMessage>): ChatMessage {
  return {
    id: "msg-1",
    conversation_id: "conv-1",
    role: "user",
    content: "What is the refund policy?",
    position: 1,
    citations: [],
    created_at: "2026-10-28T10:00:00Z",
    ...overrides,
  };
}

const assistantMessage = buildMessage({
  id: "msg-2",
  role: "assistant",
  content: "Refunds are issued within 14 days of purchase.",
  position: 2,
  citations: [
    {
      reference: 1,
      chunk_id: "chunk-1",
      chunk_index: 0,
      page_number: 2,
      score: 0.42,
      excerpt: "Refunds are issued within 14 days of purchase, minus…",
    },
  ],
});

function renderPage() {
  return render(
    <MemoryRouter>
      <ChatPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  listConversationsMock.mockResolvedValue({ items: [], total: 0 });
  listDocumentsMock.mockResolvedValue({ items: [readyDocument], total: 1 });
});

describe("ChatPage", () => {
  it("shows an empty state before a conversation is picked", async () => {
    renderPage();

    expect(
      await screen.findByText("Pick a conversation"),
    ).toBeInTheDocument();
  });

  it("lists conversations and opens one with its history", async () => {
    listConversationsMock.mockResolvedValue({
      items: [conversation],
      total: 1,
    });
    getConversationMock.mockResolvedValue({
      ...conversation,
      messages: [
        buildMessage({ content: "What is the refund policy?" }),
        assistantMessage,
      ],
    });
    renderPage();

    fireEvent.click(await screen.findByText("Refund policy"));

    expect(getConversationMock).toHaveBeenCalledWith("conv-1");
    expect(
      await screen.findByText("Refunds are issued within 14 days of purchase."),
    ).toBeInTheDocument();
    expect(screen.getByText("Page 2")).toBeInTheDocument();
  });

  it("starts a new conversation for a chosen document", async () => {
    createConversationMock.mockResolvedValue(conversation);
    const user = userEvent.setup();
    renderPage();

    await user.click(
      await screen.findByRole("button", { name: /new conversation/i }),
    );
    await user.selectOptions(
      await screen.findByRole("combobox"),
      "doc-1",
    );
    await user.click(
      screen.getByRole("button", { name: /start chatting/i }),
    );

    await waitFor(() => {
      expect(createConversationMock).toHaveBeenCalledWith("doc-1");
    });
    expect(
      await screen.findByText("Ask your first question about this document."),
    ).toBeInTheDocument();
  });

  it("sends a question and appends the cited answer", async () => {
    listConversationsMock.mockResolvedValue({
      items: [conversation],
      total: 1,
    });
    getConversationMock.mockResolvedValue({ ...conversation, messages: [] });
    sendMessageMock.mockResolvedValue({
      conversation_id: "conv-1",
      user_message: buildMessage({ content: "What is the refund policy?" }),
      assistant_message: assistantMessage,
    });
    const user = userEvent.setup();
    renderPage();

    fireEvent.click(await screen.findByText("Refund policy"));
    const input = await screen.findByPlaceholderText(
      "Ask a question about this document…",
    );
    await user.type(input, "What is the refund policy?");
    await user.click(screen.getByRole("button", { name: /send/i }));

    expect(sendMessageMock).toHaveBeenCalledWith(
      "conv-1",
      "What is the refund policy?",
    );
    expect(
      await screen.findByText("Refunds are issued within 14 days of purchase."),
    ).toBeInTheDocument();
    expect(screen.getByText("[1]")).toBeInTheDocument();
    expect(screen.getByText("Page 2")).toBeInTheDocument();
  });

  it("surfaces backend errors from a failed question", async () => {
    listConversationsMock.mockResolvedValue({
      items: [conversation],
      total: 1,
    });
    getConversationMock.mockResolvedValue({ ...conversation, messages: [] });
    sendMessageMock.mockRejectedValue(
      new ApiError("The answer provider is unavailable.", 503),
    );
    const user = userEvent.setup();
    renderPage();

    fireEvent.click(await screen.findByText("Refund policy"));
    const input = await screen.findByPlaceholderText(
      "Ask a question about this document…",
    );
    await user.type(input, "What is the refund policy?");
    await user.click(screen.getByRole("button", { name: /send/i }));

    expect(
      await screen.findByRole("alert"),
    ).toHaveTextContent("The answer provider is unavailable.");
  });
});
