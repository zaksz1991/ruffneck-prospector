"use client";
import { apiFetch } from "../lib/api";

import NotificationBell from "../components/NotificationBell";
import { getUser, clearSession } from "../lib/auth";
import WorkspaceSwitcher from "../components/WorkspaceSwitcher";

import Link from "next/link";

async function seedDemo() {
  try {
    const res = await apiFetch(`/api/demo/seed`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Seed failed");
    alert(`Loaded ${data.inserted} demo prospects. Open Pipeline or Prospects.`);
    window.location.href = "/pipeline";
  } catch (e: any) {
    alert(e.message || "Seed failed – is the API + Supabase configured?");
  }
}

export default function Dashboard() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <h1 className="text-xl font-bold tracking-tight">
            <img src="/favicon.svg" alt="" width={28} height={28} className="rounded-md inline-block mr-2 align-middle" />RuffNeck <span className="text-blue-400">Prospector</span>
            <span className="ml-2 text-xs bg-emerald-900/50 text-emerald-400 px-2 py-0.5 rounded">v1.4 FREE</span>
          </h1>
          <nav className="flex gap-6 text-sm text-slate-400">
            <Link href="/login" className="hover:text-white transition">Login</Link>
            <button
              type="button"
              onClick={() => { clearSession(); window.location.href = "/login"; }}
              className="hover:text-white transition text-slate-500"
            >
              Logout
            </button>
            <Link href="/create" className="hover:text-white transition">Create</Link>
            <Link href="/discover" className="hover:text-white transition">Discover</Link>
            <Link href="/prospects" className="hover:text-white transition">Prospects</Link>
            <Link href="/pipeline" className="hover:text-white transition">Pipeline</Link>
            <Link href="/analytics" className="hover:text-white transition">Analytics</Link>
            <Link href="/campaigns" className="hover:text-white transition">Campaigns</Link>
            <Link href="/generate" className="hover:text-white transition">Generate</Link>
          <NotificationBell />
            <WorkspaceSwitcher />
          </nav>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-12">
        <div className="mb-10">
          <h2 className="text-3xl font-bold mb-2">Find customers who need your services</h2>
          <p className="text-slate-400 max-w-2xl">
            100% free multi-platform prospecting + Google intent discovery for digital marketing,
            websites, AI solutions, graphics, CV writing, Excel help and more.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          <Card title="Discover Leads" description="Google/DuckDuckGo free search for people saying 'I need a website / marketing / AI...'" href="/prospects" stat="New" />
          <Card title="Prospects" description="View scored leads from all platforms with influence & niche fit" href="/prospects" stat="Multi-signal" />
          <Card title="Generate Asset" description="Personalized PDF guides or slide decks (local, free)" href="/generate" stat="PDF + PPTX" />
        </div>

        <section className="bg-slate-900 border border-slate-800 rounded-xl p-6 mb-8">
          <h3 className="text-lg font-semibold mb-4">Built-in service discovery (free)</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
            <ServiceBadge name="Digital Marketing" />
            <ServiceBadge name="Website / Web Dev" />
            <ServiceBadge name="AI Solutions" />
            <ServiceBadge name="Graphics Design" />
            <ServiceBadge name="CV / Resume Writing" />
            <ServiceBadge name="Excel Data Cleaning" />
          </div>
        </section>

        <section className="bg-slate-900 border border-slate-800 rounded-xl p-6">
          <h3 className="text-lg font-semibold mb-4">Free platforms</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <PlatformBadge name="Instagram" method="Public + Instaloader" />
            <PlatformBadge name="X / Twitter" method="Public methods" />
            <PlatformBadge name="Reddit" method="Official PRAW free" />
            <PlatformBadge name="YouTube" method="Data API free quota" />
            <PlatformBadge name="TikTok" method="Public endpoints" />
            <PlatformBadge name="Facebook" method="Playwright public" />
            <PlatformBadge name="Google" method="DuckDuckGo + CSE free" />
            <PlatformBadge name="Email" method="Gmail SMTP free" />
          </div>
        </section>
      </main>
    </div>
  );
}

function Card({ title, description, href, stat }: { title: string; description: string; href: string; stat: string }) {
  return (
    <Link href={href} className="block p-6 rounded-xl border border-slate-800 bg-slate-900/60 hover:border-blue-500/50 hover:bg-slate-900 transition group">
      <div className="text-xs text-blue-400 mb-2 font-medium">{stat}</div>
      <h3 className="text-lg font-semibold mb-1 group-hover:text-blue-300 transition">{title}</h3>
      <p className="text-sm text-slate-400">{description}</p>
    </Link>
  );
}

function PlatformBadge({ name, method }: { name: string; method: string }) {
  return (
    <div className="bg-slate-950 rounded-lg p-3 border border-slate-800">
      <div className="font-medium">{name}</div>
      <div className="text-xs text-slate-500 mt-1">{method}</div>
    </div>
  );
}

function ServiceBadge({ name }: { name: string }) {
  return (
    <div className="bg-emerald-950/40 border border-emerald-900/50 rounded-lg px-3 py-2 text-emerald-300 text-center">
      {name}
    </div>
  );
}
