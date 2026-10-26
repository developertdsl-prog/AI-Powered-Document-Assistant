import { FileText } from "lucide-react";
import { Link } from "react-router-dom";
import { DocumentStatusBadge } from "./DocumentStatusBadge";
import {
  documentTypeLabel,
  formatFileSize,
  formatUploadedAt,
} from "@/lib/files";
import type { DocumentRecord } from "@/types/documents";

function pageLabel(pageCount: number): string {
  return pageCount === 1 ? "1 page" : `${pageCount} pages`;
}

export function DocumentList({ documents }: { documents: DocumentRecord[] }) {
  return (
    <ul aria-label="Uploaded documents" className="flex flex-col gap-3">
      {documents.map((document) => (
        <li
          key={document.id}
          className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-slate-100 p-4 dark:border-slate-800"
        >
          <div className="flex min-w-0 items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              <FileText className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-slate-900 dark:text-slate-100">
                <Link
                  to={`/documents/${document.id}`}
                  className="rounded transition hover:text-sky-700 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:hover:text-sky-300"
                >
                  {document.original_filename}
                </Link>
              </p>
              <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                {documentTypeLabel(document.original_filename)} &middot;{" "}
                {formatFileSize(document.file_size_bytes)} &middot;{" "}
                {formatUploadedAt(document.created_at)}
                {document.page_count
                  ? ` · ${pageLabel(document.page_count)}`
                  : ""}
              </p>
              {document.status === "failed" && document.error_message ? (
                <p
                  role="alert"
                  className="mt-1 text-xs text-rose-600 dark:text-rose-400"
                >
                  {document.error_message}
                </p>
              ) : null}
            </div>
          </div>

          <DocumentStatusBadge status={document.status} />
        </li>
      ))}
    </ul>
  );
}
