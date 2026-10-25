"use client";

import { X, ShieldAlert, CheckCircle } from "lucide-react";

export default function AuditLogsModal({ isOpen, onClose, logs }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-3xl max-h-[85vh] flex flex-col rounded-2xl bg-white border border-slate-200/90 shadow-2xl overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/50">
          <div className="flex items-center gap-2">
            <ShieldAlert size={18} className="text-rose-500" />
            <h3 className="font-heading text-base font-bold text-slate-900">Security Audit Logs</h3>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-700 transition-colors p-1 rounded-lg hover:bg-slate-100"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 scrollbar-thin scrollbar-thumb-slate-200">
          <p className="text-xs text-slate-500 mb-4 leading-relaxed">
            Detailed record of confidential documents intercepted and protected from unauthorized access.
          </p>

          {logs.length === 0 ? (
            <div className="text-center py-12 text-slate-400">
              <CheckCircle size={32} className="text-emerald-500 mx-auto mb-2.5" />
              <p className="font-semibold text-slate-700 text-xs">No violations recorded.</p>
              <p className="text-[11px] mt-0.5 text-slate-400">All analyzed files have complied with privacy standards.</p>
            </div>
          ) : (
            <div className="border border-slate-200/80 rounded-xl overflow-hidden">
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className="text-left text-slate-500 bg-slate-50/80 border-b border-slate-200/80">
                    <th className="py-2.5 px-3.5 font-semibold">File Name</th>
                    <th className="py-2.5 px-3.5 font-semibold">Stage</th>
                    <th className="py-2.5 px-3.5 font-semibold">Detection Type</th>
                    <th className="py-2.5 px-3.5 font-semibold">Snippet</th>
                    <th className="py-2.5 px-3.5 font-semibold">Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log) => (
                    <tr key={log.id} className="border-b border-slate-100 hover:bg-slate-50/50 transition-colors">
                      <td className="py-2.5 px-3.5 font-medium text-slate-800">{log.file_name}</td>
                      <td className="py-2.5 px-3.5 text-blue-600 font-mono text-[11px]">{log.check_stage}</td>
                      <td className="py-2.5 px-3.5">
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-rose-50 text-rose-700 border border-rose-200">
                          {log.detection_type}
                        </span>
                      </td>
                      <td className="py-2.5 px-3.5 font-mono text-slate-500 text-[11px]">{log.snippet_matched || "N/A"}</td>
                      <td className="py-2.5 px-3.5 text-emerald-600 font-semibold">
                        {Math.round((log.confidence_score || 1.0) * 100)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
