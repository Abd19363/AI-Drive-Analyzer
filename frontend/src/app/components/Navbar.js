import { HardDrive, RefreshCw, Shield, ShieldCheck, User, LogOut } from "lucide-react";

export default function Navbar({
  isConnected,
  userEmail,
  onRefresh,
  isRefreshing,
  onOpenAudit,
  currentPortal = "user",
  onSelectPortal,
  isUserAuthenticated = false,
  onUserLogout,
}) {
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

      {/* Portal Switcher (User Portal vs Admin Portal) */}
      <div className="flex items-center p-1 bg-slate-100/90 rounded-xl border border-slate-200/80 shadow-2xs">
        <button
          type="button"
          onClick={() => onSelectPortal && onSelectPortal("user")}
          className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
            currentPortal === "user"
              ? "bg-white text-blue-700 shadow-xs border border-slate-200/60"
              : "text-slate-500 hover:text-slate-800"
          }`}
        >
          <User size={13} />
          User Portal
        </button>
        <button
          type="button"
          onClick={() => onSelectPortal && onSelectPortal("admin")}
          className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
            currentPortal === "admin"
              ? "bg-indigo-600 text-white shadow-xs border border-indigo-700"
              : "text-slate-500 hover:text-slate-800"
          }`}
        >
          <Shield size={13} className={currentPortal === "admin" ? "text-white" : "text-indigo-600"} />
          Admin Portal
        </button>
      </div>

      {/* Right Actions */}
      <div className="flex items-center gap-3">
        {isUserAuthenticated ? (
          <>
            {isConnected ? (
              <>
                <span className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  Drive: {userEmail}
                </span>
                <span className="text-slate-300">|</span>
                <button
                  onClick={onRefresh}
                  disabled={isRefreshing}
                  className="text-xs font-medium text-slate-600 hover:text-slate-900 transition-colors flex items-center gap-1.5 disabled:opacity-50"
                  title="Re-load Google Drive files"
                >
                  <RefreshCw size={13} className={isRefreshing ? "animate-spin text-blue-600" : ""} />
                  {isRefreshing ? "Reloading..." : "Re-load files"}
                </button>
              </>
            ) : (
              <span className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1 rounded-full bg-amber-50 text-amber-800 border border-amber-200/80">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                Drive Disconnected
              </span>
            )}

            <span className="text-slate-300">|</span>
            <button
              onClick={onOpenAudit}
              className="text-xs font-medium text-slate-600 hover:text-slate-900 transition-colors flex items-center gap-1"
            >
              <Shield size={13} className="text-rose-500" />
              Security Audit
            </button>

            <span className="text-slate-300">|</span>
            <button
              onClick={onUserLogout}
              className="text-xs font-semibold text-rose-600 hover:text-rose-700 transition-all flex items-center gap-1 px-2.5 py-1 rounded-lg hover:bg-rose-50 border border-transparent hover:border-rose-200"
              title="Sign out of User Portal"
            >
              <LogOut size={13} />
              Sign Out
            </button>
          </>
        ) : (
          <span className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
            <User size={12} className="text-slate-400" />
            Guest Session
          </span>
        )}
      </div>
    </header>
  );
}

