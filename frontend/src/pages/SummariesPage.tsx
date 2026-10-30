import { useEffect, useState } from "react";
import { FileText, ListChecks, Sparkles } from "lucide-react";
import {
  Button,
  Card,
  CardBody,
  EmptyState,
  PageHeader,
  Spinner,
} from "@/components/ui";
import { isAbortError } from "@/services/api";
import { listDocuments } from "@/services/documents";
import { extractInsights, generateSummary } from "@/services/insights";
import type { DocumentRecord } from "@/types/documents";
import type {
  ExtractionResponse,
  SummaryLength,
  SummaryResponse,
} from "@/types/insights";

function describeError(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}

function parseFields(text: string): string[] {
  return text
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

function lengthButtonStyle(active: boolean): string {
  return `rounded-lg border px-3 py-1.5 text-sm transition-colors ${
    active
      ? "border-sky-500 bg-sky-50 text-sky-900 dark:border-sky-500 dark:bg-sky-950 dark:text-sky-100"
      : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
  }`;
}

function ChipList({ items, empty }: { items: string[]; empty: string }) {
  if (items.length === 0) {
    return <p className="text-sm text-slate-500 dark:text-slate-400">{empty}</p>;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <span
          key={item}
          className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-300"
        >
          {item}
        </span>
      ))}
    </div>
  );
}

function InsightMeta({
  provider,
  sourceChunks,
  truncated,
}: {
  provider: string;
  sourceChunks: number;
  truncated: boolean;
}) {
  return (
    <div className="flex flex-col gap-1 text-xs text-slate-500 dark:text-slate-400">
      <span>
        Generated from {sourceChunks}{" "}
        {sourceChunks === 1 ? "passage" : "passages"} · provider {provider}
      </span>
      {truncated ? (
        <span className="text-amber-600 dark:text-amber-400">
          This document is longer than the context budget, so only its first
          part was used.
        </span>
      ) : null}
    </div>
  );
}

export default function SummariesPage() {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [documentId, setDocumentId] = useState("");
  const [length, setLength] = useState<SummaryLength>("concise");
  const [fieldsText, setFieldsText] = useState("");
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [extraction, setExtraction] = useState<ExtractionResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    listDocuments(controller.signal)
      .then((page) => {
        if (!active) {
          return;
        }

        const ready = page.items.filter((doc) => doc.status === "ready");
        setDocuments(ready);
        setDocumentId((current) =>
          current && ready.some((doc) => doc.id === current)
            ? current
            : (ready[0]?.id ?? ""),
        );
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

  function handleDocumentChange(nextId: string) {
    setDocumentId(nextId);
    setSummary(null);
    setExtraction(null);
    setError(null);
  }

  async function handleGenerateSummary(): Promise<void> {
    if (!documentId || isSummarizing) {
      return;
    }

    setIsSummarizing(true);
    setError(null);

    try {
      setSummary(await generateSummary(documentId, length));
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setIsSummarizing(false);
    }
  }

  async function handleExtract(): Promise<void> {
    if (!documentId || isExtracting) {
      return;
    }

    setIsExtracting(true);
    setError(null);

    try {
      setExtraction(
        await extractInsights(documentId, { fields: parseFields(fieldsText) }),
      );
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setIsExtracting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Summaries"
        description="Generate concise and detailed summaries with extracted insights."
      />

      {error ? (
        <div
          role="alert"
          className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-200"
        >
          {error}
        </div>
      ) : null}

      {isLoading ? (
        <Spinner label="Loading documents…" />
      ) : documents.length === 0 ? (
        <EmptyState
          icon={Sparkles}
          title="No ready documents yet"
          description="Upload a document and wait for it to finish processing, then summarize it here."
        />
      ) : (
        <>
          <Card>
            <CardBody>
              <label className="flex flex-col gap-2 text-sm sm:max-w-md">
                <span className="font-medium text-slate-700 dark:text-slate-200">
                  Document
                </span>
                <select
                  value={documentId}
                  onChange={(event) => handleDocumentChange(event.target.value)}
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-slate-900 shadow-sm dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                >
                  {documents.map((document) => (
                    <option key={document.id} value={document.id}>
                      {document.original_filename}
                    </option>
                  ))}
                </select>
              </label>
            </CardBody>
          </Card>

          <Card>
            <CardBody className="flex flex-col gap-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-slate-100">
                    <FileText className="h-4 w-4" />
                    Summary
                  </h2>
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                    A summary written from the document's own text.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <div
                    role="group"
                    aria-label="Summary length"
                    className="flex items-center gap-2"
                  >
                    {(["concise", "detailed"] as const).map((option) => (
                      <button
                        key={option}
                        type="button"
                        aria-pressed={length === option}
                        onClick={() => setLength(option)}
                        className={lengthButtonStyle(length === option)}
                      >
                        {option === "concise" ? "Concise" : "Detailed"}
                      </button>
                    ))}
                  </div>
                  <Button
                    onClick={handleGenerateSummary}
                    disabled={isSummarizing}
                  >
                    {isSummarizing ? "Generating…" : "Generate summary"}
                  </Button>
                </div>
              </div>

              {summary ? (
                <div className="flex flex-col gap-3 border-t border-slate-200 pt-4 dark:border-slate-700">
                  <p className="whitespace-pre-wrap text-sm text-slate-800 dark:text-slate-100">
                    {summary.summary}
                  </p>
                  <InsightMeta
                    provider={summary.provider}
                    sourceChunks={summary.source_chunks}
                    truncated={summary.truncated}
                  />
                </div>
              ) : (
                <p className="border-t border-slate-200 pt-4 text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
                  Choose a length and generate a summary for the selected
                  document.
                </p>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardBody className="flex flex-col gap-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-slate-100">
                    <ListChecks className="h-4 w-4" />
                    Extraction
                  </h2>
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                    Key points, dates, names, and any fields you ask for.
                  </p>
                </div>
                <Button onClick={handleExtract} disabled={isExtracting}>
                  {isExtracting ? "Extracting…" : "Extract insights"}
                </Button>
              </div>

              <label className="flex flex-col gap-2 text-sm sm:max-w-md">
                <span className="font-medium text-slate-700 dark:text-slate-200">
                  Extra fields
                </span>
                <input
                  type="text"
                  value={fieldsText}
                  onChange={(event) => setFieldsText(event.target.value)}
                  placeholder="Comma separated, e.g. Invoice number, Due date"
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-slate-900 shadow-sm placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:placeholder:text-slate-500"
                />
              </label>

              {extraction ? (
                <div className="flex flex-col gap-4 border-t border-slate-200 pt-4 dark:border-slate-700">
                  <section className="flex flex-col gap-2">
                    <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                      Key points
                    </h3>
                    {extraction.key_points.length === 0 ? (
                      <p className="text-sm text-slate-500 dark:text-slate-400">
                        Nothing found.
                      </p>
                    ) : (
                      <ul className="flex list-disc flex-col gap-1 pl-5 text-sm text-slate-700 dark:text-slate-200">
                        {extraction.key_points.map((point) => (
                          <li key={point}>{point}</li>
                        ))}
                      </ul>
                    )}
                  </section>

                  <section className="flex flex-col gap-2">
                    <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                      Dates
                    </h3>
                    <ChipList
                      items={extraction.dates}
                      empty="No dates found."
                    />
                  </section>

                  <section className="flex flex-col gap-2">
                    <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                      Names
                    </h3>
                    <ChipList
                      items={extraction.names}
                      empty="No names found."
                    />
                  </section>

                  {extraction.fields.length > 0 ? (
                    <section className="flex flex-col gap-2">
                      <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                        Requested fields
                      </h3>
                      <ul className="flex flex-col gap-1">
                        {extraction.fields.map((field) => (
                          <li
                            key={field.name}
                            className="flex justify-between gap-4 text-sm"
                          >
                            <span className="font-medium text-slate-700 dark:text-slate-200">
                              {field.name}
                            </span>
                            <span
                              className={
                                field.found
                                  ? "text-right text-slate-600 dark:text-slate-300"
                                  : "text-right italic text-slate-400"
                              }
                            >
                              {field.found ? field.value : "Not found"}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </section>
                  ) : null}

                  <InsightMeta
                    provider={extraction.provider}
                    sourceChunks={extraction.source_chunks}
                    truncated={extraction.truncated}
                  />
                </div>
              ) : (
                <p className="border-t border-slate-200 pt-4 text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
                  Extract insights to see key points, dates, names, and your
                  requested fields.
                </p>
              )}
            </CardBody>
          </Card>
        </>
      )}
    </div>
  );
}
