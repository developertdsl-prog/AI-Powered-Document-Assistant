import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, RefreshCw } from "lucide-react";
import {
  Button,
  Card,
  CardBody,
  CardDescription,
  CardHeader,
  CardTitle,
  ErrorState,
  PageHeader,
  Spinner,
} from "@/components/ui";
import { DocumentStatusBadge } from "@/components/documents/DocumentStatusBadge";
import {
  documentTypeLabel,
  formatFileSize,
  formatUploadedAt,
} from "@/lib/files";
import { isAbortError } from "@/services/api";
import { getDocument, getDocumentText } from "@/services/documents";
import type { DocumentRecord, DocumentTextResponse } from "@/types/documents";

const POLL_INTERVAL_MS = 2000;

function describeError(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}

function formatMetadataValue(value: unknown): string {
  if (typeof value === "object" && value !== null) {
    return JSON.stringify(value);
  }

  return String(value);
}

export default function DocumentDetailPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const [document, setDocument] = useState<DocumentRecord | null>(null);
  const [text, setText] = useState<DocumentTextResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);

  useEffect(() => {
    if (!documentId) {
      return;
    }

    const controller = new AbortController();
    let active = true;

    getDocument(documentId, controller.signal)
      .then(async (record) => {
        if (!active) {
          return;
        }

        setDocument(record);
        setError(null);

        if (record.status === "ready") {
          const extracted = await getDocumentText(
            documentId,
            controller.signal,
          );
          if (active) {
            setText(extracted);
          }
        } else {
          setText(null);
        }
      })
      .catch((caught: unknown) => {
        if (!active || isAbortError(caught)) {
          return;
        }

        setError(describeError(caught));
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
  }, [documentId, refreshToken]);

  const isProcessing =
    document?.status === "pending" || document?.status === "processing";

  useEffect(() => {
    if (!isProcessing) {
      return;
    }

    const timer = window.setInterval(() => {
      setRefreshToken((current) => current + 1);
    }, POLL_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, [isProcessing]);

  const handleRefresh = () => {
    setIsRefreshing(true);
    setRefreshToken((current) => current + 1);
  };

  if (!documentId) {
    return (
      <div className="flex flex-col gap-6">
        <BackLink />
        <ErrorState
          title="Document not found"
          description="The document id is missing."
        />
      </div>
    );
  }

  if (isLoading && !document) {
    return (
      <div className="flex flex-col gap-6">
        <BackLink />
        <Spinner label="Loading document..." />
      </div>
    );
  }

  if (!document) {
    return (
      <div className="flex flex-col gap-6">
        <BackLink />
        <ErrorState
          title="Document not found"
          description={error ?? "The document could not be loaded."}
        />
        <div>
          <Button variant="secondary" onClick={handleRefresh}>
            Try again
          </Button>
        </div>
      </div>
    );
  }

  const metadataEntries = Object.entries(text?.metadata ?? {}).filter(
    ([, value]) => value !== null && value !== undefined && value !== "",
  );

  return (
    <div className="flex flex-col gap-6">
      <BackLink />

      <PageHeader
        title={document.original_filename}
        description="Extracted text and processing details."
        action={
          <Button
            variant="secondary"
            onClick={handleRefresh}
            disabled={isRefreshing}
          >
            <RefreshCw
              className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
        }
      />

      <Card>
        <CardBody>
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Status
              </dt>
              <dd className="mt-1">
                <DocumentStatusBadge status={document.status} />
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Type
              </dt>
              <dd className="mt-1 text-sm font-medium text-slate-900 dark:text-slate-100">
                {documentTypeLabel(document.original_filename)}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Size
              </dt>
              <dd className="mt-1 text-sm font-medium text-slate-900 dark:text-slate-100">
                {formatFileSize(document.file_size_bytes)}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Uploaded
              </dt>
              <dd className="mt-1 text-sm font-medium text-slate-900 dark:text-slate-100">
                {formatUploadedAt(document.created_at)}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Pages
              </dt>
              <dd className="mt-1 text-sm font-medium text-slate-900 dark:text-slate-100">
                {document.page_count ?? "—"}
              </dd>
            </div>
          </dl>
        </CardBody>
      </Card>

      {error ? (
        <div
          role="alert"
          className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:bg-rose-500/10 dark:text-rose-300"
        >
          {error}
        </div>
      ) : null}

      {isProcessing ? (
        <Card>
          <CardBody className="flex flex-col items-start gap-3">
            <Spinner label="Processing document..." />
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Text extraction is running in the background. This page updates
              automatically every few seconds.
            </p>
          </CardBody>
        </Card>
      ) : null}

      {document.status === "failed" ? (
        <ErrorState
          title="Processing failed"
          description={
            document.error_message ??
            "The document could not be converted into text."
          }
        />
      ) : null}

      {document.status === "ready" && text ? (
        <Card>
          <CardHeader>
            <CardTitle>Extracted text</CardTitle>
            <CardDescription>
              {text.pages.length === 1
                ? "1 page"
                : `${text.pages.length} pages`}{" "}
              extracted from this document.
            </CardDescription>
          </CardHeader>
          <CardBody className="flex flex-col gap-5">
            {metadataEntries.length > 0 ? (
              <dl className="grid grid-cols-1 gap-3 rounded-xl bg-slate-50 p-4 text-sm sm:grid-cols-2 lg:grid-cols-3 dark:bg-slate-800/50">
                {metadataEntries.map(([key, value]) => (
                  <div key={key}>
                    <dt className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
                      {key.replaceAll("_", " ")}
                    </dt>
                    <dd className="mt-0.5 break-words text-slate-700 dark:text-slate-300">
                      {formatMetadataValue(value)}
                    </dd>
                  </div>
                ))}
              </dl>
            ) : null}

            {text.pages.length === 0 ? (
              <p className="text-sm text-slate-500 dark:text-slate-400">
                No extracted pages were returned.
              </p>
            ) : null}

            {text.pages.map((page) => (
              <article
                key={page.page_number}
                aria-label={`Page ${page.page_number}`}
                className="rounded-xl border border-slate-200 dark:border-slate-800"
              >
                <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-2.5 dark:border-slate-800">
                  <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                    Page {page.page_number}
                  </h4>
                  <span className="text-xs text-slate-500 dark:text-slate-400">
                    {page.character_count} characters
                  </span>
                </header>
                <p className="whitespace-pre-wrap break-words px-4 py-4 text-sm leading-6 text-slate-700 dark:text-slate-300">
                  {page.content || "No text on this page."}
                </p>
              </article>
            ))}
          </CardBody>
        </Card>
      ) : null}

      {document.status === "ready" && !text && !error ? (
        <Spinner label="Loading extracted text..." />
      ) : null}
    </div>
  );
}

function BackLink() {
  return (
    <Link
      to="/documents"
      className="inline-flex w-fit items-center gap-1.5 rounded text-sm font-medium text-slate-600 transition hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:text-slate-400 dark:hover:text-slate-100"
    >
      <ArrowLeft className="h-4 w-4" />
      Back to documents
    </Link>
  );
}
