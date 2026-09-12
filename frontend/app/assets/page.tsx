"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch, API } from "../../lib/api";
import WorkspaceSwitcher from "../../components/WorkspaceSwitcher";
import NotificationBell from "../../components/NotificationBell";

export default function AssetsPage() {
  const [assets, setAssets] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    load();
  }, [filter]);

  async function load() {
    setLoading(true);
    try {
      const url = filter
        ? `/api/assets?asset_type=${encodeURIComponent(filter)}&limit=50`
        : `/api/assets?limit=50`;
      const res = await apiFetch(url);
      const data = await res.json();
      setAssets(data.assets || []);
    } catch {
      setAssets([]);
    } finally {
      setLoading(false);
    }
  }

  function download(id: string, name: string) {
    window.open(`${API}/api/assets/${id}/download`, "_blank");
  }

  async function sendAsset(id: string) {
    const to = prompt("Send PDF to email (leave blank to use linked prospect email):") ?? "";
    try {
      const res = await apiFetch(`/api/assets/${id}/send`, {
        method: "POST",
        body: JSON.stringify(to.trim() ? { to_email: to.trim() } : {}),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.reason || "Send failed");
      alert(data.status === "sent" ? `Sent to ${data.to}` : (data.reason || data.status || "Done"));
    } catch (e: any) {
      alert(e.message || "Send failed – is SMTP configured?");
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="text-xl font-bold">
            <img src="/favicon.svg" alt="" width={28} height={28} className="rounded-md inline-block mr-2 align-middle" />RuffNeck <span className="text-blue-400">Prospector</span>
          </Link>
          <nav className="flex gap-4 text-sm text-slate-400 items-center">
            <Link href="/create">Create</Link>
            <Link href="/assets" className="text-white">Assets</Link>
            <Link href="/pipeline">Pipeline</Link>
            <NotificationBell />
            <WorkspaceSwitcher />
          </nav>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-10">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-8">
          <div>
            <h2 className="text-2xl font-bold">Asset Library</h2>
            <p className="text-slate-400 text-sm mt-1">Saved ebooks and implementation guides</p>
          </div>
          <div className="flex gap-2">
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm"
            >
              <option value="">All types</option>
              <option value="ebook">Ebooks</option>
              <option value="implementation_guide">Implementation guides</option>
              <option value="website_audit">Website audits</option>
            </select>
            <Link href="/create" className="bg-blue-600 hover:bg-blue-500 px-4 py-2 rounded-lg text-sm font-medium">
              + Create new
            </Link>
          </div>
        </div>

        {loading ? (
          <p className="text-slate-500">Loading…</p>
        ) : assets.length === 0 ? (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center text-slate-400 text-sm">
            No saved assets yet. Generate an ebook or implementation guide from{" "}
            <Link href="/create" className="text-blue-400 underline">Create</Link>
            {" "}or from a pipeline prospect.
          </div>
        ) : (
          <div className="space-y-2">
            {assets.map((a) => (
              <div
                key={a.id}
                className="bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 flex flex-wrap items-center justify-between gap-3"
              >
                <div>
                  <div className="font-medium">{a.title || a.file_name || "Untitled"}</div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    <span className="capitalize">{(a.asset_type || "").replace("_", " ")}</span>
                    {" · "}
                    {a.created_at ? new Date(a.created_at).toLocaleString() : ""}
                    {a.prospect_id && " · linked to prospect"}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => download(a.id, a.file_name)}
                    className="bg-slate-800 hover:bg-slate-700 px-3 py-1.5 rounded text-sm"
                  >
                    Download
                  </button>
                  <button
                    onClick={() => sendAsset(a.id)}
                    className="bg-blue-700 hover:bg-blue-600 px-3 py-1.5 rounded text-sm"
                  >
                    Email PDF
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
