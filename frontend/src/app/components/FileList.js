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
  File,
  Folder,
  FolderOpen,
  ChevronRight,
  ChevronDown,
  Loader2,
} from "lucide-react";

export default function FileList({
  files = [],
  isLoading,
  isReloading,
  driveError,
  isConnected,
  onReconnect,
  onReloadFiles,
  onFetchFolderChildren,
  selectedFileIds = [],
  onToggleSelectFile,
  onSelectAll,
  onClearSelection,
}) {
  const [searchFilter, setSearchFilter] = useState("");
  const [activeTab, setActiveTab] = useState("all"); // "all", "folders", "docs", "sheets", "pdfs"
  const [expandedFolderIds, setExpandedFolderIds] = useState(new Set());
  const [loadingFolderIds, setLoadingFolderIds] = useState(new Set());

  const isFolder = (file) =>
    Boolean(
      file.is_folder ||
      file.mime_type === "application/vnd.google-apps.folder" ||
      file.mimeType === "application/vnd.google-apps.folder"
    );

  const getChildrenOf = (parentId) => {
    return files.filter((f) => f.parent_id === parentId);
  };

  const handleToggleFolder = async (folderId) => {
    const isExpanding = !expandedFolderIds.has(folderId);
    setExpandedFolderIds((prev) => {
      const next = new Set(prev);
      if (next.has(folderId)) {
        next.delete(folderId);
      } else {
        next.add(folderId);
      }
      return next;
    });

    if (isExpanding) {
      const hasChildren = files.some((f) => f.parent_id === folderId);
      if (!hasChildren && onFetchFolderChildren) {
        setLoadingFolderIds((prev) => new Set(prev).add(folderId));
        try {
          await onFetchFolderChildren(folderId);
        } finally {
          setLoadingFolderIds((prev) => {
            const next = new Set(prev);
            next.delete(folderId);
            return next;
          });
        }
      }
    }
  };

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
    const isF = isFolder(f);
    if (activeTab === "folders") {
      return isF;
    }
    if (activeTab === "docs") {
      if (isF) return false;
      const name = (f.name || "").toLowerCase();
      const mime = (f.mime_type || f.mimeType || "").toLowerCase();
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
      if (isF) return false;
      const name = (f.name || "").toLowerCase();
      const mime = (f.mime_type || f.mimeType || "").toLowerCase();
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
      if (isF) return false;
      const name = (f.name || "").toLowerCase();
      const mime = (f.mime_type || f.mimeType || "").toLowerCase();
      return mime.includes("pdf") || name.endsWith(".pdf");
    }
    return true; // "all"
  });

  // Search filter
  const isSearching = Boolean(searchFilter.trim());
  const searchMatchedFiles = categoryFiltered.filter((f) =>
    (f.name || "").toLowerCase().includes(searchFilter.toLowerCase().trim())
  );

  // Group into hierarchical roots when not searching
  const allFolderIds = new Set(files.filter(isFolder).map((f) => f.id));
  const rootDisplayItems = isSearching
    ? searchMatchedFiles
    : activeTab === "folders"
    ? categoryFiltered.filter((f) => isFolder(f) && (!f.parent_id || !allFolderIds.has(f.parent_id)))
    : activeTab === "all"
    ? categoryFiltered.filter((f) => !f.parent_id || !allFolderIds.has(f.parent_id))
    : categoryFiltered;

  const allFilteredSelected =
    rootDisplayItems.length > 0 &&
    rootDisplayItems.every((f) => selectedFileIds.includes(f.id));

  const getFileIcon = (file, isExpanded = false) => {
    if (isFolder(file)) {
      return isExpanded ? (
        <FolderOpen size={14} className="text-amber-600 fill-amber-500/20" />
      ) : (
        <Folder size={14} className="text-amber-500 fill-amber-500/20" />
      );
    }
    const name = (file.name || "").toLowerCase();
    const mime = (file.mime_type || file.mimeType || "").toLowerCase();
    if (mime.includes("spreadsheet") || name.endsWith(".xlsx") || name.endsWith(".csv")) {
      return <FileSpreadsheet size={14} className="text-emerald-600" />;
    }
    if (mime.includes("pdf") || name.endsWith(".pdf")) {
      return <FileText size={14} className="text-rose-500" />;
    }
    return <File size={14} className="text-blue-500" />;
  };

  // Recursive renderer for files and expandable folders/sub-folders
  const renderTreeItem = (file, depth = 0) => {
    const isFolderItem = isFolder(file);
    const isSelected = selectedFileIds.includes(file.id);
    const isConfidential = file.guardrail_status === "FLAGGED_CONFIDENTIAL";
    const isPassed = file.guardrail_status === "PASSED";
    const isExpanded = expandedFolderIds.has(file.id);
    const isLoadingThisFolder = loadingFolderIds.has(file.id);
    const children = isFolderItem ? getChildrenOf(file.id) : [];

    return (
      <div key={file.id} className="flex flex-col">
        <div
          onClick={() => {
            if (isFolderItem) {
              handleToggleFolder(file.id);
            } else if (onToggleSelectFile) {
              onToggleSelectFile(file.id);
            }
          }}
          className={`group cursor-pointer flex items-center justify-between px-3 py-2 rounded-xl border transition-all duration-150 select-none ${
            isSelected
              ? "bg-blue-50/70 border-blue-200 text-slate-900 shadow-2xs"
              : isFolderItem && isExpanded
              ? "bg-amber-50/40 border-amber-200/80 text-slate-900 shadow-2xs"
              : "bg-white border-slate-100 hover:border-slate-200 hover:bg-slate-50/60 text-slate-700"
          }`}
        >
          {/* Checkbox & File / Folder Info */}
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
              title={isSelected ? "Deselect item" : "Select item"}
            >
              {isSelected && <Check size={11} className="stroke-[3]" />}
            </button>

            <div
              className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 border ${
                isFolderItem
                  ? "bg-amber-50 border-amber-100/80"
                  : "bg-slate-50 border-slate-100"
              }`}
            >
              {getFileIcon(file, isExpanded)}
            </div>

            <div className="min-w-0">
              <p
                className={`text-xs truncate max-w-[150px] ${
                  isSelected || (isFolderItem && isExpanded)
                    ? "font-semibold text-slate-900"
                    : "font-medium text-slate-800"
                }`}
                title={file.name}
              >
                {file.name}
              </p>
              <div className="flex items-center gap-1.5 mt-0.5">
                {isFolderItem ? (
                  <span className="flex items-center gap-1 text-[10px] text-amber-700 font-medium">
                    <Folder size={9} /> Folder
                    {children.length > 0 && ` (${children.length})`}
                  </span>
                ) : file.is_embedded ? (
                  <span className="flex items-center gap-1 text-[10px] text-blue-600 font-medium">
                    <Database size={9} /> Indexed
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-[10px] text-slate-400">
                    <Clock size={9} /> Ready
                  </span>
                )}
                {file.folder_name && isSearching && (
                  <span className="text-[9px] text-slate-400 bg-slate-100 px-1.5 py-0.2 rounded truncate max-w-[90px]">
                    in: {file.folder_name}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Badges & Right Action (Chevron for Folders, External Link for Files) */}
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

            {/* FOR FOLDERS / SUB-FOLDERS: Arrow toggles inline view in the same UI place */}
            {isFolderItem ? (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  handleToggleFolder(file.id);
                }}
                className={`p-1 rounded-md transition-all ${
                  isExpanded
                    ? "text-blue-700 bg-blue-100 hover:bg-blue-200/80"
                    : "text-slate-400 hover:text-slate-700 hover:bg-slate-100"
                }`}
                title={isExpanded ? "Collapse folder contents" : "Show sub-files and sub-folders"}
              >
                {isLoadingThisFolder ? (
                  <Loader2 size={13} className="animate-spin text-blue-600" />
                ) : isExpanded ? (
                  <ChevronDown size={14} className="stroke-[2.5]" />
                ) : (
                  <ChevronRight size={14} className="stroke-[2.5]" />
                )}
              </button>
            ) : (
              /* FOR FILES: Arrow / Link opens file in new tab in Google Drive */
              file.web_view_link && (
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
              )
            )}
          </div>
        </div>

        {/* INLINE SUB-ITEMS: Shows sub-files and sub-folders in the same UI place */}
        {isFolderItem && isExpanded && (
          <div className="pl-3.5 ml-3 my-1 border-l-2 border-amber-300/80 flex flex-col gap-1.5 animate-fade-in">
            {children.length === 0 ? (
              <div className="text-[11px] text-slate-400 py-1.5 pl-2 italic flex items-center gap-1.5">
                {isLoadingThisFolder ? (
                  <>
                    <Loader2 size={11} className="animate-spin text-blue-500" />
                    <span>Loading folder contents...</span>
                  </>
                ) : (
                  <span>No sub-files or folders inside</span>
                )}
              </div>
            ) : (
              children.map((child) => renderTreeItem(child, depth + 1))
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="bg-white border border-slate-200/80 rounded-2xl p-5 shadow-xs flex flex-col gap-3 min-h-[580px]">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
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

        {/* Right Header Actions */}
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {isConnected && (
            <button
              type="button"
              onClick={onReloadFiles}
              disabled={isReloading || isLoading}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-semibold text-slate-700 bg-slate-50 border border-slate-200 hover:bg-slate-100 hover:border-slate-300 active:scale-95 transition-all disabled:opacity-50 shadow-2xs"
              title="Re-load files from Google Drive"
            >
              <RefreshCw
                size={11}
                className={isReloading ? "animate-spin text-blue-600" : "text-slate-500"}
              />
              <span>{isReloading ? "Reloading..." : "Re-load files"}</span>
            </button>
          )}

          {/* Selected badge */}
          {selectedFileIds.length > 0 && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200 animate-fade-in flex-shrink-0">
              <CheckCircle2 size={12} />
              {selectedFileIds.length}
            </span>
          )}
        </div>
      </div>

      {/* Filter Tabs: All Files | Folders | Docs | Sheets | PDFs */}
      <div className="flex items-center gap-1 pt-1 border-b border-slate-100 pb-2.5 overflow-x-auto scrollbar-none">
        {[
          { key: "all", label: "All Files" },
          { key: "folders", label: "Folders" },
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
              className={`text-[11px] font-medium px-2.5 py-1 rounded-lg transition-all flex-shrink-0 ${
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

      {/* Empty State / File Tree List */}
      {files.length === 0 ? (
        <div className="flex flex-col items-center justify-center my-auto py-16 text-center">
          <div className="w-12 h-12 rounded-2xl bg-slate-50 border border-slate-200/80 flex items-center justify-center text-slate-400 mb-3 shadow-2xs">
            <FileText size={22} className="stroke-[1.5]" />
          </div>
          <p className="font-semibold text-slate-700 text-xs">No files loaded yet</p>
          <p className="text-[11px] text-slate-400 mt-1 max-w-[210px] mx-auto leading-relaxed">
            {isConnected
              ? "No supported documents detected in your Drive yet, or catalog is refreshing."
              : "Connect your Google Drive account above to automatically display accessible documents."}
          </p>
          {isConnected && (
            <button
              type="button"
              onClick={onReloadFiles}
              disabled={isReloading || isLoading}
              className="mt-3.5 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 transition-all active:scale-95 disabled:opacity-50 shadow-2xs"
            >
              <RefreshCw size={12} className={isReloading ? "animate-spin text-blue-600" : "text-blue-600"} />
              <span>{isReloading ? "Reloading..." : "Re-load files"}</span>
            </button>
          )}
        </div>
      ) : rootDisplayItems.length === 0 ? (
        <div className="py-10 text-center text-slate-400 text-xs">
          {searchFilter
            ? `No items match "${searchFilter}".`
            : activeTab === "folders"
            ? "No folders found in Google Drive."
            : `No items found in ${activeTab}.`}
        </div>
      ) : (
        <div className="flex flex-col gap-1.5 max-h-[460px] overflow-y-auto pr-1 scrollbar-thin scrollbar-thumb-slate-200">
          {rootDisplayItems.map((item) => renderTreeItem(item, 0))}
        </div>
      )}
    </div>
  );
}
