"use client";

import { useState } from "react";
import {
  FileText,
  ShieldAlert,
  ShieldCheck,
  Clock,
  Database,
  ExternalLink,
  RefreshCw,
  Check,
  Search,
  CheckCircle2,
  X,
  FileSpreadsheet,
  File
} from "lucide-react";

export default function FileList({
  files = [],
  isLoading,
  driveError,
  isConnected,
  onReconnect,
  selectedFileIds = [],
  onToggleSelectFile,
  onSelectAll,
  onClearSelection,
}) {
  const [searchFilter, setSearchFilter] = useState("");
  const [activeTab, setActiveTab] = useState("all"); // "all", "docs", "sheets", "pdfs"

  if (isLoading) {
    return (
      <div className="bg-white border border-slate-200/80 rounded-2xl p-5 shadow-xs">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-heading text-sm font-bold text-slate-900">Drive Catalog</h3>
          <span className="text-[10px] font-medium text-slate-400 bg-slate-100 border border-slate-200/80 px-2 py-0.5 rounded-full">
            Loading...
          </span>
        </div>
        <div className="flex items-center gap-2.5 text-slate-500 text-xs py-8 justify-center">
          <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
          Fetching catalog...
        </div>
      </div>
    );
  }

  if (driveError) {
    return (
      <div className="bg-white border border-amber-300 rounded-2xl p-5 shadow-xs">
        <div className="flex items-center gap-2 text-amber-700 mb-2">
          <ShieldAlert size={18} className="flex-shrink-0 text-amber-600" />
          <h3 className="font-heading text-sm font-bold text-slate-900">Drive Permission Required</h3>
        </div>
        <p className="text-xs text-slate-600 mb-3 leading-relaxed">
          {driveError.message}
        </p>
        <div className="p-3 mb-3 rounded-xl bg-amber-50/70 border border-amber-200 text-xs text-slate-700 space-y-1">
          <p className="font-semibold text-amber-900">⚠️ Important step during Google sign-in:</p>
          <p className="text-[11px] text-slate-600">On the Google consent screen, make sure to <strong>check the checkbox</strong> for:</p>
          <p className="text-emerald-700 font-mono text-[10px] bg-white px-2 py-1 rounded border border-emerald-200">
            ☑ See and download all your Google Drive files
          </p>
        </div>
        <button
          onClick={onReconnect}
          className="btn-primary w-full justify-center text-xs py-2"
        >
          <RefreshCw size={13} /> Reconnect with Drive Access
        </button>
      </div>
    );
  }

  // Filter by category tab
  const categoryFiltered = files.filter((f) => {
    const name = (f.name || "").toLowerCase();
    const mime = (f.mimeType || "").toLowerCase();
    if (activeTab === "docs") {
      return (
        mime.includes("document") ||
        mime.includes("word") ||
        mime.includes("text") ||
        name.endsWith(".docx") ||
        name.endsWith(".doc") ||
        name.endsWith(".txt")
      );
    }
    if (activeTab === "sheets") {
      return (
        mime.includes("spreadsheet") ||
        mime.includes("excel") ||
        mime.includes("csv") ||
        name.endsWith(".xlsx") ||
        name.endsWith(".xls") ||
        name.endsWith(".csv")
      );
    }
    if (activeTab === "pdfs") {
      return mime.includes("pdf") || name.endsWith(".pdf");
    }
    return true;
  });

  // Filter by search query
  const filteredFiles = categoryFiltered.filter((f) =>
    (f.name || "").toLowerCase().includes(searchFilter.toLowerCase().trim())
  );

  const allFilteredSelected =
    filteredFiles.length > 0 &&
    filteredFiles.every((f) => selectedFileIds.includes(f.id));

  const getFileIcon = (file) => {
    const name = (file.name || "").toLowerCase();
    const mime = (file.mimeType || "").toLowerCase();
    if (mime.includes("spreadsheet") || name.endsWith(".xlsx") || name.endsWith(".csv")) {
      return <FileSpreadsheet size={14} className="text-emerald-600" />;
    }
    if (mime.includes("pdf") || name.endsWith(".pdf")) {
      return <FileText size={14} className="text-rose-500" />;
    }
    return <File size={14} className="text-blue-500" />;
  };

  return (
    <div className="bg-white border border-slate-200/80 rounded-2xl p-5 shadow-xs flex flex-col gap-3 min-h-[580px]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-heading text-sm font-bold text-slate-900">
              Drive Catalog
            </h3>
            <span className="text-[10px] font-medium text-slate-500 bg-slate-100 border border-slate-200/80 px-2 py-0.5 rounded-full">
              {files.length} {files.length === 1 ? "file loaded" : "files loaded"}
            </span>
          </div>
          <p className="text-[11px] text-slate-400 mt-0.5 leading-normal">
            Select file(s) to query, or ask without selecting to auto-discover.
          </p>
        </div>

        {/* Selected badge */}
        {selectedFileIds.length > 0 && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200 animate-fade-in flex-shrink-0">
            <CheckCircle2 size={12} />
            {selectedFileIds.length}
          </span>
        )}
      </div>

      {/* Filter Tabs (All Files, Docs, Sheets, PDFs) - exactly as shown in screenshot */}
      <div className="flex items-center gap-1 pt-1 border-b border-slate-100 pb-2.5">
        {[
          { key: "all", label: "All Files" },
          { key: "docs", label: "Docs" },
          { key: "sheets", label: "Sheets" },
          { key: "pdfs", label: "PDFs" },
        ].map((tab) => {
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={`text-[11px] font-medium px-2.5 py-1 rounded-lg transition-all ${
                isActive
                  ? "bg-slate-100 text-slate-900 font-semibold shadow-2xs border border-slate-200/60"
                  : "text-slate-400 hover:text-slate-700 hover:bg-slate-50"
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Search & Bulk selection if files exist */}
      {files.length > 0 && (
        <div className="flex flex-col gap-2 pt-0.5">
          <div className="relative">
            <Search
              size={13}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400"
            />
            <input
              type="text"
              placeholder="Search files..."
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              className="w-full bg-slate-50/70 border border-slate-200/90 rounded-lg pl-7 pr-7 py-1.5 text-xs text-slate-700 placeholder-slate-400 outline-none focus:border-blue-500 focus:bg-white focus:ring-1 focus:ring-blue-100 transition-all"
            />
            {searchFilter && (
              <button
                onClick={() => setSearchFilter("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                <X size={12} />
              </button>
            )}
          </div>

          <div className="flex items-center justify-between text-xs text-slate-500 px-0.5">
            <button
              type="button"
              onClick={allFilteredSelected ? onClearSelection : onSelectAll}
              className="hover:text-blue-600 transition-colors font-medium text-[11px]"
            >
              {allFilteredSelected ? "Deselect All" : "Select All"}
            </button>
            {selectedFileIds.length > 0 && (
              <button
                type="button"
                onClick={onClearSelection}
                className="text-slate-400 hover:text-rose-600 transition-colors text-[11px]"
              >
                Clear Selection
              </button>
            )}
          </div>
        </div>
      )}

      {/* Empty State / File List */}
      {files.length === 0 ? (
        <div className="flex flex-col items-center justify-center my-auto py-16 text-center">
          {/* Outline file icon in rounded rectangle matching screenshot */}
          <div className="w-12 h-12 rounded-2xl bg-slate-50 border border-slate-200/80 flex items-center justify-center text-slate-400 mb-3 shadow-2xs">
            <FileText size={22} className="stroke-[1.5]" />
          </div>
          <p className="font-semibold text-slate-700 text-xs">No files loaded yet</p>
          <p className="text-[11px] text-slate-400 mt-1 max-w-[210px] mx-auto leading-relaxed">
            Connect your Google Drive account above to automatically display accessible documents.
          </p>
        </div>
      ) : filteredFiles.length === 0 ? (
        <div className="py-10 text-center text-slate-400 text-xs">
          No files match "{searchFilter}".
        </div>
      ) : (
        <div className="flex flex-col gap-1.5 max-h-[460px] overflow-y-auto pr-1 scrollbar-thin scrollbar-thumb-slate-200">
          {filteredFiles.map((file) => {
            const isSelected = selectedFileIds.includes(file.id);
            const isConfidential = file.guardrail_status === "FLAGGED_CONFIDENTIAL";
            const isPassed = file.guardrail_status === "PASSED";

            return (
              <div
                key={file.id}
                onClick={() => onToggleSelectFile && onToggleSelectFile(file.id)}
                className={`group cursor-pointer flex items-center justify-between px-3 py-2 rounded-xl border transition-all duration-150 select-none ${
                  isSelected
                    ? "bg-blue-50/70 border-blue-200 text-slate-900 shadow-2xs"
                    : "bg-white border-slate-100 hover:border-slate-200 hover:bg-slate-50/60 text-slate-700"
                }`}
              >
                {/* Checkbox & File Info */}
                <div className="flex items-center gap-2.5 min-w-0">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onToggleSelectFile && onToggleSelectFile(file.id);
                    }}
                    className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 transition-all ${
                      isSelected
                        ? "bg-blue-600 border-blue-600 text-white"
                        : "border-slate-300 hover:border-slate-400 bg-white"
                    }`}
                  >
                    {isSelected && <Check size={11} className="stroke-[3]" />}
                  </button>

                  <div className="w-7 h-7 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-center flex-shrink-0">
                    {getFileIcon(file)}
                  </div>

                  <div className="min-w-0">
                    <p
                      className={`text-xs truncate max-w-[150px] ${
                        isSelected ? "font-semibold text-slate-900" : "font-medium text-slate-800"
                      }`}
                      title={file.name}
                    >
                      {file.name}
                    </p>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      {file.is_embedded ? (
                        <span className="flex items-center gap-1 text-[10px] text-blue-600 font-medium">
                          <Database size={9} /> Indexed
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-[10px] text-slate-400">
                          <Clock size={9} /> Ready
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Badges & Link */}
                <div className="flex items-center gap-1.5 flex-shrink-0">
                  {isConfidential && (
                    <span
                      className="text-[10px] font-semibold px-1.5 py-0.5 rounded-md bg-rose-50 text-rose-600 border border-rose-200 flex items-center gap-1"
                      title={file.confidentiality_reason || "Sensitive document"}
                    >
                      <ShieldAlert size={10} /> Blocked
                    </span>
                  )}
                  {isPassed && (
                    <span
                      className="text-[10px] font-semibold px-1.5 py-0.5 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1"
                      title="Verified Safe"
                    >
                      <ShieldCheck size={10} /> Clean
                    </span>
                  )}

                  {file.web_view_link && (
                    <a
                      href={file.web_view_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="text-slate-400 hover:text-slate-700 transition-colors p-1 rounded hover:bg-slate-100"
                      title="Open in Google Drive"
                    >
                      <ExternalLink size={12} />
                    </a>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
