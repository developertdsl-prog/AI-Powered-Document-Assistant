import type { DocumentStatus } from "@/types/documents";

const statusStyles: Record<DocumentStatus, string> = {
  pending:
    "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  processing:
    "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  ready:
    "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
  failed: "bg-rose-100 text-rose-800 dark:bg-rose-500/15 dark:text-rose-300",
};

const statusLabels: Record<DocumentStatus, string> = {
  pending: "Pending",
  processing: "Processing",
  ready: "Ready",
  failed: "Failed",
};

export function DocumentStatusBadge({ status }: { status: DocumentStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${statusStyles[status]}`}
    >
      {statusLabels[status]}
    </span>
  );
}
