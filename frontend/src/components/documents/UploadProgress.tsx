import { Button } from "@/components/ui";

interface UploadProgressProps {
  file: File;
  percent: number;
  onCancel: () => void;
}

export function UploadProgress({
  file,
  percent,
  onCancel,
}: UploadProgressProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="rounded-xl border border-sky-200 bg-sky-50 p-4 dark:border-sky-500/40 dark:bg-sky-500/10"
    >
      <div className="flex items-center justify-between gap-3">
        <p className="truncate text-sm font-medium text-slate-900 dark:text-slate-100">
          {file.name}
        </p>
        <span className="text-xs font-semibold text-sky-700 dark:text-sky-300">
          {percent}%
        </span>
      </div>

      <div
        role="progressbar"
        aria-label={`Uploading ${file.name}`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        className="mt-3 h-2 overflow-hidden rounded-full bg-sky-100 dark:bg-slate-800"
      >
        <div
          className="h-full rounded-full bg-sky-500 transition-all duration-300 dark:bg-sky-400"
          style={{ width: `${percent}%` }}
        />
      </div>

      <div className="mt-3 flex items-center justify-between gap-3">
        <span className="text-xs text-slate-600 dark:text-slate-400">
          Uploading&hellip;
        </span>
        <Button variant="ghost" size="sm" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
