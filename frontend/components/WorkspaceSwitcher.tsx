"use client";

import { useEffect, useState } from "react";
import { getActiveWorkspaceId, getActiveWorkspaceName, setActiveWorkspace } from "../lib/workspace";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function WorkspaceSwitcher() {
  const [workspaces, setWorkspaces] = useState<any[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [activeName, setActiveName] = useState<string | null>(null);

  useEffect(() => {
    setActiveId(getActiveWorkspaceId());
    setActiveName(getActiveWorkspaceName());
    fetch(`${API}/api/workspaces`, {
      headers: (() => {
        const headers: Record<string, string> = {};
        const token = localStorage.getItem("ruffneck_token");
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }
        return headers;
      })(),
    })
      .then((r) => {
        if (!r.ok) {
          throw new Error(`Workspace request failed (${r.status})`);
        }
        return r.json();
      })
      .then((d) => setWorkspaces(Array.isArray(d.workspaces) ? d.workspaces : []))
      .catch((error) => {
        console.error("Unable to load workspaces:", error);
        setWorkspaces([]);
      });
  }, []);

  function onChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const id = e.target.value || null;
    const ws = workspaces.find((w) => w.id === id);
    setActiveWorkspace(id, ws?.name);
    setActiveId(id);
    setActiveName(ws?.name || null);
    // Soft reload so pages can re-fetch with new workspace context
    window.location.reload();
  }

  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="text-slate-500 hidden sm:inline">Workspace</span>
      <select
        value={activeId || ""}
        onChange={onChange}
        className="bg-slate-900 border border-slate-700 rounded-lg px-2 py-1.5 text-xs max-w-[160px]"
      >
        <option value="">Personal / All</option>
        {workspaces.map((ws) => (
          <option key={ws.id} value={ws.id}>
            {ws.name}
          </option>
        ))}
      </select>
    </div>
  );
}
