import { useRef, useState, type DragEvent, type KeyboardEvent } from "react";
import { Upload } from "lucide-react";
import { MAX_UPLOAD_LABEL, UPLOAD_ACCEPT } from "@/lib/files";

interface UploadDropzoneProps {
  inputId: string;
  onFileSelected: (file: File) => void;
  disabled?: boolean;
}

export function UploadDropzone({
  inputId,
  onFileSelected,
  disabled = false,
}: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const openPicker = () => {
    if (!disabled) {
      inputRef.current?.click();
    }
  };

  const selectFiles = (files: FileList | null) => {
    const file = files?.[0];

    if (file) {
      onFileSelected(file);
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openPicker();
    }
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);

    if (!disabled) {
      selectFiles(event.dataTransfer.files);
    }
  };

  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-label="Upload a document"
      aria-disabled={disabled}
      data-testid="upload-dropzone"
      onClick={openPicker}
      onKeyDown={handleKeyDown}
      onDragEnter={(event) => {
        event.preventDefault();
        if (!disabled) {
          setIsDragging(true);
        }
      }}
      onDragOver={(event) => {
        event.preventDefault();
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      className={`flex cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed px-6 py-10 text-center transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-slate-900 ${
        isDragging
          ? "border-sky-500 bg-sky-50 dark:border-sky-400 dark:bg-sky-500/10"
          : "border-slate-300 bg-slate-50 hover:border-sky-400 hover:bg-sky-50/60 dark:border-slate-700 dark:bg-slate-950/40 dark:hover:border-sky-500"
      } ${disabled ? "cursor-not-allowed opacity-60" : ""}`}
    >
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-white text-sky-600 shadow-sm dark:bg-slate-900 dark:text-sky-400">
        <Upload className="h-6 w-6" />
      </span>
      <div>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          <span className="font-semibold text-slate-900 dark:text-slate-100">
            Click to browse
          </span>{" "}
          or drag and drop
        </p>
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
          PDF, DOCX, or TXT &middot; up to {MAX_UPLOAD_LABEL}
        </p>
      </div>
      <input
        ref={inputRef}
        id={inputId}
        type="file"
        accept={UPLOAD_ACCEPT}
        aria-label="Choose document file"
        tabIndex={-1}
        disabled={disabled}
        className="sr-only"
        onChange={(event) => {
          selectFiles(event.target.files);
          event.target.value = "";
        }}
      />
    </div>
  );
}
