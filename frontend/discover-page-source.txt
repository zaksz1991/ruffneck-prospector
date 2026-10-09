"use client";

import NotificationBell from "../../components/NotificationBell";
import WorkspaceSwitcher from "../../components/WorkspaceSwitcher";
import { apiFetch, API } from "../../lib/api";
import { getActiveWorkspaceId } from "../../lib/workspace";

import { useState, useEffect } from "react";
import Link from "next/link";


const SERVICES = [
  { key: "website", label: "Website / Web Dev" },
  { key: "digital_marketing", label: "Digital Marketing" },
  { key: "ai_solution", label: "AI Solutions" },
  { key: "graphics", label: "Graphics Design" },
  { key: "cv_resume", label: "CV / Resume" },
  { key: "excel", label: "Excel / Data Cleaning" },
  { key: "any_product_service", label: "Any product / service (general demand)" },
  { key: "buying_intent", label: "Buying intent (looking to buy)" },
  { key: "hiring_services", label: "Hiring / freelancers needed" },
  { key: "local_services", label: "Local services near me" },
  { key: "b2b_suppliers", label: "B2B suppliers / wholesale" },
  { key: "coaching_consulting", label: "Coaching / consulting" },
  { key: "health_wellness", label: "Health & wellness" },
  { key: "education_training", label: "Education / training" },
  { key: "home_services", label: "Home services (plumber, etc.)" },
  { key: "events_creative", label: "Events / photo / video" },
  { key: "finance_legal", label: "Finance / legal / accounting" },
  { key: "custom", label: "Custom product or service (type below)" },
];

const JOB_BOARDS = [
  { value: "all", label: "All free boards" },
  { value: "remoteok", label: "RemoteOK" },
  { value: "remotive", label: "Remotive" },
  { value: "arbeitnow", label: "Arbeitnow" },
  { value: "jobicy", label: "Jobicy" },
  { value: "weworkremotely", label: "We Work Remotely" },
  { value: "indeed", label: "Indeed (best-effort)" },
];

export default function DiscoverPage() {
  const [tab, setTab] = useState<"daily" | "linkedin" | "jobs" | "maps" | "service" | "product" | "competitors">("daily");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [taskId, setTaskId] = useState("");
  const [taskStatus, setTaskStatus] = useState<any>(null);
  const [location, setLocation] = useState("");

  // Shared
  const [keywords, setKeywords] = useState("");
  const [maxResults, setMaxResults] = useState(20);

  // Service
  const [service, setService] = useState("website");
  const [extraKeywords, setExtraKeywords] = useState("");

  // LinkedIn
  const [liQuery, setLiQuery] = useState("need website designer OR digital marketing help");

  // Jobs
  const [jobBoard, setJobBoard] = useState("all");
  const [jobKeywords, setJobKeywords] = useState("marketing developer designer");

  // Maps
  const [mapsQuery, setMapsQuery] = useState("restaurants Lagos");
  const [noWebsite, setNoWebsite] = useState(true);
  const [minRating, setMinRating] = useState("");
  const [productQuery, setProductQuery] = useState("");
  const [productLocation, setProductLocation] = useState("");
  const [competitorSeed, setCompetitorSeed] = useState("");
  const [competitorLocation, setCompetitorLocation] = useState("");
  const [competitorCategory, setCompetitorCategory] = useState("");

  // Poll task status
  useEffect(() => {
    if (!taskId) return;
    const interval = setInterval(async () => {
      try {
        const res = await apiFetch(`/api/tasks/${taskId}`);
        const data = await res.json();
        setTaskStatus(data);
        if (data.status === "SUCCESS" || data.status === "FAILURE") {
          clearInterval(interval);
          setLoading(false);
        }
      } catch {
        // ignore
      }
    }, 2500);
    return () => clearInterval(interval);
  }, [taskId]);

  async function runSearch(payload: any, endpoint = "/api/prospects/search") {
    const ws = getActiveWorkspaceId();
    if (ws) payload.workspace_id = ws;

    setLoading(true);
    setStatus("");
    setTaskId("");
    setTaskStatus(null);
    try {
      const res = await fetch(`${API}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      setTaskId(data.task_id || "");
      setStatus(data.status || "started");
    } catch (e) {
      setStatus("Failed to start – is the API running?");
      setLoading(false);
    }
  }

  function handleDaily(e: React.FormEvent) {
    e.preventDefault();
    runSearch(
      { location: location || "", services: null },
      "/api/discover/daily"
    );
  }

  function handleServiceDiscover(e: React.FormEvent) {
    e.preventDefault();
    runSearch(
      {
        service,
        extra_keywords: extraKeywords.split(/[\s,]+/).filter(Boolean),
        max_results: maxResults,
      },
      "/api/discover/leads"
    );
  }

  function handleLinkedIn(e: React.FormEvent) {
    e.preventDefault();
    runSearch({
      platform: "linkedin",
      target_url: liQuery,
      keywords: keywords.split(/[\s,]+/).filter(Boolean),
      max_results: maxResults,
    });
  }

  function handleJobs(e: React.FormEvent) {
    e.preventDefault();
    runSearch({
      platform: "jobs",
      target_url: jobBoard,
      keywords: jobKeywords.split(/[\s,]+/).filter(Boolean),
      max_results: maxResults,
    });
  }

  function handleCompetitors(e: React.FormEvent) {
    e.preventDefault();
    if (!competitorSeed.trim()) return;
    runSearch(
      {
        seed: competitorSeed.trim(),
        location: competitorLocation.trim(),
        category: competitorCategory.trim(),
        max_results: maxResults,
      },
      "/api/discover/competitors"
    );
  }

  function handleProductDemand(e: React.FormEvent) {
    e.preventDefault();
    if (!productQuery.trim()) return;
    runSearch(
      {
        product_or_service: productQuery.trim(),
        location: productLocation.trim(),
        max_results: maxResults,
      },
      "/api/discover/product-demand"
    );
  }

  function handleMaps(e: React.FormEvent) {
    e.preventDefault();
    const kw: string[] = [];
    if (noWebsite) kw.push("no_website");
    if (minRating) kw.push(`min_rating:${minRating}`);
    runSearch({
      platform: "maps",
      target_url: mapsQuery,
      keywords: kw,
      max_results: maxResults,
    });
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="text-xl font-bold">
            <img src="/favicon.svg" alt="" width={28} height={28} className="rounded-md inline-block mr-2 align-middle" />RuffNeck <span className="text-blue-400">Prospector</span>
            <span className="ml-2 text-xs bg-emerald-900/50 text-emerald-400 px-2 py-0.5 rounded">v1.4 FREE</span>
          </Link>
          <nav className="flex gap-6 text-sm text-slate-400">
            <Link href="/discover" className="text-white">Discover</Link>
            <Link href="/prospects">Prospects</Link>
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

      <main className="max-w-3xl mx-auto px-6 py-10">
        <h2 className="text-2xl font-bold mb-2">Discovery Hub</h2>
        <p className="text-slate-400 text-sm mb-8">
          Free automated lead discovery. Use the one-click Daily button or run targeted searches.
        </p>

        {/* Tabs */}
        <div className="flex flex-wrap gap-2 mb-8">
          {[
            { id: "daily", label: "⚡ Daily Discovery" },
            { id: "service", label: "Service Intent" },
            { id: "linkedin", label: "LinkedIn" },
            { id: "jobs", label: "Job Boards" },
            { id: "maps", label: "Google Maps" },
            { id: "product", label: "Any Product/Service" },
            { id: "competitors", label: "Competitors / Lookalikes" },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id as any)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                tab === t.id
                  ? "bg-blue-600 text-white"
                  : "bg-slate-900 text-slate-400 hover:text-white border border-slate-800"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* ===== DAILY ONE-CLICK ===== */}
        {tab === "daily" && (
          <form onSubmit={handleDaily} className="space-y-5 bg-gradient-to-br from-blue-950/40 to-slate-900 border border-blue-800/50 rounded-xl p-6">
            <div>
              <h3 className="text-lg font-semibold mb-1">One-Click Daily Discovery</h3>
              <p className="text-sm text-slate-400 mb-4">
                Automatically runs service intent searches (all 6 services), LinkedIn intent, 
                free job boards, and optional local Maps — then saves + enriches leads.
              </p>
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">Location (optional – improves Maps + local relevance)</label>
              <input
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="e.g. Lagos, Nigeria or Nairobi"
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 py-3.5 rounded-lg font-semibold text-base"
            >
              {loading ? "Running Daily Discovery…" : "🚀 Run Daily Discovery"}
            </button>
          </form>
        )}

        {/* Service Intent */}
        {tab === "service" && (
          <form onSubmit={handleServiceDiscover} className="space-y-5 bg-slate-900 border border-slate-800 rounded-xl p-6">
            <div>
              <label className="block text-sm text-slate-400 mb-1">Service you offer</label>
              <select value={service} onChange={(e) => setService(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm">
                {SERVICES.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">Extra keywords (location, niche, or product name if Custom…)</label>
              <input value={extraKeywords} onChange={(e) => setExtraKeywords(e.target.value)}
                placeholder="Nigeria Lagos remote" className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm" />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">Max results</label>
              <input type="number" min={5} max={40} value={maxResults} onChange={(e) => setMaxResults(Number(e.target.value))}
                className="w-32 bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm" />
            </div>
            <button type="submit" disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 py-3 rounded-lg font-medium">
              {loading ? "Starting…" : "Discover Service Leads"}
            </button>
          </form>
        )}

        {/* LinkedIn */}
        {tab === "linkedin" && (
          <form onSubmit={handleLinkedIn} className="space-y-5 bg-slate-900 border border-slate-800 rounded-xl p-6">
            <p className="text-xs text-slate-500">
              Paste a full LinkedIn profile URL (linkedin.com/in/...) for deep profile scraping, 
              or type a search query for Google site:linkedin.com discovery.
            </p>
            <div>
              <label className="block text-sm text-slate-400 mb-1">Profile URL or Search query</label>
              <input value={liQuery} onChange={(e) => setLiQuery(e.target.value)}
                placeholder="https://www.linkedin.com/in/username  or  need website designer"
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm" />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">Extra filter keywords</label>
              <input value={keywords} onChange={(e) => setKeywords(e.target.value)} placeholder="optional"
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm" />
            </div>
            <button type="submit" disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 py-3 rounded-lg font-medium">
              {loading ? "Starting…" : "Search LinkedIn"}
            </button>
          </form>
        )}

        {/* Jobs */}
        {tab === "jobs" && (
          <form onSubmit={handleJobs} className="space-y-5 bg-slate-900 border border-slate-800 rounded-xl p-6">
            <div>
              <label className="block text-sm text-slate-400 mb-1">Job board</label>
              <select value={jobBoard} onChange={(e) => setJobBoard(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm">
                {JOB_BOARDS.map((b) => <option key={b.value} value={b.value}>{b.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">Keywords</label>
              <input value={jobKeywords} onChange={(e) => setJobKeywords(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm" />
            </div>
            <button type="submit" disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 py-3 rounded-lg font-medium">
              {loading ? "Starting…" : "Search Job Boards"}
            </button>
          </form>
        )}

        {/* Maps */}
        {tab === "maps" && (
          <form onSubmit={handleMaps} className="space-y-5 bg-slate-900 border border-slate-800 rounded-xl p-6">
            <div className="flex flex-wrap gap-2 mb-2">
              <span className="text-xs text-slate-500 w-full mb-1">Local Business Mode presets:</span>
              {[
                { q: "restaurants", label: "Restaurants" },
                { q: "salons OR barbers", label: "Salons / Barbers" },
                { q: "plumbers OR electricians", label: "Trades" },
                { q: "clinics OR dentists", label: "Clinics" },
                { q: "boutiques OR stores", label: "Retail" },
              ].map(preset => (
                <button
                  key={preset.label}
                  type="button"
                  onClick={() => setMapsQuery(preset.q + (location ? " " + location : " Lagos"))}
                  className="text-xs px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700"
                >
                  {preset.label}
                </button>
              ))}
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">Search query (business type + location)</label>
              <input value={mapsQuery} onChange={(e) => setMapsQuery(e.target.value)}
                placeholder="restaurants Lagos" className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm" />
            </div>
            <div className="flex flex-wrap gap-6 items-end">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={noWebsite} onChange={(e) => setNoWebsite(e.target.checked)} className="rounded" />
                Prefer no-website signal
              </label>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Min rating</label>
                <input type="number" step="0.1" min="0" max="5" value={minRating}
                  onChange={(e) => setMinRating(e.target.value)} placeholder="4.0"
                  className="w-24 bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-sm" />
              </div>
            </div>
            <button type="submit" disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 py-3 rounded-lg font-medium">
              {loading ? "Starting…" : "Search Google Maps"}
            </button>
          </form>
        )}

        
        
        {/* Competitors / Lookalikes */}
        {tab === "competitors" && (
          <form onSubmit={handleCompetitors} className="space-y-5 bg-gradient-to-br from-orange-950/30 to-slate-900 border border-orange-800/40 rounded-xl p-6">
            <div>
              <h3 className="text-lg font-semibold mb-1">Competitors & Lookalikes</h3>
              <p className="text-sm text-slate-400 mb-4">
                Enter a company name or website. Finds similar companies via free search
                (related sites, alternatives to, competitors of) and optional local Maps lookalikes.
              </p>
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">Company name or website</label>
              <input
                value={competitorSeed}
                onChange={(e) => setCompetitorSeed(e.target.value)}
                placeholder="e.g. hubspot.com  or  Acme Digital Agency"
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm"
                required
              />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">Location (optional)</label>
                <input
                  value={competitorLocation}
                  onChange={(e) => setCompetitorLocation(e.target.value)}
                  placeholder="Lagos, Nairobi, remote…"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">Category / industry (optional)</label>
                <input
                  value={competitorCategory}
                  onChange={(e) => setCompetitorCategory(e.target.value)}
                  placeholder="digital agency, plumber, SaaS…"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">Max results</label>
              <input
                type="number"
                min={5}
                max={40}
                value={maxResults}
                onChange={(e) => setMaxResults(Number(e.target.value))}
                className="w-32 bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-orange-600 hover:bg-orange-500 disabled:opacity-50 py-3 rounded-lg font-medium"
            >
              {loading ? "Searching…" : "Find competitors & lookalikes"}
            </button>
          </form>
        )}

        {/* Any Product / Service Demand */}
        {tab === "product" && (
          <form onSubmit={handleProductDemand} className="space-y-5 bg-gradient-to-br from-emerald-950/30 to-slate-900 border border-emerald-800/40 rounded-xl p-6">
            <div>
              <h3 className="text-lg font-semibold mb-1">Anyone who needs a product or service online</h3>
              <p className="text-sm text-slate-400 mb-4">
                Searches the open web for demand signals: “looking for”, “need a”, “recommend”,
                “where can I buy”, “anyone know a good…”. Works for any product or service.
              </p>
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">Product or service</label>
              <input
                value={productQuery}
                onChange={(e) => setProductQuery(e.target.value)}
                placeholder="e.g. solar panels, wedding photographer, accounting software, tutors"
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm"
                required
              />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">Location (optional)</label>
              <input
                value={productLocation}
                onChange={(e) => setProductLocation(e.target.value)}
                placeholder="e.g. Lagos, Nigeria or remote"
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">Max results</label>
              <input
                type="number"
                min={5}
                max={40}
                value={maxResults}
                onChange={(e) => setMaxResults(Number(e.target.value))}
                className="w-32 bg-slate-950 border border-slate-700 rounded-lg px-4 py-2.5 text-sm"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 py-3 rounded-lg font-medium"
            >
              {loading ? "Searching…" : "Find people who need this"}
            </button>
          </form>
        )}

        {/* Status Tracking Panel */}
        {(status || taskStatus) && (
          <div className="mt-8 p-5 bg-slate-900 border border-slate-800 rounded-xl text-sm space-y-3">
            <div className="flex items-center justify-between">
              <p className="font-medium text-slate-200">Task Status</p>
              {taskStatus?.status && (
                <span className={`px-2.5 py-0.5 rounded text-xs font-medium ${
                  taskStatus.status === "SUCCESS" ? "bg-emerald-900/50 text-emerald-400" :
                  taskStatus.status === "FAILURE" ? "bg-red-900/50 text-red-400" :
                  "bg-blue-900/50 text-blue-400"
                }`}>
                  {taskStatus.status}
                </span>
              )}
            </div>
            <p className="text-slate-400">Started: <span className="text-slate-300">{status}</span></p>
            {taskId && <p className="text-slate-500">Task ID: <code className="bg-slate-800 px-1.5 py-0.5 rounded text-xs">{taskId}</code></p>}
            
            {taskStatus?.status === "SUCCESS" && taskStatus.result && (
              <div className="mt-3 p-3 bg-slate-950 rounded-lg">
                <p className="text-emerald-400 font-medium mb-2">Completed successfully</p>
                {taskStatus.result.results && (
                  <pre className="text-xs text-slate-400 overflow-auto max-h-40">
                    {JSON.stringify(taskStatus.result.results, null, 2)}
                  </pre>
                )}
                <p className="mt-3">
                  <Link href="/prospects" className="text-blue-400 underline">View prospects →</Link>
                </p>
              </div>
            )}
            {taskStatus?.status === "FAILURE" && (
              <p className="text-red-400">Error: {taskStatus.error || "Unknown error"}</p>
            )}
            {(taskStatus?.status === "PENDING" || taskStatus?.status === "STARTED") && (
              <p className="text-blue-400 animate-pulse">Working… results will appear here and in Prospects when done.</p>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
