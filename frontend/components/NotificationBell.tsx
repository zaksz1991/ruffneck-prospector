"use client";

import { useEffect, useState } from "react";

import { apiFetch } from "../lib/api";

export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<any[]>([]);
  const [unread, setUnread] = useState(0);

  async function load() {
    try {
      const res = await apiFetch(`/api/notifications?limit=20`);
      const data = await res.json();
      setItems(data.notifications || []);
      setUnread(data.unread || 0);
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, []);

  async function markAll() {
    await apiFetch(`/api/notifications/read`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ all: true }),
    });
    load();
  }

  return (
    <div className="relative">
      <button
        onClick={() => {
          const nextOpen = !open;
          setOpen(nextOpen);
          if (nextOpen) load();
        }}
        className="relative text-slate-400 hover:text-white text-sm px-2 py-1"
        title="Notifications"
      >
        🔔
        {unread > 0 && (
          <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[10px] rounded-full min-w-[16px] h-4 px-1 flex items-center justify-center">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-80 bg-slate-900 border border-slate-700 rounded-xl shadow-xl z-50 max-h-96 overflow-y-auto">
          <div className="flex justify-between items-center px-3 py-2 border-b border-slate-800">
            <span className="text-sm font-medium">Notifications</span>
            <button onClick={markAll} className="text-xs text-blue-400">Mark all read</button>
          </div>
          {items.length === 0 ? (
            <p className="text-xs text-slate-500 p-4">No notifications yet</p>
          ) : (
            <ul>
              {items.map((n) => (
                <li
                  key={n.id}
                  className={`px-3 py-2 border-b border-slate-800 text-sm ${n.read ? "opacity-60" : ""}`}
                >
                  <div className="font-medium text-slate-200">{n.title}</div>
                  {n.body && <div className="text-xs text-slate-500 mt-0.5 line-clamp-2">{n.body}</div>}
                  <div className="text-[10px] text-slate-600 mt-1 capitalize">{n.type}</div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
