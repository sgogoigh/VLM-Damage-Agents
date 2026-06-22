import type {
  HealthResponse,
  ProvidersResponse,
  SamplesResponse,
  VerifyRequest,
  VerifyResponse,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "http://localhost:8000";

/** Public URL for a dataset image path (e.g. "images/sample/case_001/img_1.jpg"). */
export function imageUrl(relPath: string): string {
  const clean = relPath.replace(/^\/+/, "");
  return `${API_BASE}/dataset/${clean}`;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError(
      "Can't reach the verification service. Is the backend running on " +
        `${API_BASE}?`,
      0
    );
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep default */
    }
    throw new ApiError(detail, res.status);
  }
  return (await res.json()) as T;
}

async function uploadImages(files: File[]): Promise<string[]> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  let res: Response;
  try {
    // No Content-Type header — the browser sets the multipart boundary.
    res = await fetch(`${API_BASE}/api/uploads`, { method: "POST", body: form });
  } catch {
    throw new ApiError(
      `Can't reach the verification service. Is the backend running on ${API_BASE}?`,
      0
    );
  }
  if (!res.ok) {
    let detail = `Upload failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : detail;
    } catch {
      /* keep default */
    }
    throw new ApiError(detail, res.status);
  }
  const data = (await res.json()) as { paths: string[] };
  return data.paths;
}

export const api = {
  health: () => request<HealthResponse>("/api/health"),
  uploadImages,
  providers: () => request<ProvidersResponse>("/api/providers"),
  samples: (split: "sample" | "test" | "all" = "sample") =>
    request<SamplesResponse>(`/api/samples?split=${split}`),
  verify: (body: VerifyRequest) =>
    request<VerifyResponse>("/api/verify", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
