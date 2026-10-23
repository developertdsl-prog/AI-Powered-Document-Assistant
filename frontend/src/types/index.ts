export interface DocumentSummary {
  id: string;
  title: string;
  type: "PDF" | "DOCX" | "TXT";
  sizeLabel: string;
  uploadedAt: string;
  status: "processing" | "ready" | "error";
  pages: number | null;
}

export interface ConversationSummary {
  id: string;
  documentId: string | null;
  title: string;
  lastActivityAt: string;
  messageCount: number;
}

export interface StatCard {
  label: string;
  value: string;
  hint: string;
}
