"use client";

import NotificationBell from "../../components/NotificationBell";
import WorkspaceSwitcher from "../../components/WorkspaceSwitcher";
import { getActiveWorkspaceId } from "../../lib/workspace";
import { apiFetch, API } from "../../lib/api";

import { useEffect, useState } from "react";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const STAGES = ["new", "contacted", "replied", "meeting", "won", "lost"];

const stageColors: Record<string, string> = {
  new: "border-slate-600",
  contacted: "border-blue-600",
  replied: "border-emerald-600",
  meeting: "border-violet-600",
  won: "border-green-500",
  lost: "border-red-700",
};

export default function PipelinePage() {
  const [board, setBoard] = useState<Record<string, any[]>>({});
  const [loading, setLoading] = useState(true);
  const [sequences, setSequences] = useState<any[]>([]);
  const [checkingReplies, setCheckingReplies] = useState(false);
  const [timeline, setTimeline] = useState<any[] | null>(null);
  const [timelineFor, setTimelineFor] = useState<string | null>(null);
  const [guideFor, setGuideFor] = useState<any | null>(null);
  const [guideForm, setGuideForm] = useState({ business_name: "", industry: "", goals: "", current_situation: "", services: "", notes: "" });
  const [guideLoading, setGuideLoading] = useState(false);
  const [mobileStage, setMobileStage] = useState<string>("new");
  const [auditLoading, setAuditLoading] = useState<string | null>(null);

  useEffect(() => {
    load();
    apiFetch(`/api/sequences`).then(r => r.json()).then(d => setSequences(d.sequences || [])).catch(() => {});
  }, []);

  async function load() {
    setLoading(true);
    try {
      const ws = getActiveWorkspaceId();
      const q = ws ? `?workspace_id=${encodeURIComponent(ws)}` : "";
      const res = await apiFetch(`/api/pipeline${q}`);
      const data = await res.json();
      setBoard(data.board || {});
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function moveTo(prospectId: string, stage: string) {
    await apiFetch(`/api/pipeline/move`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prospect_ids: [prospectId], stage }),
    });
    load();
  }

  function openGuide(p: any) {
    setGuideFor(p);
    setGuideForm({
      business_name: p.display_name || p.username || "",
      industry: p.platform === "maps" ? "local business" : (p.metadata?.industry || ""),
      goals: "",
      current_situation: (p.comment_text || p.bio_text || "").slice(0, 300),
      services: "",
      notes: [p.email, p.metadata?.company_domain, p.profile_url].filter(Boolean).join(" · "),
    });
  }

  async function submitGuide(e: React.FormEvent) {
    e.preventDefault();
    if (!guideFor) return;
    setGuideLoading(true);
    try {
      const res = await apiFetch(`/api/generate/implementation-guide`, {
        method: "POST",
        body: JSON.stringify({
          ...guideForm,
          prospect_id: guideFor.id,
          company_name: "RuffNeck Consulting",
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Implementation_${(guideForm.business_name || "guide").slice(0, 30)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      // Offer to email if we have asset id header + prospect email
      const assetId = res.headers.get("X-Asset-Id");
      if (assetId && guideFor?.email) {
        const send = confirm(`Guide saved. Email PDF to ${guideFor.email}?`);
        if (send) {
          const sendRes = await apiFetch(`/api/assets/${assetId}/send`, {
            method: "POST",
            body: JSON.stringify({ to_email: guideFor.email }),
          });
          const sendData = await sendRes.json();
          alert(sendData.status === "sent" ? `Emailed to ${guideFor.email}` : (sendData.detail || sendData.reason || "Send status unknown"));
        }
      }
      setGuideFor(null);
    } catch (err: any) {
      alert(err.message || "Guide generation failed");
    } finally {
      setGuideLoading(false);
    }
  }

  async function assignLead(prospectId: string) {
    const who = prompt("Assign to (name or email):");
    if (!who || !who.trim()) return;
    try {
      await apiFetch(`/api/prospects/assign`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prospect_ids: [prospectId], assigned_to: who.trim() }),
      });
      load();
    } catch {
      alert("Assign failed");
    }
  }

  async function downloadAudit(p: any) {
    setAuditLoading(p.id);
    try {
      const res = await apiFetch(`/api/generate/website-audit`, {
        method: "POST",
        body: JSON.stringify({
          prospect_id: p.id,
          business_name: p.display_name || p.username || "",
          company_name: "RuffNeck",
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Audit_${(p.display_name || "site").slice(0, 20)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      const assetId = res.headers.get("X-Asset-Id");
      if (assetId && p.email && confirm("Audit saved. Email PDF to prospect?")) {
        await apiFetch(`/api/assets/${assetId}/send`, {
          method: "POST",
          body: JSON.stringify({ to_email: p.email }),
        });
        alert("Audit emailed");
      }
    } catch (e: any) {
      alert(e.message || "Audit failed – prospect needs a website URL");
    } finally {
      setAuditLoading(null);
    }
  }

  async function seedDemo() {
    try {
      const res = await apiFetch(`/api/demo/seed`, { method: "POST" });
      const data = await res.json();
      alert(data.message || `Loaded ${data.inserted} demo leads`);
      load();
    } catch {
      alert("Demo seed failed");
    }
  }

  async function checkReplies() {
    setCheckingReplies(true);
    try {
      await apiFetch(`/api/replies/check`, { method: "POST" });
      alert("Reply check started. Refresh pipeline in a minute.");
      setTimeout(load, 5000);
    } catch {
      alert("Reply check failed");
    } finally {
      setCheckingReplies(false);
    }
  }

  async function showTimeline(prospectId: string) {
    setTimelineFor(prospectId);
    try {
      const res = await apiFetch(`/api/prospects/${prospectId}/activities`);
      const data = await res.json();
      setTimeline(data.activities || []);
    } catch {
      setTimeline([]);
    }
  }

  async function enrollOne(prospectId: string, sequenceId: string) {
    try {
      await apiFetch(`/api/sequences/enroll`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sequence_id: sequenceId, prospect_ids: [prospectId] }),
      });
      alert("Enrolled in sequence");
    } catch {
      alert("Enroll failed");
    }
  }

  async function logReply(prospectId: string) {
    const body = prompt("Paste reply content (optional):") || "Reply received";
    await apiFetch(`/api/replies`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prospect_id: prospectId,
        channel: "email",
        direction: "inbound",
        body,
      }),
    });
    load();
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="text-xl font-bold">
            <img src="/favicon.svg" alt="" width={28} height={28} className="rounded-md inline-block mr-2 align-middle" />RuffNeck <span className="text-blue-400">Prospector</span>
          </Link>
          <nav className="flex gap-5 text-sm text-slate-400">
            <Link href="/discover">Discover</Link>
            <Link href="/prospects">Prospects</Link>
            <Link href="/pipeline" className="text-white">Pipeline</Link>
            <Link href="/sequences" className="hover:text-white transition">Sequences</Link>
            <Link href="/team" className="hover:text-white transition">Team</Link>
            <Link href="/analytics">Analytics</Link>
            <Link href="/campaigns">Campaigns</Link>
          <NotificationBell />
            <WorkspaceSwitcher />
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
          <h2 className="text-2xl font-bold">Pipeline</h2>
          <div className="flex flex-wrap gap-2">
            <button onClick={seedDemo} className="text-sm bg-violet-800 px-3 py-1.5 rounded">
              Load demo
            </button>
            <button onClick={checkReplies} disabled={checkingReplies} className="text-sm bg-emerald-800 px-3 py-1.5 rounded disabled:opacity-50">
              {checkingReplies ? "Checking…" : "Check Replies"}
            </button>
            <button onClick={load} className="text-sm bg-slate-800 px-3 py-1.5 rounded">Refresh</button>
          </div>
        </div>

        {loading ? (
          <p className="text-slate-400">Loading pipeline…</p>
        ) : (
          <>
          {/* Mobile stage tabs */}
          <div className="flex gap-1 overflow-x-auto pb-3 md:hidden -mx-1 px-1">
            {STAGES.map((stage) => (
              <button
                key={stage}
                onClick={() => setMobileStage(stage)}
                className={`flex-shrink-0 px-3 py-1.5 rounded-full text-xs capitalize border ${
                  mobileStage === stage
                    ? "bg-blue-600 border-blue-500 text-white"
                    : "bg-slate-900 border-slate-700 text-slate-400"
                }`}
              >
                {stage} {(board[stage] || []).length}
              </button>
            ))}
          </div>

          <div className="flex gap-3 overflow-x-auto pb-4 md:grid md:grid-cols-3 lg:grid-cols-6 md:overflow-visible">
            {STAGES.map((stage) => (
              <div
                key={stage}
                className={`flex-shrink-0 w-[85vw] max-w-xs md:w-auto md:max-w-none bg-slate-900 border ${stageColors[stage]} rounded-xl ${
                  mobileStage !== stage ? "hidden md:block" : ""
                }`}
              >
                <div className="px-3 py-2 border-b border-slate-800 flex justify-between items-center sticky top-0 bg-slate-900 rounded-t-xl z-10">
                  <span className="font-medium capitalize text-sm">{stage}</span>
                  <span className="text-xs text-slate-500">{(board[stage] || []).length}</span>
                </div>
                <div className="p-2 space-y-2 max-h-[70vh] overflow-y-auto">
                  {(board[stage] || []).map((p: any) => (
                    <div key={p.id} className="bg-slate-950 border border-slate-800 rounded-lg p-3 text-sm">
                      <div className="font-medium truncate">{p.display_name || p.username}</div>
                      <div className="text-xs text-slate-500 capitalize mt-0.5">{p.platform} · Score {p.intent_score}</div>
                      {p.email && <div className="text-xs text-emerald-400 mt-1 truncate">{p.email}</div>}
                      {p.assigned_to && <div className="text-xs text-amber-400/90 mt-0.5">→ {p.assigned_to}</div>}
                      <p className="text-xs text-slate-400 mt-1 line-clamp-2">{p.comment_text}</p>
                      <div className="flex flex-wrap gap-1 mt-2">
                        {STAGES.filter(s => s !== stage).slice(0, 3).map(s => (
                          <button
                            key={s}
                            onClick={() => moveTo(p.id, s)}
                            className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 hover:bg-slate-700 capitalize"
                          >
                            → {s}
                          </button>
                        ))}
                        {stage !== "replied" && stage !== "won" && (
                          <button
                            onClick={() => logReply(p.id)}
                            className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-900/50 text-emerald-400"
                          >
                            Log reply
                          </button>
                        )}
                        {sequences.length > 0 && p.email && (
                          <select
                            className="text-[10px] bg-slate-800 border-0 rounded px-1 py-0.5 max-w-[90px]"
                            defaultValue=""
                            onChange={(e) => {
                              if (e.target.value) enrollOne(p.id, e.target.value);
                              e.target.value = "";
                            }}
                          >
                            <option value="" disabled>Enroll…</option>
                            {sequences.map((s: any) => (
                              <option key={s.id} value={s.id}>{s.name}</option>
                            ))}
                          </select>
                        )}
                        <button
                          onClick={() => showTimeline(p.id)}
                          className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300"
                        >
                          Timeline
                        </button>
                        <button
                          onClick={() => assignLead(p.id)}
                          className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300"
                        >
                          Assign
                        </button>
                        <button
                          onClick={() => openGuide(p)}
                          className="text-[10px] px-1.5 py-0.5 rounded bg-teal-900/50 text-teal-300"
                        >
                          Guide
                        </button>
                        <button
                          onClick={() => downloadAudit(p)}
                          disabled={auditLoading === p.id}
                          className="text-[10px] px-1.5 py-0.5 rounded bg-amber-900/40 text-amber-300 disabled:opacity-50"
                        >
                          {auditLoading === p.id ? "…" : "Audit"}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
          </>
        )}

        {guideFor && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={() => setGuideFor(null)}>
            <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-lg w-full max-h-[85vh] overflow-y-auto p-5" onClick={(e) => e.stopPropagation()}>
              <div className="flex justify-between items-center mb-4">
                <h3 className="font-semibold">Implementation guide</h3>
                <button onClick={() => setGuideFor(null)} className="text-slate-400 text-sm">Close</button>
              </div>
              <p className="text-xs text-slate-500 mb-4">Prefills from prospect. Add consultation details, then generate a branded PDF (saved to Assets).</p>
              <form onSubmit={submitGuide} className="space-y-3">
                {(["business_name", "industry", "goals", "current_situation", "services", "notes"] as const).map((field) => (
                  <div key={field}>
                    <label className="block text-[10px] text-slate-500 mb-0.5 capitalize">{field.replace("_", " ")}</label>
                    {field === "goals" || field === "current_situation" || field === "services" || field === "notes" ? (
                      <textarea
                        value={(guideForm as any)[field]}
                        onChange={(e) => setGuideForm({ ...guideForm, [field]: e.target.value })}
                        rows={2}
                        className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-sm"
                      />
                    ) : (
                      <input
                        value={(guideForm as any)[field]}
                        onChange={(e) => setGuideForm({ ...guideForm, [field]: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-sm"
                        required={field === "business_name"}
                      />
                    )}
                  </div>
                ))}
                <button type="submit" disabled={guideLoading}
                  className="w-full bg-teal-700 hover:bg-teal-600 disabled:opacity-50 py-2.5 rounded-lg text-sm font-medium">
                  {guideLoading ? "Generating…" : "Generate & download PDF"}
                </button>
              </form>
            </div>
          </div>
        )}

        {timelineFor && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={() => { setTimelineFor(null); setTimeline(null); }}>
            <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-lg w-full max-h-[70vh] overflow-y-auto p-5" onClick={(e) => e.stopPropagation()}>
              <div className="flex justify-between items-center mb-4">
                <h3 className="font-semibold">Activity Timeline</h3>
                <button onClick={() => { setTimelineFor(null); setTimeline(null); }} className="text-slate-400 text-sm">Close</button>
              </div>
              {!timeline || timeline.length === 0 ? (
                <p className="text-sm text-slate-500">No activities yet. Replies and sent emails will appear here.</p>
              ) : (
                <ul className="space-y-3">
                  {timeline.map((a: any) => (
                    <li key={a.id} className="border border-slate-800 rounded-lg p-3 text-sm">
                      <div className="flex justify-between gap-2">
                        <span className="font-medium capitalize">{a.activity_type}</span>
                        <span className="text-xs text-slate-500">{a.created_at ? new Date(a.created_at).toLocaleString() : ""}</span>
                      </div>
                      <div className="text-slate-300 mt-1">{a.title}</div>
                      {a.body && <p className="text-xs text-slate-500 mt-1 line-clamp-3 whitespace-pre-wrap">{a.body}</p>}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

