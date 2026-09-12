"use client";

import NotificationBell from "../../components/NotificationBell";
import WorkspaceSwitcher from "../../components/WorkspaceSwitcher";
import { getActiveWorkspaceId } from "../../lib/workspace";
import { apiFetch, API } from "../../lib/api";

import { useEffect, useState } from "react";
import Link from "next/link";

interface Prospect {
  id: string;
  platform: string;
  username: string;
  display_name?: string;
  comment_text: string;
  intent_score: number;
  follower_count: number;
  status: string;
  email?: string;
  email_confidence?: number;
  metadata?: {
    enrichment_status?: string;
    company_domain?: string;
    email_source?: string;
    score_breakdown?: any;
    recommended_service?: string;
  };
  created_at: string;
}

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ProspectsPage() {
  const [prospects, setProspects] = useState<Prospect[]>([]);
  const [loading, setLoading] = useState(true);
  const [platform, setPlatform] = useState("");
  const [minScore, setMinScore] = useState(0);
  const [enriching, setEnriching] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [autoEnriching, setAutoEnriching] = useState(false);
  const [sequences, setSequences] = useState<any[]>([]);
  const [enrolling, setEnrolling] = useState(false);
  const [verifying, setVerifying] = useState(false);

  useEffect(() => {
    fetchProspects();
    apiFetch(`/api/sequences`).then(r => r.json()).then(d => setSequences(d.sequences || [])).catch(() => {});
  }, [platform, minScore]);

  async function fetchProspects() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (platform) params.set("platform", platform);
      if (minScore) params.set("min_score", String(minScore));
      const ws = getActiveWorkspaceId();
      if (ws) params.set("workspace_id", ws);
      const res = await apiFetch(`/api/prospects?${params}`);
      const json = await res.json();
      setProspects(json.data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function enrichSelected() {
    const ids = prospects.slice(0, 30).map((p) => p.id);
    if (!ids.length) return;
    setEnriching(true);
    try {
      await apiFetch(`/api/prospects/enrich`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prospect_ids: ids }),
      });
      setTimeout(fetchProspects, 4000);
    } catch (e) {
      console.error(e);
    } finally {
      setEnriching(false);
    }
  }

  async function detectTechForRow(id: string) {
    try {
      const res = await apiFetch(`/api/prospects/${id}/detect-tech`, { method: "POST" });
      const data = await res.json();
      alert(data.ok ? `Tech: ${(data.technologies || []).join(", ") || "unknown"}\n${data.pitch_hint || ""}` : (data.error || "Failed"));
      fetchProspects();
    } catch {
      alert("Tech detect failed");
    }
  }

  async function verifyEmails() {
    const ids = prospects.filter(p => p.email).slice(0, 40).map(p => p.id);
    if (!ids.length) {
      alert("No emails to verify on current list");
      return;
    }
    setVerifying(true);
    try {
      await apiFetch(`/api/prospects/verify-batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prospect_ids: ids }),
      });
      setTimeout(fetchProspects, 2000);
      alert("Verification started – refresh in a moment");
    } catch {
      alert("Verify failed");
    } finally {
      setVerifying(false);
    }
  }

  async function enrollInSequence(sequenceId: string) {
    const ids = prospects.filter(p => p.email).slice(0, 25).map(p => p.id);
    if (!ids.length) {
      alert("No prospects with email on the current list.");
      return;
    }
    setEnrolling(true);
    try {
      const res = await apiFetch(`/api/sequences/enroll`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sequence_id: sequenceId, prospect_ids: ids }),
      });
      const data = await res.json();
      alert(`Enrolled ${data.count || ids.length} prospects in sequence`);
    } catch {
      alert("Enroll failed");
    } finally {
      setEnrolling(false);
    }
  }

  async function autoEnrich() {
    setAutoEnriching(true);
    try {
      const res = await apiFetch(`/api/prospects/auto-enrich?limit=40`, { method: "POST" });
      const data = await res.json();
      // Poll a bit then refresh
      setTimeout(fetchProspects, 5000);
      alert("Auto-enrich started. Prospects will update shortly.");
    } catch (e) {
      console.error(e);
      alert("Auto-enrich failed to start");
    } finally {
      setAutoEnriching(false);
    }
  }

  async function exportExcel() {
    setExporting(true);
    try {
      const params = new URLSearchParams();
      if (platform) params.set("platform", platform);
      if (minScore) params.set("min_score", String(minScore));
      params.set("limit", "500");
      const ws = getActiveWorkspaceId();
      if (ws) params.set("workspace_id", ws);

      const res = await apiFetch(`/api/prospects/export?${params}`);
      if (!res.ok) throw new Error("Export failed");

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `RuffNeck_Leads_${new Date().toISOString().slice(0, 10)}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      console.error(e);
      alert("Export failed. Is the API running and openpyxl installed?");
    } finally {
      setExporting(false);
    }
  }

  function enrichmentBadge(p: Prospect) {
    const status = p.metadata?.enrichment_status || (p.email ? "email_found" : "none");
    const conf = p.email_confidence || 0;
    if (status === "email_found" || (p.email && conf >= 70)) {
      return <span className="text-xs px-2 py-0.5 rounded bg-emerald-900/40 text-emerald-400">Email ✓</span>;
    }
    if (status === "email_guessed" || (p.email && conf < 70)) {
      return <span className="text-xs px-2 py-0.5 rounded bg-yellow-900/40 text-yellow-400">Email ~</span>;
    }
    if (status === "domain_found" || p.metadata?.company_domain) {
      return <span className="text-xs px-2 py-0.5 rounded bg-blue-900/40 text-blue-400">Domain</span>;
    }
    if (status === "patterns_generated") {
      return <span className="text-xs px-2 py-0.5 rounded bg-slate-700 text-slate-300">Patterns</span>;
    }
    return <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-500">—</span>;
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="text-xl font-bold">
            <img src="/favicon.svg" alt="" width={28} height={28} className="rounded-md inline-block mr-2 align-middle" />RuffNeck <span className="text-blue-400">Prospector</span>
          </Link>
          <nav className="flex gap-6 text-sm text-slate-400">
            <Link href="/discover">Discover</Link>
            <Link href="/prospects" className="text-white">Prospects</Link>
            <Link href="/pipeline" className="hover:text-white transition">Pipeline</Link>
            <Link href="/sequences" className="hover:text-white transition">Sequences</Link>
            <Link href="/team" className="hover:text-white transition">Team</Link>
            <Link href="/analytics" className="hover:text-white transition">Analytics</Link>
            <Link href="/campaigns">Campaigns</Link>
            <Link href="/generate">Generate</Link>
          <NotificationBell />
            <WorkspaceSwitcher />
          </nav>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8">
        <div className="flex flex-wrap gap-4 mb-6 items-end justify-between">
          <div className="flex flex-wrap gap-4 items-end">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Platform</label>
              <select
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
                className="bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm"
              >
                <option value="">All</option>
                <option value="linkedin">LinkedIn</option>
                <option value="jobs">Jobs</option>
                <option value="maps">Maps</option>
                <option value="google">Google</option>
                <option value="instagram">Instagram</option>
                <option value="twitter">Twitter / X</option>
                <option value="reddit">Reddit</option>
                <option value="youtube">YouTube</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Min Score</label>
              <input
                type="number"
                min={0}
                max={100}
                value={minScore}
                onChange={(e) => setMinScore(Number(e.target.value))}
                className="bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm w-24"
              />
            </div>
            <button onClick={fetchProspects} className="bg-slate-800 hover:bg-slate-700 px-4 py-2 rounded text-sm">
              Refresh
            </button>
          </div>

          <div className="flex gap-3 flex-wrap">
            <button
              onClick={enrichSelected}
              disabled={enriching || prospects.length === 0}
              className="bg-emerald-700 hover:bg-emerald-600 disabled:opacity-50 px-4 py-2 rounded text-sm font-medium"
            >
              {enriching ? "Enriching…" : "Enrich visible"}
            </button>
            <button
              onClick={autoEnrich}
              disabled={autoEnriching}
              className="bg-violet-700 hover:bg-violet-600 disabled:opacity-50 px-4 py-2 rounded text-sm font-medium"
              title="Automatically find and enrich prospects that still need email / domain data"
            >
              {autoEnriching ? "Auto-enriching…" : "⚡ Auto-Enrich New"}
            </button>
            <button
              onClick={verifyEmails}
              disabled={verifying || prospects.length === 0}
              className="bg-amber-700 hover:bg-amber-600 disabled:opacity-50 px-4 py-2 rounded text-sm font-medium"
            >
              {verifying ? "Verifying…" : "Verify Emails"}
            </button>
            {sequences.length > 0 && (
              <select
                disabled={enrolling || prospects.length === 0}
                onChange={(e) => {
                  if (e.target.value) enrollInSequence(e.target.value);
                  e.target.value = "";
                }}
                className="bg-violet-800 hover:bg-violet-700 disabled:opacity-50 px-3 py-2 rounded text-sm border-0 cursor-pointer"
                defaultValue=""
              >
                <option value="" disabled>{enrolling ? "Enrolling…" : "Enroll in Sequence…"}</option>
                {sequences.map((s: any) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            )}
            <button
              onClick={exportExcel}
              disabled={exporting || prospects.length === 0}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 px-4 py-2 rounded text-sm font-medium flex items-center gap-2"
            >
              {exporting ? "Exporting…" : "⬇ Export to Excel"}
            </button>
          </div>
        </div>

        {loading ? (
          <p className="text-slate-400">Loading…</p>
        ) : prospects.length === 0 ? (
          <div className="text-center py-20 text-slate-500">
            <p className="text-lg mb-2">No prospects yet</p>
            <p className="text-sm">
              Go to <Link href="/discover" className="text-blue-400 underline">Discover</Link> and run Daily Discovery or a targeted search.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto border border-slate-800 rounded-xl">
            <table className="w-full text-sm">
              <thead className="bg-slate-900 text-slate-400">
                <tr>
                  <th className="text-left p-3">Platform</th>
                  <th className="text-left p-3">User / Company</th>
                  <th className="text-left p-3">Comment / Snippet</th>
                  <th className="text-left p-3">Score</th>
                  <th className="text-left p-3">Enrichment</th>
                  <th className="text-left p-3">Email</th>
                  <th className="text-left p-3">Status</th>
                  <th className="text-left p-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {prospects.map((p) => (
                  <tr key={p.id} className="border-t border-slate-800 hover:bg-slate-900/50">
                    <td className="p-3 capitalize">{p.platform}</td>
                    <td className="p-3">
                      <div className="font-medium">@{p.username}</div>
                      {p.display_name && <div className="text-xs text-slate-500">{p.display_name}</div>}
                      {p.metadata?.company_domain && (
                        <div className="text-xs text-blue-400">{p.metadata.company_domain}</div>
                      )}
                    </td>
                    <td className="p-3 max-w-xs truncate text-slate-300" title={p.comment_text}>
                      {p.comment_text}
                    </td>
                    <td className="p-3">
                      <span className={`font-mono ${p.intent_score >= 70 ? "text-green-400" : p.intent_score >= 40 ? "text-yellow-400" : "text-slate-400"}`}>
                        {p.intent_score}
                      </span>
                    </td>
                    <td className="p-3">{enrichmentBadge(p)}</td>
                    <td className="p-3 text-xs">
                      {p.email ? (
                        <span title={`Source: ${p.metadata?.email_source || "?"} • Confidence: ${p.email_confidence || "?"}`}>
                          {p.email}
                        </span>
                      ) : (
                        <span className="text-slate-600">—</span>
                      )}
                    </td>
                    <td className="p-3 capitalize text-slate-400">{p.status}</td>
                    <td className="p-3">
                      <button
                        onClick={() => detectTechForRow(p.id)}
                        className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300"
                        title="Detect website technology"
                      >
                        Tech
                      </button>
                      {p.metadata?.tech?.technologies?.length > 0 && (
                        <div className="text-[10px] text-slate-500 mt-1 max-w-[100px] truncate" title={(p.metadata.tech.technologies || []).join(", ")}>
                          {(p.metadata.tech.technologies || []).slice(0, 2).join(", ")}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
