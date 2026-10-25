"use client";

import { HardDrive, ArrowRight, ShieldCheck, Sparkles, CheckCircle2, LogOut, Loader2 } from "lucide-react";

export default function DriveConnector({
  isConnected,
  userEmail,
  onConnect,
  onDisconnect,
  isLoading,
  isDisconnecting,
}) {
  /* ── CONNECTED STATE ── */
  if (isConnected) {
    return (
      <div className="bg-white border border-slate-200/80 rounded-2xl p-4 shadow-xs flex items-center justify-between gap-4 animate-fade-in">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-600 flex-shrink-0">
            <CheckCircle2 size={20} />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <p className="text-sm font-bold text-slate-900 leading-tight">Google Drive Connected</p>
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                Active
              </span>
            </div>
            {userEmail && (
              <p className="text-xs text-slate-500 truncate mt-0.5">{userEmail}</p>
            )}
          </div>
        </div>

        <button
          onClick={onDisconnect}
          disabled={isDisconnecting}
          className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-medium text-rose-600 bg-rose-50 border border-rose-200 hover:bg-rose-100 active:scale-[0.98] transition-all disabled:opacity-50 flex-shrink-0"
        >
          {isDisconnecting ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <LogOut size={14} />
          )}
          {isDisconnecting ? "Disconnecting…" : "Disconnect Google Drive"}
        </button>
      </div>
    );
  }

  /* ── NOT CONNECTED STATE (Exact match to screenshot banner) ── */
  return (
    <div className="bg-white border border-slate-200/80 rounded-2xl p-5 shadow-xs flex flex-col lg:flex-row lg:items-center justify-between gap-4 animate-fade-in">
      {/* Left Icon & Text */}
      <div className="flex items-start md:items-center gap-3.5 min-w-0">
        <div className="w-11 h-11 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600 flex-shrink-0 shadow-xs">
          <HardDrive size={20} />
        </div>
        <div className="min-w-0">
          <h2 className="font-heading text-sm font-bold text-slate-900">
            Connect Your Google Drive
          </h2>
          <p className="text-xs text-slate-500 mt-0.5 leading-relaxed max-w-2xl">
            Authorize secure read-only access to query your documents.{" "}
            <strong className="text-slate-800 font-semibold">Your documents remain private</strong>
            {" "}— files are processed securely only when you ask questions, protected by automated privacy and confidentiality screening.
          </p>
        </div>
      </div>

      {/* Right Badges & Action Button */}
      <div className="flex items-center gap-3 flex-shrink-0 flex-wrap">
        {/* Privacy Protected Badge */}
        <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-xl bg-emerald-50/70 border border-emerald-200/60">
          <ShieldCheck size={16} className="text-emerald-600 flex-shrink-0" />
          <div className="text-left">
            <div className="text-[11px] font-bold text-slate-800 leading-tight">Privacy Protected</div>
            <div className="text-[10px] text-slate-500 leading-tight">Zero persistent training</div>
          </div>
        </div>

        {/* Smart Analysis Badge */}
        <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-xl bg-purple-50/70 border border-purple-200/60">
          <Sparkles size={16} className="text-purple-600 flex-shrink-0" />
          <div className="text-left">
            <div className="text-[11px] font-bold text-slate-800 leading-tight">Smart Analysis</div>
            <div className="text-[10px] text-slate-500 leading-tight">Automated vector indexing</div>
          </div>
        </div>

        {/* Connect Button */}
        <button
          onClick={onConnect}
          disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white font-medium text-xs shadow-sm shadow-blue-500/20 transition-all flex-shrink-0"
        >
          <HardDrive size={14} />
          {isLoading ? "Connecting to Google..." : "Connect Google Drive"}
          <ArrowRight size={14} />
        </button>
      </div>
    </div>
  );
}

