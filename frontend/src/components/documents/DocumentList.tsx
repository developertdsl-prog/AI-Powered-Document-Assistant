import { useState } from "react";
import { FileText, Trash2 } from "lucide-react";
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

function DeleteButton({
  document,
  busy,
  onDelete,
}: {
  document: DocumentRecord;
  busy: boolean;
  onDelete: (document: DocumentRecord) => void;
}) {
  const [confirming, setConfirming] = useState(false);

  if (confirming) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-slate-500 dark:text-slate-400">
          Delete &ldquo;{document.original_filename}&rdquo;?
        </span>
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            setConfirming(false);
            onDelete(document);
          }}
          className="rounded-md bg-rose-600 px-2.5 py-1 text-xs font-semibold text-white transition hover:bg-rose-500 disabled:opacity-60"
        >
          {busy ? "Deleting\u2026" : "Confirm delete"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => setConfirming(false)}
          className="rounded-md px-2.5 py-1 text-xs font-semibold text-slate-600 transition hover:bg-slate-100 disabled:opacity-60 dark:text-slate-400 dark:hover:bg-slate-800"
        >
          Cancel
        </button>
      </div>
    );
  }

  return (
    <button
      type="button"
      disabled={busy}
      onClick={() => setConfirming(true)}
      aria-label={`Delete ${document.original_filename}`}
      className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold text-rose-600 transition hover:bg-rose-50 hover:text-rose-700 disabled:opacity-60 dark:text-rose-400 dark:hover:bg-rose-500/10 dark:hover:text-rose-300"
    >
      <Trash2 className="h-3.5 w-3.5" />
      {busy ? "Deleting\u2026" : "Delete"}
    </button>
  );
}

export interface DocumentListProps {
  documents: DocumentRecord[];
  /** When set, each row gets a delete button; deletion is confirmed inline. */
  onDelete?: (document: DocumentRecord) => void;
  /** Id of the document whose deletion is in flight, if any. */
  deletingId?: string | null;
}

export function DocumentList({
  documents,
  onDelete,
  deletingId,
}: DocumentListProps) {
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

          <div className="flex flex-wrap items-center gap-3">
            {onDelete ? (
              <DeleteButton
                document={document}
                busy={deletingId === document.id}
                onDelete={onDelete}
              />
            ) : null}
            <DocumentStatusBadge status={document.status} />
          </div>
        </li>
      ))}
    </ul>
  );
}
