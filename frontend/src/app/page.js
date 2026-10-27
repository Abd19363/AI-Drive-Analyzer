"use client";

import { useState, useEffect, useRef } from "react";
import Navbar from "./components/Navbar";
import DriveConnector from "./components/DriveConnector";
import FileList from "./components/FileList";
import ChatInterface from "./components/ChatInterface";
import AuditLogsModal from "./components/AuditLogsModal";
import { AlertCircle, CheckCircle2, X } from "lucide-react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export default function Home() {
  const [userId, setUserId] = useState(null);
  const [userEmail, setUserEmail] = useState("");
  const [isConnected, setIsConnected] = useState(false);
  const [driveFiles, setDriveFiles] = useState([]);
  const [selectedFileIds, setSelectedFileIds] = useState([]);
  const [isLoadingFiles, setIsLoadingFiles] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isDisconnecting, setIsDisconnecting] = useState(false);
  const [isProcessingQuery, setIsProcessingQuery] = useState(false);
  const [currentStep, setCurrentStep] = useState(null);
  const [isAuditModalOpen, setIsAuditModalOpen] = useState(false);
  const [auditLogs, setAuditLogs] = useState([]);
  const [notification, setNotification] = useState(null);
  const [driveError, setDriveError] = useState(null);
  const activeQueryRef = useRef(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const urlUserId = params.get("user_id");
      const connectedParam = params.get("connected");
      const errorParam = params.get("error");

      if (errorParam) {
        setNotification({
          type: "error",
          message: `Connection Error: ${decodeURIComponent(errorParam)}`,
        });
        window.history.replaceState({}, document.title, window.location.pathname);
      } else if (urlUserId) {
        setUserId(urlUserId);
        localStorage.setItem("ai_drive_user_id", urlUserId);
        if (connectedParam === "true") {
          setNotification({
            type: "success",
            message: "Google Drive successfully connected and authorized!",
          });
        }
        checkUserStatus(urlUserId);
        window.history.replaceState({}, document.title, window.location.pathname);
      } else {
        const storedId = localStorage.getItem("ai_drive_user_id");
        if (storedId) {
          setUserId(storedId);
          checkUserStatus(storedId);
        }
      }
    }
  }, []);

  const checkUserStatus = async (uid) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/me?user_id=${uid}`);
      if (res.ok) {
        const data = await res.json();
        setIsConnected(data.is_drive_connected);
        setUserEmail(data.google_email || data.email);
        if (data.is_drive_connected) {
          fetchDriveFiles(uid);
        }
      }
    } catch (err) {
      console.error("Error checking user status:", err);
    }
  };

  const fetchDriveFiles = async (uid) => {
    const id = uid || userId;
    if (!id) return;
    setIsLoadingFiles(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/drive/files?user_id=${id}`);
      if (res.ok) {
        const d = await res.json();
        if (d.error) {
          setDriveError(d);
          setDriveFiles([]);
          setSelectedFileIds([]);
        } else {
          setDriveError(null);
          const loadedFiles = d.files || [];
          setDriveFiles(loadedFiles);
          // Keep only previously valid selections; default to empty for auto-discovery
          setSelectedFileIds((prev) => {
            const loadedIds = new Set(loadedFiles.map((f) => f.id));
            const valid = prev.filter((pid) => loadedIds.has(pid));
            return valid;
          });
        }
      }
    } catch (err) {
      console.error("Error fetching files:", err);
    } finally {
      setIsLoadingFiles(false);
    }
  };

  const handleToggleSelectFile = (fileId) => {
    setSelectedFileIds((prev) =>
      prev.includes(fileId) ? prev.filter((id) => id !== fileId) : [...prev, fileId]
    );
  };

  const handleSelectAll = () => {
    setSelectedFileIds(driveFiles.map((f) => f.id));
  };

  const handleClearSelection = () => {
    setSelectedFileIds([]);
  };

  const handleDeselectFile = (fileId) => {
    setSelectedFileIds((prev) => prev.filter((id) => id !== fileId));
  };

  const handleConnectDrive = async () => {
    setIsConnecting(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/google/url`);
      const data = await res.json();
      if (data.authorization_url) {
        window.location.href = data.authorization_url;
      }
    } catch (err) {
      setNotification({
        type: "error",
        message: "Failed to initiate Google OAuth: " + err.message,
      });
      setIsConnecting(false);
    }
  };

  const handleDisconnectDrive = async () => {
    if (!userId) return;
    setIsDisconnecting(true);
    try {
      const res = await fetch(
        `${BACKEND_URL}/api/auth/disconnect?user_id=${userId}`,
        { method: "DELETE" }
      );
      if (res.ok) {
        setIsConnected(false);
        setUserEmail("");
        setDriveFiles([]);
        setSelectedFileIds([]);
        setDriveError(null);
        setUserId(null);
        localStorage.removeItem("ai_drive_user_id");
        setNotification({
          type: "success",
          message: "Google Drive disconnected successfully.",
        });
      } else {
        const e = await res.json();
        setNotification({
          type: "error",
          message: "Disconnect failed: " + (e.detail || "Unknown error"),
        });
      }
    } catch (err) {
      setNotification({
        type: "error",
        message: "Disconnect failed: " + err.message,
      });
    } finally {
      setIsDisconnecting(false);
    }
  };

  const handleOpenAuditModal = async () => {
    if (!userId) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/guardrails/logs?user_id=${userId}`);
      if (res.ok) {
        const d = await res.json();
        setAuditLogs(d.logs || []);
      }
    } catch (err) {
      console.error("Error loading audit logs:", err);
    }
    setIsAuditModalOpen(true);
  };

  const handleAskQuestion = async (queryText, fileIds = selectedFileIds) => {
    if (!userId) throw new Error("Please connect your Google Drive first.");
    const queryId = crypto.randomUUID();
    const controller = new AbortController();
    activeQueryRef.current = { queryId, controller };
    setIsProcessingQuery(true);
    setCurrentStep("ANALYZING");
    const t1 = setTimeout(() => setCurrentStep("GUARDRAILS"), 800);
    const t2 = setTimeout(() => setCurrentStep("EMBEDDING"), 1800);
    const t3 = setTimeout(() => setCurrentStep("ANSWERING"), 3000);

    try {
      const res = await fetch(`${BACKEND_URL}/api/rag/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          query_id: queryId,
          query: queryText,
          selected_file_ids: fileIds,
        }),
        signal: controller.signal,
      });
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        throw new Error(e.detail || `Server error ${res.status}`);
      }
      const data = await res.json();
      // Refresh file list in background — must NOT block the return value
      fetchDriveFiles(userId).catch(console.error);
      return data;
    } finally {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      if (activeQueryRef.current?.queryId === queryId) {
        activeQueryRef.current = null;
      }
      setIsProcessingQuery(false);
      setCurrentStep(null);
    }
  };

  const handleCancelQuery = async () => {
    const activeQuery = activeQueryRef.current;
    if (!activeQuery) return;

    try {
      await fetch(`${BACKEND_URL}/api/rag/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          query_id: activeQuery.queryId,
        }),
      });
    } catch (err) {
      console.error("Failed to cancel query on the server:", err);
    } finally {
      activeQuery.controller.abort();
    }
  };

  const selectedFilesList = driveFiles.filter((f) => selectedFileIds.includes(f.id));

  return (
    <main className="min-h-screen">
      <Navbar
        isConnected={isConnected}
        userEmail={userEmail}
        onRefresh={() => fetchDriveFiles(userId)}
        onOpenAudit={handleOpenAuditModal}
      />

      {/* Notification banner (exact light mint styling from picture) */}
      {notification && (
        <div className="max-w-[1440px] mx-auto px-6 pt-3">
          <div
            className={`flex items-center justify-between px-4 py-2.5 rounded-xl border text-xs font-medium animate-fade-in ${
              notification.type === "error"
                ? "bg-rose-50 border-rose-200 text-rose-800"
                : "bg-emerald-50/90 border-emerald-200/90 text-emerald-800"
            }`}
          >
            <div className="flex items-center gap-2">
              {notification.type === "error" ? (
                <AlertCircle size={15} className="text-rose-600 flex-shrink-0" />
              ) : (
                <CheckCircle2 size={15} className="text-emerald-600 flex-shrink-0" />
              )}
              <span>{notification.message}</span>
            </div>
            <button
              onClick={() => setNotification(null)}
              className="text-slate-400 hover:text-slate-700 transition-colors p-0.5"
            >
              <X size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Main Container */}
      <div className="max-w-[1440px] mx-auto px-6 py-5 flex flex-col gap-5">
        {/* Full-width Connect Google Drive Banner (matching screenshot) */}
        <DriveConnector
          isConnected={isConnected}
          userEmail={userEmail}
          onConnect={handleConnectDrive}
          onDisconnect={handleDisconnectDrive}
          isLoading={isConnecting}
          isDisconnecting={isDisconnecting}
        />

        {/* 2-Column Grid: Drive Catalog (left) & Chat Workspace (right) */}
        <div className="grid grid-cols-1 lg:grid-cols-[330px_1fr] gap-5 items-start">
          <FileList
            files={driveFiles}
            isLoading={isLoadingFiles}
            driveError={driveError}
            isConnected={isConnected}
            onReconnect={handleConnectDrive}
            selectedFileIds={selectedFileIds}
            onToggleSelectFile={handleToggleSelectFile}
            onSelectAll={handleSelectAll}
            onClearSelection={handleClearSelection}
          />

          <ChatInterface
            onAskQuestion={handleAskQuestion}
            onCancelQuery={handleCancelQuery}
            isProcessing={isProcessingQuery}
            currentStep={currentStep}
            selectedFiles={selectedFilesList}
            selectedFileIds={selectedFileIds}
            onDeselectFile={handleDeselectFile}
          />
        </div>
      </div>

      <AuditLogsModal
        isOpen={isAuditModalOpen}
        onClose={() => setIsAuditModalOpen(false)}
        logs={auditLogs}
      />
    </main>
  );
}
