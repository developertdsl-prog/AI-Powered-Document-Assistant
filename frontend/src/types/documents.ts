export type DocumentStatus = "pending" | "processing" | "ready" | "failed";

export interface DocumentRecord {
  id: string;
  original_filename: string;
  content_type: string;
  file_size_bytes: number;
  checksum: string | null;
  status: DocumentStatus;
  page_count: number | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  items: DocumentRecord[];
  total: number;
}

export interface DocumentPage {
  page_number: number;
  content: string;
  character_count: number;
  metadata: Record<string, unknown> | null;
}

export interface DocumentTextResponse {
  document_id: string;
  status: DocumentStatus;
  page_count: number | null;
  metadata: Record<string, unknown> | null;
  pages: DocumentPage[];
}
