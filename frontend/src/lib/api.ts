/**
 * api.ts — typed fetch client for the Geo-Insight FastAPI backend.
 *
 * One function per endpoint. Plain `fetch()` with explicit response typing —
 * no third-party HTTP client. All paths are relative (`/api/v1/...`) so the
 * Vite dev proxy forwards them to FastAPI in dev and they resolve same-origin
 * in the deployed Databricks App.
 */
import type {
  AskExchange,
  CascadeResponse,
  CbpfResponse,
  ChangesResponse,
  CompareResponse,
  CompositeWeightsResponse,
  CrisisDetail,
  RankingsResponse,
} from "@/lib/types";

const BASE = "/api/v1";

async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body?.detail) detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export type RankScope = "global" | "region" | "country";

export function fetchRankings(params?: {
  year?: number;
  scope?: RankScope;
  region?: string | null;
}): Promise<RankingsResponse> {
  const q = new URLSearchParams();
  q.set("year", String(params?.year ?? 2026));
  q.set("scope", params?.scope ?? "global");
  if (params?.region) q.set("region", params.region);
  return getJson<RankingsResponse>(`${BASE}/rankings?${q.toString()}`);
}

export function fetchCrisis(iso3: string, year = 2026): Promise<CrisisDetail> {
  return getJson<CrisisDetail>(`${BASE}/crisis/${encodeURIComponent(iso3)}?year=${year}`);
}

export function fetchCompare(countries: string[]): Promise<CompareResponse> {
  const q = new URLSearchParams({ countries: countries.join(",") });
  return getJson<CompareResponse>(`${BASE}/compare?${q.toString()}`);
}

export function fetchAsk(question: string): Promise<AskExchange> {
  return getJson<AskExchange>(`${BASE}/ask`, {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

export function fetchChanges(since = "2025-Q4"): Promise<ChangesResponse> {
  return getJson<ChangesResponse>(`${BASE}/changes?since=${encodeURIComponent(since)}`);
}

export function fetchCascadeDistribution(): Promise<CascadeResponse> {
  return getJson<CascadeResponse>(`${BASE}/methodology/cascade-distribution`);
}

export function fetchCompositeWeights(): Promise<CompositeWeightsResponse> {
  return getJson<CompositeWeightsResponse>(`${BASE}/methodology/composite-weights`);
}

/** Convenience alias used by the Methodology screen (both methodology reads). */
export const fetchMethodology = {
  cascade: fetchCascadeDistribution,
  weights: fetchCompositeWeights,
};

export function fetchCbpf(year = 2026): Promise<CbpfResponse> {
  return getJson<CbpfResponse>(`${BASE}/cbpf/funds?year=${year}`);
}
