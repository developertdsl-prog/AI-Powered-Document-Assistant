import { apiBaseUrl } from "@/config/env";

export interface HealthPayload {
  status: string;
  service: string;
  version: string;
  environment: string;
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthPayload> {
  const response = await fetch(`${apiBaseUrl}/api/health`, { signal });

  if (!response.ok) {
    throw new Error(`Backend responded with HTTP ${response.status}`);
  }

  return (await response.json()) as HealthPayload;
}

export { apiBaseUrl };
