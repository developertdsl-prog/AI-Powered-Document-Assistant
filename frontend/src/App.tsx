import { useCallback, useEffect, useState } from "react";
import {
  apiBaseUrl,
  fetchHealth,
  type HealthPayload,
} from "./services/health";

type HealthStatus = "loading" | "online" | "offline";

const statusStyles: Record<HealthStatus, string> = {
  loading:
    "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  online:
    "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
  offline: "bg-rose-100 text-rose-800 dark:bg-rose-500/15 dark:text-rose-300",
};

function describeError(caught: unknown): string {
  return caught instanceof Error ? caught.message : "Unable to reach the backend";
}

export default function App() {
  const [status, setStatus] = useState<HealthStatus>("loading");
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  const applyHealth = useCallback((payload: HealthPayload) => {
    setHealth(payload);
    setError(null);
    setStatus("online");
  }, []);

  const applyFailure = useCallback((caught: unknown) => {
    if (caught instanceof DOMException && caught.name === "AbortError") {
      return;
    }

    setHealth(null);
    setError(describeError(caught));
    setStatus("offline");
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    fetchHealth(controller.signal)
      .then((payload) => {
        if (!controller.signal.aborted) {
          applyHealth(payload);
        }
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          applyFailure(caught);
        }
      });

    return () => controller.abort();
  }, [applyHealth, applyFailure]);

  const handleRetry = () => {
    setStatus("loading");
    setError(null);
    fetchHealth().then(applyHealth).catch(applyFailure);
  };

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center px-6 py-16">
      <span className="mb-6 inline-flex w-fit items-center gap-2 rounded-full bg-sky-100 px-3 py-1 text-xs font-semibold tracking-wide text-sky-700 uppercase dark:bg-sky-500/15 dark:text-sky-300">
        Phase 1.1 · Foundation
      </span>

      <h1 className="text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
        AI-Powered Document Assistant
      </h1>

      <p className="mt-4 max-w-xl text-lg text-slate-600 dark:text-slate-400">
        The foundation is running. Uploading, document processing, and grounded
        AI answers arrive in the next phases.
      </p>

      <section className="mt-10 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold text-slate-500 uppercase dark:text-slate-400">
              Backend health
            </h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {apiBaseUrl}/api/health
            </p>
          </div>

          <span
            className={`rounded-full px-3 py-1 text-xs font-semibold capitalize ${statusStyles[status]}`}
          >
            {status === "loading" ? "checking..." : status}
          </span>
        </div>

        {health ? (
          <dl className="mt-6 grid grid-cols-1 gap-4 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-slate-500 dark:text-slate-400">Service</dt>
              <dd className="mt-1 font-medium">{health.service}</dd>
            </div>
            <div>
              <dt className="text-slate-500 dark:text-slate-400">Version</dt>
              <dd className="mt-1 font-medium">{health.version}</dd>
            </div>
            <div>
              <dt className="text-slate-500 dark:text-slate-400">Environment</dt>
              <dd className="mt-1 font-medium">{health.environment}</dd>
            </div>
          </dl>
        ) : null}

        {error ? (
          <p
            role="alert"
            className="mt-6 rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:bg-rose-500/10 dark:text-rose-300"
          >
            {error}. Start the backend with{" "}
            <code className="font-mono">uvicorn app.main:app --reload</code> and
            try again.
          </p>
        ) : null}

        <button
          type="button"
          onClick={handleRetry}
          disabled={status === "loading"}
          className="mt-6 inline-flex items-center rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-sky-500 dark:text-slate-950 dark:hover:bg-sky-400"
        >
          {status === "loading" ? "Checking..." : "Check again"}
        </button>
      </section>
    </main>
  );
}
