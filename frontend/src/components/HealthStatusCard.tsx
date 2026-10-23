import { useCallback, useEffect, useState } from "react";
import { Activity } from "lucide-react";
import { Button, Spinner } from "@/components/ui";
import { fetchHealth, type HealthPayload } from "@/services/health";

type HealthStatus = "loading" | "online" | "degraded" | "offline";

const statusStyles: Record<HealthStatus, string> = {
  loading:
    "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  online:
    "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
  degraded:
    "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  offline: "bg-rose-100 text-rose-800 dark:bg-rose-500/15 dark:text-rose-300",
};

const statusLabels: Record<HealthStatus, string> = {
  loading: "checking...",
  online: "online",
  degraded: "degraded",
  offline: "offline",
};

function describeError(caught: unknown): string {
  return caught instanceof Error ? caught.message : "Unable to reach the backend";
}

export function HealthStatusCard() {
  const [status, setStatus] = useState<HealthStatus>("loading");
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  const applyHealth = useCallback((payload: HealthPayload) => {
    setHealth(payload);
    setError(null);
    setStatus(payload.database === "down" ? "degraded" : "online");
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
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
            <Activity className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              System status
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {health
                ? `${health.service} · v${health.version} · ${health.environment}`
                : "Checking the backend connection"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span
            className={`rounded-full px-3 py-1 text-xs font-semibold capitalize ${statusStyles[status]}`}
          >
            {statusLabels[status]}
          </span>
          <Button variant="secondary" size="sm" onClick={handleRetry}>
            Retry
          </Button>
        </div>
      </div>

      {status === "loading" ? (
        <div className="mt-4">
          <Spinner label="Contacting backend..." />
        </div>
      ) : null}

      {health ? (
        <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">
          Database:{" "}
          <span className="font-medium text-slate-700 dark:text-slate-200">
            {health.database ?? "not reported"}
          </span>
        </p>
      ) : null}

      {error ? (
        <div
          role="alert"
          className="mt-4 rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:bg-rose-500/10 dark:text-rose-300"
        >
          {error}. Start the backend with{" "}
          <code className="font-mono">uvicorn app.main:app --reload</code>.
        </div>
      ) : null}
    </section>
  );
}
