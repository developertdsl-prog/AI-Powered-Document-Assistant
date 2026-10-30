import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { FileText, MessageSquare, Upload } from "lucide-react";
import { HealthStatusCard } from "@/components/HealthStatusCard";
import { DocumentStatusBadge } from "@/components/documents/DocumentStatusBadge";
import {
  Button,
  Card,
  CardBody,
  CardDescription,
  CardHeader,
  CardTitle,
  EmptyState,
  ErrorState,
  Spinner,
} from "@/components/ui";
import {
  documentTypeLabel,
  formatFileSize,
  formatUploadedAt,
} from "@/lib/files";
import { isAbortError } from "@/services/api";
import { listConversations } from "@/services/conversations";
import { listDocuments } from "@/services/documents";
import type { ConversationRecord } from "@/types/conversations";
import type { DocumentRecord } from "@/types/documents";

interface StatCard {
  label: string;
  value: string;
  hint: string;
}

const RECENT_LIMIT = 5;

const DOCUMENT_STATUSES = [
  "ready",
  "processing",
  "pending",
  "failed",
] as const;

function documentStatHint(documents: DocumentRecord[]): string {
  if (documents.length === 0) {
    return "Nothing uploaded yet";
  }

  const counts: Record<DocumentRecord["status"], number> = {
    pending: 0,
    processing: 0,
    ready: 0,
    failed: 0,
  };
  for (const document of documents) {
    counts[document.status] += 1;
  }

  return DOCUMENT_STATUSES.filter((status) => counts[status] > 0)
    .map((status) => `${counts[status]} ${status}`)
    .join(" · ");
}

function describeError(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [conversations, setConversations] = useState<ConversationRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    Promise.all([
      listDocuments(controller.signal),
      listConversations(controller.signal),
    ])
      .then(([documentPage, conversationPage]) => {
        if (!active) {
          return;
        }

        setDocuments(documentPage.items);
        setConversations(conversationPage.items);
        setLoadError(null);
      })
      .catch((error: unknown) => {
        if (!active || isAbortError(error)) {
          return;
        }

        setLoadError(describeError(error));
      })
      .finally(() => {
        if (!active) {
          return;
        }

        setIsLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [reloadToken]);

  const stats: StatCard[] = [
    {
      label: "Documents",
      value: String(documents.length),
      hint: documentStatHint(documents),
    },
    {
      label: "Conversations",
      value: String(conversations.length),
      hint:
        conversations.length === 0
          ? "Start a chat from any ready document"
          : "Across your document chats",
    },
    {
      label: "Failed",
      value: String(
        documents.filter((document) => document.status === "failed").length,
      ),
      hint: documents.some((document) => document.status === "failed")
        ? "Uploads that need attention"
        : "No processing errors",
    },
  ];

  const recentDocuments = documents.slice(0, RECENT_LIMIT);
  const recentConversations = conversations.slice(0, RECENT_LIMIT);

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100 sm:text-3xl">
            Dashboard
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Overview of your documents and conversations.
          </p>
        </div>
        <Button onClick={() => navigate("/documents")}>
          <Upload className="h-4 w-4" />
          Upload document
        </Button>
      </header>

      {isLoading ? <Spinner label="Loading dashboard..." /> : null}

      {!isLoading && loadError ? (
        <div className="flex flex-col items-center gap-3">
          <ErrorState
            title="Couldn't load the dashboard"
            description={loadError}
          />
          <Button
            variant="secondary"
            onClick={() => setReloadToken((current) => current + 1)}
          >
            Try again
          </Button>
        </div>
      ) : null}

      {!isLoading && !loadError ? (
        <>
          <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {stats.map((stat) => (
              <Card key={stat.label}>
                <CardBody className="flex flex-col gap-1">
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    {stat.label}
                  </p>
                  <p className="text-3xl font-semibold text-slate-900 dark:text-slate-100">
                    {stat.value}
                  </p>
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    {stat.hint}
                  </p>
                </CardBody>
              </Card>
            ))}
          </section>

          <HealthStatusCard />

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Recent documents</CardTitle>
                <CardDescription>
                  Track uploads and processing status from the library.
                </CardDescription>
              </CardHeader>
              <CardBody className="flex flex-col gap-3">
                {recentDocuments.map((document) => (
                  <div
                    key={document.id}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-100 px-4 py-3 dark:border-slate-800"
                  >
                    <div className="flex min-w-0 items-center gap-3">
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
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                          {documentTypeLabel(document.original_filename)} ·{" "}
                          {formatFileSize(document.file_size_bytes)} ·{" "}
                          {formatUploadedAt(document.created_at)}
                          {document.page_count
                            ? ` · ${document.page_count} pages`
                            : ""}
                        </p>
                      </div>
                    </div>
                    <DocumentStatusBadge status={document.status} />
                  </div>
                ))}
                {recentDocuments.length === 0 ? (
                  <EmptyState
                    title="No documents yet"
                    description="Upload a PDF, DOCX, or TXT file to get started."
                    action={
                      <Button onClick={() => navigate("/documents")}>
                        Upload document
                      </Button>
                    }
                  />
                ) : null}
              </CardBody>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Recent conversations</CardTitle>
                <CardDescription>
                  Continue asking questions about your uploaded documents.
                </CardDescription>
              </CardHeader>
              <CardBody className="flex flex-col gap-3">
                {recentConversations.map((conversation) => (
                  <div
                    key={conversation.id}
                    className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 px-4 py-3 dark:border-slate-800"
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-sky-100 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300">
                        <MessageSquare className="h-5 w-5" />
                      </div>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-slate-900 dark:text-slate-100">
                          {conversation.title}
                        </p>
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                          Updated {formatUploadedAt(conversation.updated_at)}
                        </p>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => navigate("/chat")}
                    >
                      Resume
                    </Button>
                  </div>
                ))}
                {recentConversations.length === 0 ? (
                  <EmptyState
                    icon={MessageSquare}
                    title="No conversations yet"
                    description="Open a document or start a new chat to begin."
                  />
                ) : null}
              </CardBody>
            </Card>
          </div>
        </>
      ) : null}
    </div>
  );
}
