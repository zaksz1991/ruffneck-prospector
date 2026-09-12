import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "RuffNeck Prospector",
    template: "%s · RuffNeck Prospector",
  },
  description:
    "Free multi-platform lead prospecting, CRM pipeline, email sequences, and branded document generation.",
  applicationName: "RuffNeck Prospector",
  authors: [{ name: "RuffNeck" }],
  keywords: [
    "lead generation",
    "prospecting",
    "CRM",
    "email outreach",
    "LinkedIn",
    "Google Maps",
    "free",
  ],
  manifest: "/site.webmanifest",
  icons: {
    icon: [{ url: "/favicon.svg", type: "image/svg+xml" }],
    apple: [{ url: "/icon-192.svg", type: "image/svg+xml" }],
    shortcut: ["/favicon.svg"],
  },
  openGraph: {
    title: "RuffNeck Prospector",
    description:
      "Free multi-platform lead prospecting, CRM pipeline, and outreach.",
    type: "website",
    siteName: "RuffNeck Prospector",
  },
};

export const viewport: Viewport = {
  themeColor: "#1e3a5f",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased bg-slate-950 text-slate-100">{children}</body>
    </html>
  );
}
