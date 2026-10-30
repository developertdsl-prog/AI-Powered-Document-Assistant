export type SummaryLength = "concise" | "detailed";

export interface SummaryResponse {
  document_id: string;
  length: SummaryLength;
  summary: string;
  provider: string;
  source_chunks: number;
  truncated: boolean;
  generated_at: string;
}

export interface ExtractedField {
  name: string;
  value: string | null;
  found: boolean;
}

export interface ExtractionResponse {
  document_id: string;
  key_points: string[];
  dates: string[];
  names: string[];
  fields: ExtractedField[];
  provider: string;
  source_chunks: number;
  truncated: boolean;
  generated_at: string;
}

export interface ExtractionOptions {
  fields?: string[];
  maxItems?: number;
}
