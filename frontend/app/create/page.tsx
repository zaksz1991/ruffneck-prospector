"use client";

import { useState } from "react";
import Link from "next/link";
import { apiFetch, API } from "../../lib/api";
import WorkspaceSwitcher from "../../components/WorkspaceSwitcher";
import NotificationBell from "../../components/NotificationBell";

export default function CreatePage() {
  const [tab, setTab] = useState<"ebook" | "guide" | "audit">("ebook");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Ebook
  const [title, setTitle] = useState("");
  const [subtitle, setSubtitle] = useState("");
  const [audience, setAudience] = useState("business owners and professionals");
  const [brand, setBrand] = useState("RuffNeck");
  const [accent, setAccent] = useState("#1e3a5f");

  // Implementation guide
  const [bizName, setBizName] = useState("");
  const [industry, setIndustry] = useState("");
  const [goals, setGoals] = useState("");
  const [current, setCurrent] = useState("");
  const [services, setServices] = useState("");
  const [notes, setNotes] = useState("");
  const [guideBrand, setGuideBrand] = useState("RuffNeck Consulting");
  const [auditUrl, setAuditUrl] = useState("");
  const [auditName, setAuditName] = useState("");

  async function downloadBlob(res: Response, fallbackName: string) {
    if (!res.ok) {
      const t = await res.text();
      throw new Error(t || `HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = fallbackName;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function handleEbook(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/api/generate/ebook`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          subtitle,
          audience,
          company_name: brand,
          accent_color: accent,
          chapters: 6,
        }),
      });
      await downloadBlob(res, `${title.slice(0, 40).replace(/\s+/g, "_") || "ebook"}.pdf`);
    } catch (err: any) {
      setError(err.message || "Generation failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleGuide(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/api/generate/implementation-guide`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          business_name: bizName,
          industry,
          goals,
          current_situation: current,
          services,
          notes,
          company_name: guideBrand,
          accent_color: "#0f766e",
        }),
      });
      await downloadBlob(res, `Implementation_${bizName.slice(0, 30).replace(/\s+/g, "_") || "guide"}.pdf`);
    } catch (err: any) {
      setError(err.message || "Generation failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="text-xl font-bold">
            <img src="/favicon.svg" alt="" width={28} height={28} className="rounded-md inline-block mr-2 align-middle" />RuffNeck <span className="text-blue-400">Prospector</span>
          </Link>
          <nav className="flex gap-4 text-sm text-slate-400 items-center">
            <Link href="/discover">Discover</Link>
            <Link href="/prospects">Prospects</Link>
            <Link href="/pipeline">Pipeline</Link>
            <Link href="/create" className="text-white">Create</Link>
            <Link href="/assets">Assets</Link>
            <NotificationBell />
            <WorkspaceSwitcher />
          </nav>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-10">
        <h2 className="text-2xl font-bold mb-2">Create Documents</h2>
        <p className="text-slate-400 text-sm mb-6">
          Generate branded PDF ebooks from a title, or step-by-step implementation guides from consultation notes.
          Optional: set <code className="text-slate-300">GROQ_API_KEY</code> for richer AI-written content (free tier).
        </p>

        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setTab("ebook")}
            className={`px-4 py-2 rounded-lg text-sm ${tab === "ebook" ? "bg-blue-600 text-white" : "bg-slate-800 text-slate-300"}`}
          >
            Digital Ebook / PDF
          </button>
          <button
            onClick={() => setTab("guide")}
            className={`px-4 py-2 rounded-lg text-sm ${tab === "guide" ? "bg-emerald-700 text-white" : "bg-slate-800 text-slate-300"}`}
          >
            Implementation Guide
          </button>
          <button
            onClick={() => setTab("audit")}
            className={`px-4 py-2 rounded-lg text-sm ${tab === "audit" ? "bg-amber-700 text-white" : "bg-slate-800 text-slate-300"}`}
          >
            Website Audit
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-950/50 border border-red-800 rounded text-sm text-red-300">{error}</div>
        )}

        {tab === "ebook" && (
          <form onSubmit={handleEbook} className="space-y-4 bg-slate-900 border border-slate-800 rounded-xl p-6">
            <h3 className="font-semibold text-lg">Branded ebook from a title</h3>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Ebook title *</label>
              <input required value={title} onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. 7-Day Local Business Visibility Plan"
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm" />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Subtitle</label>
              <input value={subtitle} onChange={(e) => setSubtitle(e.target.value)}
                placeholder="A practical guide for owners who want more customers"
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm" />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Audience</label>
              <input value={audience} onChange={(e) => setAudience(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Brand / author name</label>
                <input value={brand} onChange={(e) => setBrand(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm" />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Accent color</label>
                <input type="color" value={accent} onChange={(e) => setAccent(e.target.value)}
                  className="w-full h-10 bg-slate-950 border border-slate-700 rounded-lg" />
              </div>
            </div>
            <button type="submit" disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 py-3 rounded-lg font-medium">
              {loading ? "Generating PDF…" : "Generate branded ebook PDF"}
            </button>
          </form>
        )}

        {tab === "guide" && (
          <form onSubmit={handleGuide} className="space-y-4 bg-slate-900 border border-slate-800 rounded-xl p-6">
            <h3 className="font-semibold text-lg">Post-consultation implementation guide</h3>
            <p className="text-xs text-slate-500">Enter business details from the consultation. Get a step-by-step PDF plan.</p>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Business name *</label>
              <input required value={bizName} onChange={(e) => setBizName(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Industry</label>
                <input value={industry} onChange={(e) => setIndustry(e.target.value)}
                  placeholder="e.g. dental clinic, fashion retail"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm" />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Your brand on the PDF</label>
                <input value={guideBrand} onChange={(e) => setGuideBrand(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm" />
              </div>
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Goals</label>
              <textarea value={goals} onChange={(e) => setGoals(e.target.value)} rows={2}
                placeholder="More booked appointments, better Instagram presence…"
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm" />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Current situation</label>
              <textarea value={current} onChange={(e) => setCurrent(e.target.value)} rows={2}
                placeholder="No website, WhatsApp-only sales, outdated logo…"
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm" />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Services you will deliver</label>
              <textarea value={services} onChange={(e) => setServices(e.target.value)} rows={2}
                placeholder="Website + Google Business + 2-week content plan"
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm" />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Consultation notes</label>
              <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3}
                placeholder="Budget, timeline, decision maker, competitors mentioned…"
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm" />
            </div>
            <button type="submit" disabled={loading}
              className="w-full bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 py-3 rounded-lg font-medium">
              {loading ? "Generating guide…" : "Generate implementation guide PDF"}
            </button>
          </form>
        )}
      </main>
    </div>
  );
}
