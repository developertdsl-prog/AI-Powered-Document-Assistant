import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { MessageSquare, Plus, Send } from "lucide-react";
import {
  Button,
  Card,
  CardBody,
  EmptyState,
  PageHeader,
  Spinner,
} from "@/components/ui";
import { isAbortError } from "@/services/api";
import {
  createConversation,
  getConversation,
  listConversations,
  sendMessage,
} from "@/services/conversations";
import { listDocuments } from "@/services/documents";
import type { DocumentRecord } from "@/types/documents";
import type {
  ChatMessage,
  ConversationRecord,
} from "@/types/conversations";

function describeError(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}

function conversationButtonStyle(active: boolean): string {
  return `w-full rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
    active
      ? "border-sky-500 bg-sky-50 text-sky-900 dark:border-sky-500 dark:bg-sky-950 dark:text-sky-100"
      : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
  }`;
}

function CitationList({ message }: { message: ChatMessage }) {
  if (message.citations.length === 0) {
    return null;
  }

  return (
    <ul className="mt-3 flex flex-col gap-2 border-t border-slate-200 pt-3 dark:border-slate-700">
      {message.citations.map((citation) => (
        <li
          key={citation.reference}
          className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300"
        >
          <span className="font-semibold text-slate-700 dark:text-slate-200">
            [{citation.reference}]
          </span>{" "}
          <span>
            {citation.page_number !== null
              ? `Page ${citation.page_number}`
              : `Passage ${citation.chunk_index + 1}`}
          </span>
          <p className="mt-1">{citation.excerpt}</p>
        </li>
      ))}
    </ul>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <li
      className={`flex ${isUser ? "justify-end" : "justify-start"}`}
    >
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${
          isUser
            ? "bg-sky-600 text-white"
            : "border border-slate-200 bg-white text-slate-800 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        }`}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>
        {isUser ? null : <CitationList message={message} />}
      </div>
    </li>
  );
}

export default function ChatPage() {
  const [conversations, setConversations] = useState<ConversationRecord[]>([]);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [isPickerOpen, setIsPickerOpen] = useState(false);
  const [pickerDocumentId, setPickerDocumentId] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    Promise.all([
      listConversations(controller.signal),
      listDocuments(controller.signal),
    ])
      .then(([conversationPage, documentPage]) => {
        if (!active) {
          return;
        }

        setConversations(conversationPage.items);
        setDocuments(documentPage.items.filter((doc) => doc.status === "ready"));
      })
      .catch((caught: unknown) => {
        if (!active || isAbortError(caught)) {
          return;
        }

        setError(describeError(caught));
      })
      .finally(() => {
        if (active) {
          setIsLoading(false);
        }
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, []);

  const openConversation = useCallback(
    async (conversationId: string) => {
      setError(null);
      setActiveId(conversationId);
      setMessages([]);

      try {
        const detail = await getConversation(conversationId);
        setMessages(detail.messages);
      } catch (caught) {
        if (!isAbortError(caught)) {
          setError(describeError(caught));
        }
      }
    },
    [],
  );

  async function handleStartConversation(
    event: FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();

    if (!pickerDocumentId) {
      return;
    }

    setError(null);

    try {
      const conversation = await createConversation(pickerDocumentId);
      setConversations((current) => [conversation, ...current]);
      setMessages([]);
      setActiveId(conversation.id);
      setIsPickerOpen(false);
      setPickerDocumentId("");
    } catch (caught) {
      setError(describeError(caught));
    }
  }

  async function handleSend(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();

    const question = draft.trim();

    if (!question || !activeId || isSending) {
      return;
    }

    setIsSending(true);
    setError(null);

    try {
      const exchange = await sendMessage(activeId, question);
      setMessages((current) => [
        ...current,
        exchange.user_message,
        exchange.assistant_message,
      ]);
      setDraft("");
      // The backend retitles a default conversation with its first question;
      // mirror that so the sidebar does not lag behind.
      setConversations((current) =>
        current.map((conversation) =>
          conversation.id === activeId &&
          conversation.title === "New conversation"
            ? { ...conversation, title: question.slice(0, 60) }
            : conversation,
        ),
      );
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setIsSending(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Chat"
        description="Ask questions about a document and get answers grounded in its content."
        action={
          <Button
            onClick={() => setIsPickerOpen((open) => !open)}
            disabled={documents.length === 0}
          >
            <Plus className="h-4 w-4" />
            New conversation
          </Button>
        }
      />

      {error ? (
        <div
          role="alert"
          className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-200"
        >
          {error}
        </div>
      ) : null}

      {isPickerOpen ? (
        <Card>
          <CardBody>
            <form
              onSubmit={handleStartConversation}
              className="flex flex-col gap-3 sm:flex-row sm:items-end"
            >
              <label className="flex flex-1 flex-col gap-2 text-sm">
                <span className="font-medium text-slate-700 dark:text-slate-200">
                  Document
                </span>
                <select
                  value={pickerDocumentId}
                  onChange={(event) => setPickerDocumentId(event.target.value)}
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-slate-900 shadow-sm dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                >
                  <option value="">Choose a document…</option>
                  {documents.map((document) => (
                    <option key={document.id} value={document.id}>
                      {document.original_filename}
                    </option>
                  ))}
                </select>
              </label>
              <Button type="submit" disabled={!pickerDocumentId}>
                Start chatting
              </Button>
            </form>
          </CardBody>
        </Card>
      ) : null}

      {isLoading ? (
        <Spinner label="Loading conversations…" />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(0, 16rem)_minmax(0, 1fr)]">
          <aside className="flex flex-col gap-2">
            <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              History
            </h2>
            {conversations.length === 0 ? (
              <p className="text-sm text-slate-500 dark:text-slate-400">
                No conversations yet.
              </p>
            ) : (
              conversations.map((conversation) => (
                <button
                  key={conversation.id}
                  type="button"
                  onClick={() => openConversation(conversation.id)}
                  className={conversationButtonStyle(
                    conversation.id === activeId,
                  )}
                  aria-current={
                    conversation.id === activeId ? "true" : undefined
                  }
                >
                  <span className="block truncate">{conversation.title}</span>
                  <span className="mt-0.5 block text-xs text-slate-500 dark:text-slate-400">
                    {new Date(conversation.updated_at).toLocaleString()}
                  </span>
                </button>
              ))
            )}
          </aside>

          <section className="flex min-h-[24rem] flex-col gap-4">
            {activeId === null ? (
              <EmptyState
                icon={MessageSquare}
                title="Pick a conversation"
                description="Start a new conversation about a ready document, or choose one from your history."
              />
            ) : (
              <>
                <Card>
                  <CardBody className="flex flex-col gap-4">
                    {messages.length === 0 ? (
                      <p className="text-sm text-slate-500 dark:text-slate-400">
                        Ask your first question about this document.
                      </p>
                    ) : (
                      <ul className="flex flex-col gap-4">
                        {messages.map((message) => (
                          <MessageBubble
                            key={message.id}
                            message={message}
                          />
                        ))}
                      </ul>
                    )}
                    {isSending ? (
                      <p className="text-sm text-slate-500 dark:text-slate-400">
                        Generating an answer…
                      </p>
                    ) : null}
                  </CardBody>
                </Card>

                <form
                  onSubmit={handleSend}
                  className="flex flex-col gap-3 sm:flex-row sm:items-end"
                >
                  <label className="flex flex-1 flex-col gap-2 text-sm">
                    <span className="sr-only">Your question</span>
                    <input
                      type="text"
                      value={draft}
                      onChange={(event) => setDraft(event.target.value)}
                      placeholder="Ask a question about this document…"
                      className="w-full rounded-lg border border-slate-200 px-3 py-2 text-slate-900 shadow-sm placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:placeholder:text-slate-500"
                    />
                  </label>
                  <Button
                    type="submit"
                    disabled={isSending || draft.trim().length === 0}
                  >
                    <Send className="h-4 w-4" />
                    Send
                  </Button>
                </form>
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
