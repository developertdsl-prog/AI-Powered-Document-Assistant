import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  createConversation,
  getConversation,
  listConversations,
  sendMessage,
} from "./conversations";
import type { ChatMessage, ConversationRecord } from "@/types/conversations";
import { clearAuthToken, setAuthToken } from "@/lib/auth";

const fetchMock = vi.fn<typeof fetch>();

const conversation: ConversationRecord = {
  id: "conv-1",
  document_id: "doc-1",
  title: "Refund questions",
  created_at: "2026-10-23T09:42:00Z",
  updated_at: "2026-10-23T09:42:00Z",
};

function chatMessage(role: ChatMessage["role"], position: number): ChatMessage {
  return {
    id: `msg-${position}`,
    conversation_id: conversation.id,
    role,
    content: role === "user" ? "What is the refund policy?" : "Within 14 days.",
    position,
    citations: [],
    created_at: "2026-10-23T09:42:00Z",
  };
}

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

describe("listConversations", () => {
  it("fetches the conversations page with the bearer token", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(200, { items: [conversation], total: 1 }),
    );

    const payload = await listConversations();

    expect(payload.total).toBe(1);
    expect(payload.items[0].id).toBe("conv-1");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/conversations?limit=100",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer token-123",
        }),
      }),
    );
  });

  it("forwards an abort signal", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(200, { items: [], total: 0 }),
    );
    const controller = new AbortController();

    await listConversations(controller.signal);

    const [, init] = fetchMock.mock.calls[0];
    expect(init?.signal).toBe(controller.signal);
  });
});

describe("getConversation", () => {
  it("encodes the conversation id in the path", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(200, {
        ...conversation,
        id: "conv/1",
        messages: [chatMessage("user", 0)],
      }),
    );

    const payload = await getConversation("conv/1");

    expect(payload.messages).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/conversations/conv%2F1",
      expect.anything(),
    );
  });
});

describe("createConversation", () => {
  it("posts only the document id when no title is given", async () => {
    fetchMock.mockResolvedValue(jsonResponse(201, conversation));

    const payload = await createConversation("doc-1");

    expect(payload.id).toBe("conv-1");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/conversations");
    expect(init?.method).toBe("POST");
    expect(init?.headers).toMatchObject({
      "Content-Type": "application/json",
      Authorization: "Bearer token-123",
    });
    expect(JSON.parse(String(init?.body))).toEqual({ document_id: "doc-1" });
  });

  it("includes the title when one is given", async () => {
    fetchMock.mockResolvedValue(jsonResponse(201, conversation));

    await createConversation("doc-1", "Refund questions");

    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse(String(init?.body))).toEqual({
      document_id: "doc-1",
      title: "Refund questions",
    });
  });
});

describe("sendMessage", () => {
  it("posts the question to the conversation's messages", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(200, {
        conversation_id: conversation.id,
        user_message: chatMessage("user", 0),
        assistant_message: chatMessage("assistant", 1),
      }),
    );

    const payload = await sendMessage("conv-1", "What is the refund policy?");

    expect(payload.assistant_message.role).toBe("assistant");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(
      "http://localhost:8000/api/conversations/conv-1/messages",
    );
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual({
      question: "What is the refund policy?",
    });
  });

  it("ends the session when the backend rejects the token", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(401, {
        error: { code: "unauthorized", message: "Token rejected." },
      }),
    );

    await expect(sendMessage("conv-1", "Hello?")).rejects.toMatchObject({
      status: 401,
      code: "unauthorized",
    });
    expect(window.localStorage.getItem("document-assistant-token")).toBeNull();
  });
});
