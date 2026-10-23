import { HealthStatusCard } from "@/components/HealthStatusCard";
import { Button, Card, CardBody, CardDescription, CardHeader, CardTitle, EmptyState } from "@/components/ui";
import type { ConversationSummary, DocumentSummary, StatCard } from "@/types";
import { FileText, MessageSquare, Upload } from "lucide-react";

const stats: StatCard[] = [
  { label: "Documents", value: "3", hint: "2 ready · 1 processing" },
  { label: "Conversations", value: "4", hint: "Across document and general chat" },
  { label: "Summaries", value: "2", hint: "Generated this week" },
];

const recentDocuments: DocumentSummary[] = [
  {
    id: "doc-1",
    title: "Quarterly Report Q4.pdf",
    type: "PDF",
    sizeLabel: "2.4 MB",
    uploadedAt: "2026-10-23",
    status: "ready",
    pages: 24,
  },
  {
    id: "doc-2",
    title: "Product Requirements.docx",
    type: "DOCX",
    sizeLabel: "412 KB",
    uploadedAt: "2026-10-22",
    status: "ready",
    pages: 9,
  },
  {
    id: "doc-3",
    title: "Meeting Notes.txt",
    type: "TXT",
    sizeLabel: "18 KB",
    uploadedAt: "2026-10-23",
    status: "processing",
    pages: null,
  },
];

const recentConversations: ConversationSummary[] = [
  {
    id: "conv-1",
    documentId: "doc-1",
    title: "Q4 revenue breakdown",
    lastActivityAt: "2026-10-23 09:42",
    messageCount: 6,
  },
  {
    id: "conv-2",
    documentId: "doc-2",
    title: "API authentication requirements",
    lastActivityAt: "2026-10-22 16:18",
    messageCount: 4,
  },
];

const statusStyles: Record<DocumentSummary["status"], string> = {
  ready:
    "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
  processing:
    "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  error: "bg-rose-100 text-rose-800 dark:bg-rose-500/15 dark:text-rose-300",
};

export default function DashboardPage() {
  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100 sm:text-3xl">
            Dashboard
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Overview of your documents, conversations, and summaries.
          </p>
        </div>
        <Button>
          <Upload className="h-4 w-4" />
          Upload document
        </Button>
      </header>

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
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                    <FileText className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-900 dark:text-slate-100">
                      {document.title}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      {document.type} · {document.sizeLabel} ·{" "}
                      {document.uploadedAt}
                      {document.pages ? ` · ${document.pages} pages` : ""}
                    </p>
                  </div>
                </div>
                <span
                  className={`rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${statusStyles[document.status]}`}
                >
                  {document.status}
                </span>
              </div>
            ))}
            {recentDocuments.length === 0 ? (
              <EmptyState
                title="No documents yet"
                description="Upload a PDF, DOCX, or TXT file to get started."
                action={<Button>Upload document</Button>}
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
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-sky-100 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300">
                    <MessageSquare className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-900 dark:text-slate-100">
                      {conversation.title}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      {conversation.messageCount} messages ·{" "}
                      {conversation.lastActivityAt}
                    </p>
                  </div>
                </div>
                <Button variant="ghost" size="sm">
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
    </div>
  );
}
