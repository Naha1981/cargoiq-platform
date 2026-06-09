/**
 * CargoIQ API client — typed fetch wrapper.
 * All calls go through here for consistent auth + error handling.
 */
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function apiFetch<T>(
  path: string,
  options: RequestInit & { token?: string } = {}
): Promise<T> {
  const { token, ...fetchOptions } = options;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(fetchOptions.headers as Record<string, string> || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  } else {
    // Try to get token from localStorage
    const stored = typeof window !== "undefined"
      ? localStorage.getItem("cargoiq_token")
      : null;
    if (stored) headers["Authorization"] = `Bearer ${stored}`;
  }

  const res = await fetch(`${API_URL}/api/v1${path}`, {
    ...fetchOptions,
    headers,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail || "Request failed");
  }

  // Handle 204 No Content
  if (res.status === 204) return null as T;
  return res.json();
}

// ---- Auth ----
export const authApi = {
  signUp: (data: { email: string; password: string; full_name: string; org_name: string }) =>
    apiFetch<any>("/auth/signup", { method: "POST", body: JSON.stringify(data) }),

  signIn: (data: { email: string; password: string }) =>
    apiFetch<any>("/auth/signin", { method: "POST", body: JSON.stringify(data) }),

  me: () => apiFetch<any>("/auth/me"),
};

// ---- Documents ----
export const documentsApi = {
  upload: async (file: File): Promise<any> => {
    const token = localStorage.getItem("cargoiq_token");
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_URL}/api/v1/documents/upload`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(res.status, err.detail || "Upload failed");
    }
    return res.json();
  },

  get: (id: string, includeText = false) =>
    apiFetch<any>(`/documents/${id}?include_text=${includeText}`),

  list: (page = 1, limit = 20) =>
    apiFetch<any>(`/documents/?page=${page}&limit=${limit}`),

  reprocess: (id: string) =>
    apiFetch<any>(`/documents/${id}/reprocess`, { method: "POST" }),
};

// ---- Shipments ----
export const shipmentsApi = {
  list: (params: {
    page?: number; limit?: number; status?: string;
    confidence?: string; shield?: string; search?: string;
  } = {}) => {
    const q = new URLSearchParams();
    if (params.page)       q.set("page", String(params.page));
    if (params.limit)      q.set("limit", String(params.limit));
    if (params.status)     q.set("status", params.status);
    if (params.confidence) q.set("confidence", params.confidence);
    if (params.shield)     q.set("shield", params.shield);
    if (params.search)     q.set("search", params.search);
    return apiFetch<any>(`/shipments/?${q}`);
  },

  get: (id: string) => apiFetch<any>(`/shipments/${id}`),

  createFromDocuments: (documentIds: string[]) =>
    apiFetch<any>("/shipments/from-documents", {
      method: "POST",
      body: JSON.stringify(documentIds),
    }),

  update: (id: string, data: Record<string, any>) =>
    apiFetch<any>(`/shipments/${id}`, { method: "PATCH", body: JSON.stringify(data) }),

  approve: (id: string, notes?: string, acknowledgedRisks = false) =>
    apiFetch<any>(`/shipments/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ notes, acknowledged_risks: acknowledgedRisks }),
    }),

  reject: (id: string, reason: string) =>
    apiFetch<any>(`/shipments/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),

  audit: (id: string) => apiFetch<any>(`/shipments/${id}/audit`),
};

// ---- Analytics ----
export const analyticsApi = {
  dashboard:          () => apiFetch<any>("/analytics/dashboard"),
  volume:     (days = 30) => apiFetch<any>(`/analytics/volume?days=${days}`),
  compliance: (days = 30) => apiFetch<any>(`/analytics/compliance-summary?days=${days}`),
  roi:                () => apiFetch<any>("/analytics/roi"),
};

// ---- Compliance ----
export const complianceApi = {
  audit:    (shipmentId: string) =>
    apiFetch<any>("/compliance/audit", { method: "POST", body: JSON.stringify(shipmentId) }),
  events:   (shipmentId: string) => apiFetch<any>(`/compliance/events/${shipmentId}`),
  resolve:  (eventId: string, note: string) =>
    apiFetch<any>(`/compliance/events/${eventId}/resolve`, {
      method: "POST", body: JSON.stringify(note),
    }),
  rla:      () => apiFetch<any>("/compliance/rla-statuses"),
};

export { ApiError };

// ---- Generic API client for new endpoints ----
export const apiClient = {
  get: async <T = any>(path: string): Promise<T> => apiFetch<T>(path),
  post: async <T = any>(path: string, data: any): Promise<T> =>
    apiFetch<T>(path, { method: "POST", body: JSON.stringify(data) }),
  patch: async <T = any>(path: string, data: any): Promise<T> =>
    apiFetch<T>(path, { method: "PATCH", body: JSON.stringify(data) }),
  delete: async <T = any>(path: string): Promise<T> =>
    apiFetch<T>(path, { method: "DELETE" }),
};
