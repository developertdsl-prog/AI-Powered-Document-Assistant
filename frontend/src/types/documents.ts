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
