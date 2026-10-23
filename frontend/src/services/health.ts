import { apiBaseUrl } from "@/config/env";

export interface HealthPayload {
  status: string;
  service: string;
  version: string;
  environment: string;
  database?: "up" | "down";
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthPayload> {
  const response = await fetch(`${apiBaseUrl}/api/health`, { signal });

  // A degraded backend (database down) responds with 503 but still returns a
  // health payload describing which dependency failed.
  if (!response.ok && response.status !== 503) {
    throw new Error(`Backend responded with HTTP ${response.status}`);
  }

  return (await response.json()) as HealthPayload;
}

export { apiBaseUrl };
