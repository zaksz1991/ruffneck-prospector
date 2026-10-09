"use client";

import NotificationBell from "../../components/NotificationBell";
import WorkspaceSwitcher from "../../components/WorkspaceSwitcher";
import { apiFetch } from "../../lib/api";
import { setActiveWorkspace } from "../../lib/workspace";

import { useEffect, useState } from "react";
import Link from "next/link";

export default function TeamPage() {
  const [workspaces, setWorkspaces] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [selectedWs, setSelectedWs] = useState<string | null>(null);
  const [members, setMembers] = useState<any[]>([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    loadWorkspaces();
  }, []);

  async function loadWorkspaces() {
    setLoading(true);

    try {
      const res = await apiFetch("/api/workspaces");
      const data = await res.json();
      setWorkspaces(data.workspaces || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function createWorkspace(e: React.FormEvent) {
    e.preventDefault();

    if (!name.trim()) {
      return;
    }

    try {
      const workspaceName = name.trim();

      const res = await apiFetch("/api/workspaces", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: workspaceName,
          owner_email: ownerEmail || undefined,
        }),
      });

      const data = await res.json();

      setMessage(
        `Workspace "${workspaceName}" created`
      );

      setName("");
      loadWorkspaces();

      if (data.workspace?.id) {
        setSelectedWs(data.workspace.id);
        loadMembers(data.workspace.id);
      }
    } catch {
      setMessage("Failed to create workspace");
    }
  }

  async function loadMembers(wsId: string) {
    setSelectedWs(wsId);

    const ws = workspaces.find(
      (w) => w.id === wsId
    );

    setActiveWorkspace(wsId, ws?.name);

    try {
      const res = await apiFetch(
        `/api/workspaces/${wsId}/members`
      );

      const data = await res.json();

      setMembers(data.members || []);
    } catch (e) {
      console.error(e);
    }
  }

  async function inviteMember(e: React.FormEvent) {
    e.preventDefault();

    if (!selectedWs || !inviteEmail.trim()) {
      return;
    }

    const email = inviteEmail.trim();

    try {
      await apiFetch("/api/workspaces/invite", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          workspace_id: selectedWs,
          email,
          role: "member",
        }),
      });

      setMessage(`Invited ${email}`);
      setInviteEmail("");

      loadMembers(selectedWs);
    } catch {
      setMessage("Invite failed");
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link
            href="/"
            className="text-xl font-bold"
          >
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
            <Link href="/discover">
              Discover
            </Link>

            <Link href="/prospects">
              Prospects
            </Link>

            <Link href="/pipeline">
              Pipeline
            </Link>

            <Link href="/sequences">
              Sequences
            </Link>

            <Link
              href="/team"
              className="text-white"
            >
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

      <main className="max-w-5xl mx-auto px-6 py-10">
        <h2 className="text-2xl font-bold mb-2">
          Team & Shared Workspaces
        </h2>

        <p className="text-slate-400 text-sm mb-8">
          Create a workspace, invite teammates by
          email, and share the pipeline and leads.
          Works with a shared Supabase project
          (recommended for small teams).
        </p>

        {message && (
          <div className="mb-6 p-3 bg-slate-900 border border-slate-700 rounded-lg text-sm">
            {message}
          </div>
        )}

        <div className="grid md:grid-cols-2 gap-8">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
            <h3 className="font-semibold mb-4">
              Create Workspace
            </h3>

            <form
              onSubmit={createWorkspace}
              className="space-y-4"
            >
              <div>
                <label className="block text-xs text-slate-400 mb-1">
                  Workspace name
                </label>

                <input
                  value={name}
                  onChange={(e) =>
                    setName(e.target.value)
                  }
                  placeholder="e.g. Acme Agency"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm"
                  required
                />
              </div>

              <div>
                <label className="block text-xs text-slate-400 mb-1">
                  Your email (owner)
                </label>

                <input
                  type="email"
                  value={ownerEmail}
                  onChange={(e) =>
                    setOwnerEmail(e.target.value)
                  }
                  placeholder="you@agency.com"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm"
                />
              </div>

              <button
                type="submit"
                className="bg-blue-600 hover:bg-blue-500 px-4 py-2 rounded text-sm font-medium"
              >
                Create Workspace
              </button>
            </form>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
            <h3 className="font-semibold mb-4">
              Your Workspaces
            </h3>

            {loading ? (
              <p className="text-slate-500 text-sm">
                Loading…
              </p>
            ) : workspaces.length === 0 ? (
              <p className="text-slate-500 text-sm">
                No workspaces yet. Create one to start
                sharing.
              </p>
            ) : (
              <ul className="space-y-2 mb-6">
                {workspaces.map((ws) => (
                  <li key={ws.id}>
                    <button
                      onClick={() =>
                        loadMembers(ws.id)
                      }
                      className={`w-full text-left px-3 py-2 rounded-lg text-sm border ${
                        selectedWs === ws.id
                          ? "border-blue-600 bg-blue-950/40"
                          : "border-slate-800 hover:border-slate-600"
                      }`}
                    >
                      <span className="font-medium">
                        {ws.name}
                      </span>

                      <span className="text-xs text-slate-500 ml-2">
                        {ws.slug}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {selectedWs && (
              <div className="border-t border-slate-800 pt-4">
                <h4 className="text-sm font-medium mb-3">
                  Members
                </h4>

                <ul className="space-y-1 mb-4 text-sm">
                  {members.map((m) => (
                    <li
                      key={m.id}
                      className="flex justify-between"
                    >
                      <span>{m.email}</span>

                      <span className="text-xs text-slate-500 capitalize">
                        {m.role} · {m.status}
                      </span>
                    </li>
                  ))}

                  {members.length === 0 && (
                    <li className="text-slate-500">
                      No members yet
                    </li>
                  )}
                </ul>

                <form
                  onSubmit={inviteMember}
                  className="flex gap-2"
                >
                  <input
                    type="email"
                    value={inviteEmail}
                    onChange={(e) =>
                      setInviteEmail(e.target.value)
                    }
                    placeholder="teammate@email.com"
                    className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm"
                    required
                  />

                  <button
                    type="submit"
                    className="bg-emerald-700 hover:bg-emerald-600 px-3 py-2 rounded text-sm"
                  >
                    Invite
                  </button>
                </form>
              </div>
            )}
          </div>
        </div>

        <div className="mt-10 p-5 bg-slate-900/50 border border-slate-800 rounded-xl text-sm text-slate-400 space-y-2">
          <p className="font-medium text-slate-300">
            How shared pipeline works
          </p>

          <ol className="list-decimal list-inside space-y-1">
            <li>
              Create a workspace and invite teammates
              by email.
            </li>

            <li>
              All members use the{" "}
              <strong>
                same Supabase project
              </strong>{" "}
              (simplest free setup).
            </li>

            <li>
              Assign prospects to the workspace (via
              API or future UI button) so everyone sees
              them in the Pipeline.
            </li>

            <li>
              Sequences and replies can also be scoped
              to the workspace.
            </li>
          </ol>

          <p className="mt-3 text-xs">
            For production multi-tenant security,
            enable Supabase Auth + Row Level Security
            (RLS) policies on the workspace tables.
          </p>
        </div>
      </main>
    </div>
  );
}