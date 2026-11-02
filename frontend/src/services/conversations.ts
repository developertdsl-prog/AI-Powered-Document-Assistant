import { apiBaseUrl } from "@/config/env";
import { authHeaders } from "@/lib/auth";
import type {
  ConversationDetailResponse,
  ConversationListResponse,
  ConversationRecord,
  MessageExchangeResponse,
} from "@/types/conversations";
import { protectedApiError } from "./api";

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: { ...authHeaders(), ...init.headers },
  });

  if (!response.ok) {
    throw await protectedApiError(response);
  }

  return (await response.json()) as T;
}

export function listConversations(
  signal?: AbortSignal,
): Promise<ConversationListResponse> {
  return request<ConversationListResponse>(
    "/api/conversations?limit=100",
    { signal },
  );
}

export function getConversation(
  conversationId: string,
  signal?: AbortSignal,
): Promise<ConversationDetailResponse> {
  return request<ConversationDetailResponse>(
    `/api/conversations/${encodeURIComponent(conversationId)}`,
    { signal },
  );
}

export function createConversation(
  documentId: string,
  title?: string,
): Promise<ConversationRecord> {
  return request<ConversationRecord>("/api/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(
      title ? { document_id: documentId, title } : { document_id: documentId },
    ),
  });
}

export function sendMessage(
  conversationId: string,
  question: string,
  signal?: AbortSignal,
): Promise<MessageExchangeResponse> {
  return request<MessageExchangeResponse>(
    `/api/conversations/${encodeURIComponent(conversationId)}/messages`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
      signal,
    },
  );
}
