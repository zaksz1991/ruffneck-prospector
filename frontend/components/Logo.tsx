import Link from "next/link";

export default function Logo({ className = "" }: { className?: string }) {
  return (
    <Link href="/" className={`flex items-center gap-2.5 font-bold text-xl ${className}`}>
      <img src="/favicon.svg" alt="RuffNeck" width={32} height={32} className="rounded-lg" />
      <span>
        RuffNeck <span className="text-blue-400">Prospector</span>
      </span>
    </Link>
  );
}
