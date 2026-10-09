import { getToken } from "./auth";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function apiUrl(path: string): string {
  if (path.startsWith("http")) return path;
  return `${API}${path.startsWith("/") ? path : "/" + path}`;
}

/** fetch wrapper that attaches Authorization Bearer when logged in */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers || {});
  if (!headers.has("Content-Type") && init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const token = getToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return fetch(apiUrl(path), { ...init, headers });
}

export { API };
