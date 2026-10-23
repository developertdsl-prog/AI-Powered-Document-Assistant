export const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;
export const MAX_UPLOAD_LABEL = "20 MB";
export const SUPPORTED_EXTENSIONS = ["pdf", "docx", "txt"] as const;
export const UPLOAD_ACCEPT = ".pdf,.docx,.txt";

function extensionOf(filename: string): string {
  const lastDot = filename.lastIndexOf(".");

  return lastDot >= 0 ? filename.slice(lastDot + 1).toLowerCase() : "";
}

export function validateFile(file: File): string | null {
  const extension = extensionOf(file.name);

  if (
    !extension ||
    !SUPPORTED_EXTENSIONS.includes(
      extension as (typeof SUPPORTED_EXTENSIONS)[number],
    )
  ) {
    return "Unsupported format. Upload a PDF, DOCX, or TXT file.";
  }

  if (file.size === 0) {
    return "This file is empty. Choose a file with content.";
  }

  if (file.size > MAX_UPLOAD_BYTES) {
    return `This file is ${formatFileSize(file.size)}. The maximum upload size is ${MAX_UPLOAD_LABEL}.`;
  }

  return null;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }

  const kilobytes = bytes / 1024;
  if (kilobytes < 1024) {
    return `${kilobytes < 10 ? kilobytes.toFixed(1) : Math.round(kilobytes)} KB`;
  }

  const megabytes = kilobytes / 1024;
  return `${megabytes < 10 ? megabytes.toFixed(1) : Math.round(megabytes)} MB`;
}

export function formatUploadedAt(isoDate: string): string {
  const date = new Date(isoDate);

  if (Number.isNaN(date.getTime())) {
    return isoDate;
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export function documentTypeLabel(filename: string): string {
  const extension = extensionOf(filename);

  if (extension === "pdf" || extension === "docx" || extension === "txt") {
    return extension.toUpperCase();
  }

  return "FILE";
}
