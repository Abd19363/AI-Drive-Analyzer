"use client";

import { HardDrive, RefreshCw, Shield, ShieldCheck } from "lucide-react";

export default function Navbar({ isConnected, userEmail, onRefresh, onOpenAudit }) {
  return (
    <header className="sticky top-0 z-50 flex items-center justify-between px-8 py-3.5 border-b border-slate-200/80 bg-white/90 backdrop-blur-md">
      {/* Logo & Brand */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-xl bg-blue-600 flex items-center justify-center text-white shadow-sm shadow-blue-500/20 flex-shrink-0">
          <HardDrive size={18} />
        </div>
        <div className="flex items-center gap-2.5">
          <span className="font-heading text-base font-bold text-slate-900 tracking-tight">
            AI-Drive Analyzer
          </span>
          <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-600 border border-emerald-200/80">
            <ShieldCheck size={11} className="stroke-[2.5]" />
            SECURE
          </span>
        </div>
      </div>

      {/* Right Actions */}
      <div className="flex items-center gap-3">
        {isConnected ? (
          <>
            <span className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              Connected: {userEmail}
            </span>
            <span className="text-slate-300">|</span>
            <button
              onClick={onOpenAudit}
              className="text-xs font-medium text-slate-600 hover:text-slate-900 transition-colors flex items-center gap-1"
            >
              <Shield size={13} className="text-rose-500" />
              Security Audit
            </button>
            <button
              onClick={onRefresh}
              className="text-xs font-medium text-slate-600 hover:text-slate-900 transition-colors flex items-center gap-1"
              title="Refresh Google Drive files"
            >
              <RefreshCw size={13} />
              Sync
            </button>
          </>
        ) : (
          <>
            <span className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1 rounded-full bg-amber-50 text-amber-800 border border-amber-200/80">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
              Drive Disconnected
            </span>
            <span className="text-slate-300">|</span>
            <button
              onClick={onOpenAudit}
              className="text-xs font-medium text-slate-600 hover:text-slate-900 transition-colors"
            >
              Security Audit
            </button>
            <span className="text-slate-300">|</span>
            <span className="text-xs font-medium text-slate-500 hover:text-slate-800 transition-colors cursor-pointer">
              Privacy Policy
            </span>
          </>
        )}
      </div>
    </header>
  );
}

