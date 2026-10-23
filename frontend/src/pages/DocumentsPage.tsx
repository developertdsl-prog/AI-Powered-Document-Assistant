import { useEffect, useRef, useState } from "react";
import {
  FileText,
  RefreshCw,
  Upload,
  X,
} from "lucide-react";
import {
  Button,
  Card,
  CardBody,
  CardDescription,
  CardHeader,
  CardTitle,
  EmptyState,
  ErrorState,
  PageHeader,
  Spinner,
} from "@/components/ui";
import { DocumentList } from "@/components/documents/DocumentList";
import { UploadDropzone } from "@/components/documents/UploadDropzone";
import { UploadProgress } from "@/components/documents/UploadProgress";
import { validateFile } from "@/lib/files";
import { isAbortError } from "@/services/api";
import { listDocuments, uploadDocument } from "@/services/documents";
import type { DocumentRecord } from "@/types/documents";

const UPLOAD_INPUT_ID = "document-upload-input";
const POLL_INTERVAL_MS = 2000;

type UploadState =
  | { status: "idle" }
  | { status: "uploading"; file: File; percent: number }
  | { status: "success"; file: File; message: string }
  | { status: "error"; file: File; message: string }
  | { status: "cancelled"; file: File; message: string };

type NoticeTone = "success" | "error" | "neutral";

function describeError(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}

function Notice({
  tone,
  message,
  onDismiss,
}: {
  tone: NoticeTone;
  message: string;
  onDismiss: () => void;
}) {
  const toneStyles: Record<NoticeTone, string> = {
    success:
      "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-300",
    error:
      "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-300",
    neutral:
      "border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-300",
  };

  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`flex items-start justify-between gap-3 rounded-xl border px-4 py-3 text-sm ${toneStyles[tone]}`}
    >
      <p>{message}</p>
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss message"
        className="rounded p-0.5 opacity-70 transition hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);
  const [upload, setUpload] = useState<UploadState>({ status: "idle" });
  const uploadAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    listDocuments(controller.signal)
      .then((response) => {
        if (!active) {
          return;
        }

        setDocuments(response.items);
        setListError(null);
      })
      .catch((error: unknown) => {
        if (!active || isAbortError(error)) {
          return;
        }

        setListError(describeError(error));
      })
      .finally(() => {
        if (!active) {
          return;
        }

        setIsLoading(false);
        setIsRefreshing(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [refreshToken]);

  const hasActiveDocuments = documents.some(
    (document) =>
      document.status === "pending" || document.status === "processing",
  );

  useEffect(() => {
    if (!hasActiveDocuments) {
      return;
    }

    const timer = window.setInterval(() => {
      setRefreshToken((current) => current + 1);
    }, POLL_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, [hasActiveDocuments]);

  useEffect(
    () => () => {
      uploadAbortRef.current?.abort();
    },
    [],
  );

  const startUpload = (file: File) => {
    const validationError = validateFile(file);

    if (validationError) {
      setUpload({ status: "error", file, message: validationError });
      return;
    }

    uploadAbortRef.current?.abort();

    const controller = new AbortController();
    uploadAbortRef.current = controller;
    setUpload({ status: "uploading", file, percent: 0 });

    uploadDocument(file, {
      signal: controller.signal,
      onProgress: (percent) => {
        setUpload((current) =>
          current.status === "uploading"
            ? { ...current, percent }
            : current,
        );
      },
    })
      .then((document) => {
        setUpload({
          status: "success",
          file,
          message: `${document.original_filename} uploaded. Processing will start automatically.`,
        });
        setIsRefreshing(true);
        setRefreshToken((current) => current + 1);
      })
      .catch((error: unknown) => {
        if (isAbortError(error)) {
          setUpload({
            status: "cancelled",
            file,
            message: "Upload cancelled.",
          });
          return;
        }

        setUpload({
          status: "error",
          file,
          message: describeError(error),
        });
      })
      .finally(() => {
        if (uploadAbortRef.current === controller) {
          uploadAbortRef.current = null;
        }
      });
  };

  const handleRefresh = () => {
    setIsRefreshing(true);
    setRefreshToken((current) => current + 1);
  };

  const dismissUpload = () => setUpload({ status: "idle" });

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Documents"
        description="Upload PDF, DOCX, or TXT files and track their processing status."
        action={
          <Button
            onClick={() => {
              const input = document.getElementById(
                UPLOAD_INPUT_ID,
              ) as HTMLInputElement | null;
              input?.click();
            }}
          >
            <Upload className="h-4 w-4" />
            Upload document
          </Button>
        }
      />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Add a document</CardTitle>
            <CardDescription>
              Drag a file into the area below or choose one from your device.
            </CardDescription>
          </CardHeader>
          <CardBody className="flex flex-col gap-4">
            <UploadDropzone
              inputId={UPLOAD_INPUT_ID}
              onFileSelected={startUpload}
              disabled={upload.status === "uploading"}
            />

            {upload.status === "uploading" ? (
              <UploadProgress
                file={upload.file}
                percent={upload.percent}
                onCancel={() => uploadAbortRef.current?.abort()}
              />
            ) : null}

            {upload.status === "success" ? (
              <Notice
                tone="success"
                message={upload.message}
                onDismiss={dismissUpload}
              />
            ) : null}

            {upload.status === "cancelled" ? (
              <Notice
                tone="neutral"
                message={upload.message}
                onDismiss={dismissUpload}
              />
            ) : null}

            {upload.status === "error" ? (
              <Notice
                tone="error"
                message={upload.message}
                onDismiss={dismissUpload}
              />
            ) : null}
          </CardBody>
        </Card>

        <Card>
          <CardHeader className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle>Your documents</CardTitle>
              <CardDescription>
                {documents.length > 0
                  ? `${documents.length} uploaded`
                  : "Uploads appear here with their status."}
              </CardDescription>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={handleRefresh}
              disabled={isRefreshing}
            >
              <RefreshCw
                className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`}
              />
              Refresh
            </Button>
          </CardHeader>

          <CardBody className="flex flex-col gap-4">
            {isLoading ? <Spinner label="Loading documents..." /> : null}

            {!isLoading && listError && documents.length === 0 ? (
              <div className="flex flex-col gap-3">
                <ErrorState
                  title="Couldn't load documents"
                  description={listError}
                />
                <Button variant="secondary" onClick={handleRefresh}>
                  Try again
                </Button>
              </div>
            ) : null}

            {!isLoading && listError && documents.length > 0 ? (
              <div
                role="alert"
                className="rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:bg-amber-500/10 dark:text-amber-300"
              >
                Couldn't refresh the list: {listError}
              </div>
            ) : null}

            {!isLoading && !listError && documents.length === 0 ? (
              <EmptyState
                icon={FileText}
                title="No documents yet"
                description="Upload your first PDF, DOCX, or TXT file to get started."
              />
            ) : null}

            {documents.length > 0 ? (
              <DocumentList documents={documents} />
            ) : null}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
