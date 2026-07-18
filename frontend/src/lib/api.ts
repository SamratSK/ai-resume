import type {
  JobDescription,
  JobStatus,
  ResumeRecord,
  ResumeSummary,
  ShortlistPayload,
  ProvenancePayload,
  ChatHistoryMessage,
  ChatResponse,
} from "./types";

const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: init?.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* non-JSON error body, keep statusText */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

async function pollJob<T>(jobId: string, intervalMs = 900): Promise<T> {
  while (true) {
    const job = await request<JobStatus<T>>(`/jobs/${jobId}`);
    if (job.status === "done") return job.result as T;
    if (job.status === "error") throw new Error(job.error ?? "Job failed");
    await new Promise((r) => setTimeout(r, intervalMs));
  }
}

async function pollJobWithProgress<T>(
  jobId: string,
  onProgress: (progress: string) => void,
  intervalMs = 900,
): Promise<T> {
  while (true) {
    const job = await request<JobStatus<T>>(`/jobs/${jobId}`);
    onProgress(job.progress);
    if (job.status === "done") return job.result as T;
    if (job.status === "error") throw new Error(job.error ?? "Job failed");
    await new Promise((r) => setTimeout(r, intervalMs));
  }
}

export const api = {
  jds: {
    list: () => request<JobDescription[]>("/jds"),
    get: (id: string) => request<JobDescription>(`/jds/${id}`),
    create: (payload: JobDescription) =>
      request<JobDescription>("/jds", { method: "POST", body: JSON.stringify(payload) }),
    parse: (text: string) =>
      request<JobDescription>("/jds/parse", { method: "POST", body: JSON.stringify({ text }) }),
    update: (id: string, payload: Partial<JobDescription>) =>
      request<JobDescription>(`/jds/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
    remove: (id: string) => request<void>(`/jds/${id}`, { method: "DELETE" }),
  },
  resumes: {
    list: () => request<ResumeSummary[]>("/resumes"),
    get: (id: string) => request<ResumeRecord>(`/resumes/${id}`),
    pages: (id: string) => request<ProvenancePayload>(`/resumes/${id}/pages`),
    remove: (id: string) => request<void>(`/resumes/${id}`, { method: "DELETE" }),
    upload: async (
      files: File[],
      onProgress?: (progress: string) => void,
    ): Promise<ResumeSummary[]> => {
      const form = new FormData();
      for (const f of files) form.append("files", f);
      const { job_id } = await request<{ job_id: string }>("/resumes", {
        method: "POST",
        body: form,
      });
      return onProgress
        ? pollJobWithProgress<ResumeSummary[]>(job_id, onProgress)
        : pollJob<ResumeSummary[]>(job_id);
    },
  },
  shortlist: {
    run: async (jdId: string, onProgress?: (progress: string) => void): Promise<ShortlistPayload> => {
      const { job_id } = await request<{ job_id: string }>(`/jds/${jdId}/shortlist`);
      return onProgress
        ? pollJobWithProgress<ShortlistPayload>(job_id, onProgress)
        : pollJob<ShortlistPayload>(job_id);
    },
    csvUrl: (jdId: string) => `${BASE}/jds/${jdId}/shortlist.csv`,
  },
  chat: {
    send: (jdId: string, message: string, history: ChatHistoryMessage[]) =>
      request<ChatResponse>(`/jds/${jdId}/chat`, {
        method: "POST",
        body: JSON.stringify({ message, history }),
      }),
  },
};
