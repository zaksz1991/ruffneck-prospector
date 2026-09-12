const WS_KEY = "ruffneck_workspace_id";
const WS_NAME_KEY = "ruffneck_workspace_name";

export function setActiveWorkspace(id: string | null, name?: string) {
  if (typeof window === "undefined") return;
  if (id) {
    localStorage.setItem(WS_KEY, id);
    if (name) localStorage.setItem(WS_NAME_KEY, name);
  } else {
    localStorage.removeItem(WS_KEY);
    localStorage.removeItem(WS_NAME_KEY);
  }
}

export function getActiveWorkspaceId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(WS_KEY);
}

export function getActiveWorkspaceName(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(WS_NAME_KEY);
}
