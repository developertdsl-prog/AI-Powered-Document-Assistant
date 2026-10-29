export interface AnswerCitation {
  reference: number;
  chunk_id: string;
  chunk_index: number;
  page_number: number | null;
  score: number;
  excerpt: string;
}

export interface ConversationRecord {
  id: string;
  document_id: string | null;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationListResponse {
  items: ConversationRecord[];
  total: number;
}

export type MessageRole = "user" | "assistant" | "system";

export interface ChatMessage {
  id: string;
  conversation_id: string;
  role: MessageRole;
  content: string;
  position: number;
  citations: AnswerCitation[];
  created_at: string;
}

export interface ConversationDetailResponse extends ConversationRecord {
  messages: ChatMessage[];
}

export interface MessageExchangeResponse {
  conversation_id: string;
  user_message: ChatMessage;
  assistant_message: ChatMessage;
}
