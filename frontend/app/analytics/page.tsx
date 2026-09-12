"use client";

import NotificationBell from "../../components/NotificationBell";
import WorkspaceSwitcher from "../../components/WorkspaceSwitcher";
import { apiFetch, API } from "../../lib/api";
import { getActiveWorkspaceId } from "../../lib/workspace";

import { useEffect, useState } from "react";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function AnalyticsPage() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const ws = getActiveWorkspaceId();
    const q = ws ? `?workspace_id=${encodeURIComponent(ws)}` : "";
    apiFetch(`/api/analytics${q}`)
      .then(r => r.json())
      .then(setStats)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="min-h-screen bg-slate-950 text-slate-400 p-10">Loading analytics…</div>;
  if (!stats) return <div className="min-h-screen bg-slate-950 text-slate-400 p-10">No data yet.</div>;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="text-xl font-bold">
            <img src="/favicon.svg" alt="" width={28} height={28} className="rounded-md inline-block mr-2 align-middle" />RuffNeck <span className="text-blue-400">Prospector</span>
          </Link>
          <nav className="flex gap-5 text-sm text-slate-400">
            <Link href="/discover">Discover</Link>
            <Link href="/prospects">Prospects</Link>
            <Link href="/pipeline">Pipeline</Link>
            <Link href="/sequences" className="hover:text-white transition">Sequences</Link>
            <Link href="/team" className="hover:text-white transition">Team</Link>
            <Link href="/analytics" className="text-white">Analytics</Link>
          <NotificationBell />
            <WorkspaceSwitcher />
          </nav>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-10">
        <h2 className="text-2xl font-bold mb-8">Analytics Dashboard</h2>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
          {[
            { label: "Total Prospects", value: stats.total_prospects },
            { label: "With Email", value: `${stats.with_email} (${stats.email_rate}%)` },
            { label: "High Intent (≥70)", value: stats.high_intent },
            { label: "Replied", value: stats.replied },
            { label: "Won", value: stats.won },
          ].map((c) => (
            <div key={c.label} className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <div className="text-2xl font-bold text-blue-400">{c.value}</div>
              <div className="text-sm text-slate-400 mt-1">{c.label}</div>
            </div>
          ))}
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h3 className="font-semibold mb-4">By Platform</h3>
            <div className="space-y-2">
              {Object.entries(stats.by_platform || {}).map(([k, v]: any) => (
                <div key={k} className="flex justify-between text-sm">
                  <span className="capitalize text-slate-300">{k}</span>
                  <span className="font-mono">{v}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h3 className="font-semibold mb-4">By Pipeline Stage</h3>
            <div className="space-y-2">
              {Object.entries(stats.by_status || {}).map(([k, v]: any) => (
                <div key={k} className="flex justify-between text-sm">
                  <span className="capitalize text-slate-300">{k}</span>
                  <span className="font-mono">{v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
