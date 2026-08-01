import { Insight, Theme, Segment, Review, ReviewFilters, Distribution, EvalReport, Stats, PaginatedResponse } from "@/types";

const API_BASE = "/api";

async function fetchJson<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }

  return res.json();
}

export const api = {
  insights: () => fetchJson<{ insights: Insight[] }>("/insights"),
  themes: () => fetchJson<{ themes: Theme[] }>("/themes"),
  eval: () => fetchJson<EvalReport>("/eval"),
  segments: () => fetchJson<{ segments: Segment[] }>("/segments"),
  stats: () => fetchJson<Stats>("/stats"),
  reviews: (params?: Record<string, string | number>) => {
    const qs = params
      ? "?" +
        new URLSearchParams(
          Object.entries(params).reduce((a, [k, v]) => ({ ...a, [k]: String(v) }), {} as Record<string, string>)
        ).toString()
      : "";
    return fetchJson<PaginatedResponse<Review>>(`/reviews${qs}`);
  },
  reviewFilters: () => fetchJson<ReviewFilters>("/review-filters"),
  reviewDistribution: () => fetchJson<Distribution>("/review-distribution"),
  umap: (format = "json") => fetchJson<{ exists: boolean; image_url?: string; points?: unknown[]; count?: number }>(`/umap?format=${format}`),
};
