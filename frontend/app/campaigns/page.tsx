"use client";
import Link from "next/link";

export default function CampaignsPage() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="text-xl font-bold"><img src="/favicon.svg" alt="" width={28} height={28} className="rounded-md inline-block mr-2 align-middle" />RuffNeck <span className="text-blue-400">Prospector</span></Link>
          <nav className="flex gap-6 text-sm text-slate-400">
            <Link href="/discover" className="hover:text-white transition">Discover</Link>
            <Link href="/prospects">Prospects</Link>
            <Link href="/pipeline" className="hover:text-white transition">Pipeline</Link>
            <Link href="/analytics" className="hover:text-white transition">Analytics</Link>
            <Link href="/campaigns" className="text-white">Campaigns</Link>
            <Link href="/generate">Generate</Link>
          </nav>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-6 py-12">
        <h2 className="text-2xl font-bold mb-4">Campaigns</h2>
        <p className="text-slate-400 mb-8">
          Campaign management UI is scaffolded. Use the API endpoints and the seeded outreach templates
          in the database to start sequences. Full campaign builder can be expanded here.
        </p>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
          <p className="text-sm text-slate-300">
            Default templates are already inserted by <code className="bg-slate-800 px-1 rounded">schema.sql</code>.
            Query them via <code className="bg-slate-800 px-1 rounded">GET /api/templates</code>.
          </p>
        </div>
      </main>
    </div>
  );
}
