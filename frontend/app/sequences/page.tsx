"use client";

import NotificationBell from "../../components/NotificationBell";
import WorkspaceSwitcher from "../../components/WorkspaceSwitcher";
import { apiFetch } from "../../lib/api";

import { useEffect, useState } from "react";
import Link from "next/link";

export default function SequencesPage() {
  const [sequences, setSequences] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [steps, setSteps] = useState<any[]>([]);
  const [enrollments, setEnrollments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [processing, setProcessing] = useState(false);
  const [checkingReplies, setCheckingReplies] = useState(false);
  const [suppressEmail, setSuppressEmail] = useState("");
  const [suppressions, setSuppressions] = useState<any[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadSequences();
    loadSuppressions();
  }, []);

  async function loadSequences() {
    setLoading(true);

    try {
      const res = await apiFetch("/api/sequences");
      const data = await res.json();
      setSequences(data.sequences || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function loadSuppressions() {
    try {
      const res = await apiFetch("/api/suppressions");
      const data = await res.json();
      setSuppressions(data.suppressions || []);
    } catch (e) {
      console.error(e);
    }
  }

  async function refreshPage() {
    setRefreshing(true);

    try {
      await Promise.all([
        loadSequences(),
        loadSuppressions(),
        selected?.id ? selectSequence(selected.id) : Promise.resolve(),
      ]);

      setMessage("Sequences refreshed");
    } finally {
      setRefreshing(false);
    }
  }

  async function selectSequence(id: string) {
    try {
      const [seqRes, enrRes] = await Promise.all([
        apiFetch(`/api/sequences/${id}`),
        apiFetch(`/api/sequences/${id}/enrollments`),
      ]);

      const seqData = await seqRes.json();
      const enrData = await enrRes.json();

      setSelected(seqData.sequence);
      setSteps(seqData.steps || []);
      setEnrollments(enrData.enrollments || []);
    } catch (e) {
      console.error(e);
    }
  }

  async function seedDefault() {
    try {
      const res = await apiFetch(
        "/api/sequences/seed-default",
        {
          method: "POST",
        }
      );

      const data = await res.json();

      setMessage(
        data.status === "created"
          ? "Default sequence created!"
          : "Default sequence already exists"
      );

      loadSequences();
    } catch {
      setMessage(
        "Could not seed sequence – is the API running and schema updated?"
      );
    }
  }

  async function addSuppression(e: React.FormEvent) {
    e.preventDefault();

    if (!suppressEmail.trim()) {
      return;
    }

    const email = suppressEmail.trim();

    await apiFetch("/api/suppressions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        email,
        reason: "unsubscribe",
        source: "manual",
      }),
    });

    setSuppressEmail("");

    const res = await apiFetch("/api/suppressions");
    const data = await res.json();

    setSuppressions(data.suppressions || []);
    setMessage(`Added ${email} to suppression list`);
  }

  async function checkReplies() {
    setCheckingReplies(true);
    setMessage("");

    try {
      const res = await apiFetch("/api/replies/check", {
        method: "POST",
      });

      const data = await res.json();

      setMessage(
        `Reply check started (task: ${
          data.task_id || "ok"
        }). Matched replies will auto-update pipeline.`
      );
    } catch {
      setMessage(
        "Reply check failed – is IMAP/SMTP configured?"
      );
    } finally {
      setCheckingReplies(false);
    }
  }

  async function processDue() {
    setProcessing(true);
    setMessage("");

    try {
      const res = await apiFetch("/api/sequences/process", {
        method: "POST",
      });

      const data = await res.json();

      setMessage(
        `Processor started (task: ${
          data.task_id || "ok"
        }). Real emails will send if SMTP is configured.`
      );
    } catch {
      setMessage("Failed to start processor");
    } finally {
      setProcessing(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="text-xl font-bold">
            <img
              src="/favicon.svg"
              alt=""
              width={28}
              height={28}
              className="rounded-md inline-block mr-2 align-middle"
            />
            RuffNeck{" "}
            <span className="text-blue-400">
              Prospector
            </span>
          </Link>

          <nav className="flex gap-5 text-sm text-slate-400 items-center">
            <Link href="/discover">Discover</Link>

            <Link href="/prospects">
              Prospects
            </Link>

            <Link href="/pipeline">
              Pipeline
            </Link>

            <Link
              href="/sequences"
              className="text-white"
            >
              Sequences
            </Link>

            <Link href="/team">
              Team
            </Link>

            <Link href="/analytics">
              Analytics
            </Link>

            <NotificationBell />

            <WorkspaceSwitcher />
          </nav>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-10">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-8">
          <div>
            <h2 className="text-2xl font-bold">
              Email Sequences
            </h2>

            <p className="text-slate-400 text-sm mt-1">
              Multi-step follow-ups with real sending and
              auto-pause on reply.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
                          <button
                onClick={refreshPage}
                disabled={refreshing}
                className="bg-slate-700 hover:bg-slate-600 disabled:opacity-50 px-4 py-2 rounded text-sm"
              >
                {refreshing ? "Refreshing…" : "Refresh"}
              </button>
<button
              onClick={seedDefault}
              className="bg-slate-700 hover:bg-slate-600 px-4 py-2 rounded text-sm"
            >
              Seed Default Sequence
            </button>

            <button
              onClick={checkReplies}
              disabled={checkingReplies}
              className="bg-emerald-700 hover:bg-emerald-600 disabled:opacity-50 px-4 py-2 rounded text-sm"
            >
              {checkingReplies
                ? "Checking…"
                : "Check Inbox for Replies"}
            </button>

            <button
              onClick={processDue}
              disabled={processing}
              className="bg-violet-700 hover:bg-violet-600 disabled:opacity-50 px-4 py-2 rounded text-sm"
            >
              {processing
                ? "Processing…"
                : "Process Due Steps (sends emails)"}
            </button>
          </div>
        </div>

        {message && (
          <div className="mb-6 p-3 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-300">
            {message}
          </div>
        )}

        <div className="grid lg:grid-cols-3 gap-6">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h3 className="font-semibold mb-4">
              Sequences
            </h3>

            {loading ? (
              <p className="text-slate-500 text-sm">
                Loading…
              </p>
            ) : sequences.length === 0 ? (
              <div className="text-sm text-slate-500">
                <p className="mb-3">
                  No sequences yet.
                </p>

                <button
                  onClick={seedDefault}
                  className="text-blue-400 underline"
                >
                  Create default 3-step sequence
                </button>
              </div>
            ) : (
              <ul className="space-y-2">
                {sequences.map((seq) => (
                  <li key={seq.id}>
                    <button
                      onClick={() =>
                        selectSequence(seq.id)
                      }
                      className={`w-full text-left px-3 py-2.5 rounded-lg text-sm border transition ${
                        selected?.id === seq.id
                          ? "border-blue-600 bg-blue-950/40"
                          : "border-slate-800 hover:border-slate-600"
                      }`}
                    >
                      <div className="font-medium">
                        {seq.name}
                      </div>

                      <div className="text-xs text-slate-500 mt-0.5">
                        {seq.is_active
                          ? "Active"
                          : "Inactive"}
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h3 className="font-semibold mb-4">
              {selected
                ? `Steps – ${selected.name}`
                : "Steps"}
            </h3>

            {!selected ? (
              <p className="text-sm text-slate-500">
                Select a sequence to view steps
              </p>
            ) : steps.length === 0 ? (
              <p className="text-sm text-slate-500">
                No steps found
              </p>
            ) : (
              <div className="space-y-3">
                {steps.map((step, idx) => (
                  <div
                    key={step.id || idx}
                    className="border border-slate-800 rounded-lg p-3 bg-slate-950"
                  >
                    <div className="flex justify-between text-xs text-slate-500 mb-1">
                      <span>
                        Step {step.step_order + 1}
                      </span>

                      <span>
                        Delay: {step.delay_days}d
                      </span>
                    </div>

                    <div className="text-sm font-medium">
                      {step.subject_template}
                    </div>

                    <p className="text-xs text-slate-400 mt-1 line-clamp-3 whitespace-pre-wrap">
                      {step.body_template}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h3 className="font-semibold mb-4">
              Enrollments
            </h3>

            {!selected ? (
              <p className="text-sm text-slate-500">
                Select a sequence
              </p>
            ) : enrollments.length === 0 ? (
              <div className="text-sm text-slate-500 space-y-2">
                <p>
                  No one enrolled yet.
                </p>

                <p>
                  Go to{" "}
                  <Link
                    href="/prospects"
                    className="text-blue-400 underline"
                  >
                    Prospects
                  </Link>{" "}
                  or{" "}
                  <Link
                    href="/pipeline"
                    className="text-blue-400 underline"
                  >
                    Pipeline
                  </Link>{" "}
                  and use{" "}
                  <strong>
                    Enroll in Sequence
                  </strong>
                  .
                </p>
              </div>
            ) : (
              <ul className="space-y-2 max-h-96 overflow-y-auto">
                {enrollments.map((enr) => {
                  const p = enr.prospects || {};

                  return (
                    <li
                      key={enr.id}
                      className="text-sm border border-slate-800 rounded-lg p-2.5"
                    >
                      <div className="font-medium">
                        {p.display_name ||
                          p.username ||
                          "Prospect"}
                      </div>

                      <div className="text-xs text-slate-500 mt-0.5">
                        {p.email || "No email"} · Step{" "}
                        {enr.current_step} ·{" "}
                        <span className="capitalize">
                          {enr.status}
                        </span>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>

        <div className="mt-10 p-5 bg-slate-900/50 border border-slate-800 rounded-xl text-sm text-slate-400">
          <p className="font-medium text-slate-300 mb-2">
            How to use sequences
          </p>

          <ol className="list-decimal list-inside space-y-1">
            <li>
              Click{" "}
              <strong>
                Seed Default Sequence
              </strong>{" "}
              (or create your own via API)
            </li>

            <li>
              On Prospects or Pipeline, select leads
              and click{" "}
              <strong>
                Enroll in Sequence
              </strong>
            </li>

            <li>
              Configure Gmail SMTP in{" "}
              <code>.env</code> (SMTP_USER +
              SMTP_PASS)
            </li>

            <li>
              Click{" "}
              <strong>
                Process Due Steps
              </strong>{" "}
              to send the next emails
            </li>

            <li>
              When a prospect replies, log the reply →
              sequence auto-pauses
            </li>
          </ol>
        </div>

        <div className="mt-10 p-5 bg-slate-900 border border-slate-800 rounded-xl">
          <h3 className="font-semibold mb-2">
            Suppression / Unsubscribe list
          </h3>

          <p className="text-xs text-slate-500 mb-3">
            Suppressed emails are never sent sequence
            mail. Replies containing STOP/UNSUBSCRIBE
            are added automatically.
          </p>

          <form
            onSubmit={addSuppression}
            className="flex gap-2 mb-4"
          >
            <input
              type="email"
              value={suppressEmail}
              onChange={(e) =>
                setSuppressEmail(e.target.value)
              }
              placeholder="email@to-suppress.com"
              className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm"
              required
            />

            <button
              type="submit"
              className="bg-slate-700 hover:bg-slate-600 px-4 py-2 rounded text-sm"
            >
              Suppress
            </button>
          </form>

          {suppressions.length > 0 && (
            <ul className="text-xs text-slate-400 space-y-1 max-h-32 overflow-y-auto">
              {suppressions
                .slice(0, 20)
                .map((s: any) => (
                  <li key={s.id || s.email}>
                    {s.email} · {s.reason} ·{" "}
                    {s.source}
                  </li>
                ))}
            </ul>
          )}
        </div>
      </main>
    </div>
  );
}