"use client";

import { useState } from "react";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function GeneratePage() {
  const [prospectId, setProspectId] = useState("");
  const [topic, setTopic] = useState("How to land remote AI jobs in 2026");
  const [assetType, setAssetType] = useState("ebook");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setStatus("");
    try {
      const res = await fetch(`${API}/api/generate/asset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prospect_id: prospectId,
          asset_type: assetType,
          topic,
          branding: { company_name: "RuffNeck Entertainment" },
        }),
      });
      const data = await res.json();
      setStatus(`Started: task ${data.task_id}`);
    } catch (err) {
      setStatus("Failed to start generation");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="text-xl font-bold"><img src="/favicon.svg" alt="" width={28} height={28} className="rounded-md inline-block mr-2 align-middle" />RuffNeck <span className="text-blue-400">Prospector</span></Link>
          <nav className="flex gap-6 text-sm text-slate-400">
            <Link href="/discover" className="hover:text-white transition">Discover</Link>
            <Link href="/prospects">Prospects</Link>
            <Link href="/campaigns">Campaigns</Link>
            <Link href="/generate" className="text-white">Generate</Link>
          </nav>
        </div>
      </header>

      <main className="max-w-xl mx-auto px-6 py-12">
        <h2 className="text-2xl font-bold mb-2">Generate Personalized Asset</h2>
        <p className="text-slate-400 mb-8 text-sm">
          Creates a free PDF mini-guide or PowerPoint deck personalized for a prospect.
          Files are generated locally (ReportLab / python-pptx). Upload to free storage yourself.
        </p>

        <form onSubmit={handleGenerate} className="space-y-5">
          <div>
            <label className="block text-sm text-slate-400 mb-1">Prospect ID (UUID)</label>
            <input
              required
              value={prospectId}
              onChange={(e) => setProspectId(e.target.value)}
              placeholder="from /api/prospects"
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1">Topic</label>
            <input
              required
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1">Asset Type</label>
            <select
              value={assetType}
              onChange={(e) => setAssetType(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-sm"
            >
              <option value="ebook">PDF Mini-Guide (ebook)</option>
              <option value="slides">PowerPoint Deck</option>
            </select>
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 py-3 rounded-lg font-medium"
          >
            {loading ? "Starting…" : "Generate Asset"}
          </button>
        </form>

        {status && (
          <p className="mt-6 text-sm text-center text-slate-300 bg-slate-900 border border-slate-800 rounded-lg p-4">
            {status}
          </p>
        )}
      </main>
    </div>
  );
}
