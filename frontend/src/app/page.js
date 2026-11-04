"use client";

import { useState, useEffect, useRef } from "react";
import Navbar from "./components/Navbar";
import DriveConnector from "./components/DriveConnector";
import FileList from "./components/FileList";
import ChatInterface from "./components/ChatInterface";
import AuditLogsModal from "./components/AuditLogsModal";
import AdminPortal from "./components/AdminPortal";
import UserPortalAuth from "./components/UserPortalAuth";
import { AlertCircle, CheckCircle2, X, AlertTriangle, LogOut, RefreshCw } from "lucide-react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

async function fetchBackend(url, options) {
  try {
    return await fetch(url, options);
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error(
        `Cannot reach the backend at ${BACKEND_URL}. Check that the backend is running and reachable, then retry.`
      );
    }
    throw error;
  }
}

export default function Home() {
  const [currentPortal, setCurrentPortal] = useState("user"); // "user" | "admin"
  const [userId, setUserId] = useState(null);
  const [portalEmail, setPortalEmail] = useState("");
  const [googleEmail, setGoogleEmail] = useState("");
  const [isConnected, setIsConnected] = useState(false);
  const [driveFiles, setDriveFiles] = useState([]);
  const [selectedFileIds, setSelectedFileIds] = useState([]);
  const [isLoadingFiles, setIsLoadingFiles] = useState(false);
  const [isReloadingFiles, setIsReloadingFiles] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isDisconnecting, setIsDisconnecting] = useState(false);
  const [isProcessingQuery, setIsProcessingQuery] = useState(false);
  const [currentStep, setCurrentStep] = useState(null);
  const [isAuditModalOpen, setIsAuditModalOpen] = useState(false);
  const [auditLogs, setAuditLogs] = useState([]);
  const [notification, setNotification] = useState(null);
  const [driveError, setDriveError] = useState(null);
  const [isDisconnectRequiredModalOpen, setIsDisconnectRequiredModalOpen] = useState(false);
  const [isDisconnectingBeforeLogout, setIsDisconnectingBeforeLogout] = useState(false);
  const activeQueryRef = useRef(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const portalParam = params.get("portal");
      if (portalParam === "admin") {
        setCurrentPortal("admin");
      }
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
        sessionStorage.setItem("ai_drive_user_id", urlUserId);
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
        const storedId = sessionStorage.getItem("ai_drive_user_id");
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
        setPortalEmail(data.email || "");
        if (data.is_drive_connected && data.google_email) {
          setIsConnected(true);
          setGoogleEmail(data.google_email);
          fetchDriveFiles(uid);
        } else {
          setIsConnected(false);
          setGoogleEmail("");
        }
      } else {
        // User record was removed or invalid; reset to sign-in state
        sessionStorage.removeItem("ai_drive_user_id");
        sessionStorage.removeItem("ai_drive_user_email");
        sessionStorage.removeItem("ai_drive_user_token");
        localStorage.removeItem("ai_drive_user_id");
        localStorage.removeItem("ai_drive_user_email");
        localStorage.removeItem("ai_drive_user_token");
        setUserId(null);
        setPortalEmail("");
        setGoogleEmail("");
        setIsConnected(false);
      }
    } catch (err) {
      console.error("Error checking user status:", err);
    }
  };

  const handleUserAuthenticated = (data) => {
    setUserId(data.user_id);
    setPortalEmail(data.email || "");
    if (data.is_drive_connected && data.google_email) {
      setIsConnected(true);
      setGoogleEmail(data.google_email);
      fetchDriveFiles(data.user_id);
    } else {
      setIsConnected(false);
      setGoogleEmail("");
    }
    setNotification({
      type: "success",
      message: `Welcome, ${data.full_name || data.email}! Please connect a Google Drive account of your choice.`,
    });
  };

  const handleUserLogout = () => {
    if (isConnected) {
      setIsDisconnectRequiredModalOpen(true);
      setNotification({
        type: "error",
        message: "You must disconnect Google Drive before signing out of the User Portal.",
      });
      return;
    }
    if (userId) {
      sessionStorage.removeItem(`ai_drive_user_admin_token_${userId}`);
    }
    sessionStorage.removeItem("ai_drive_user_id");
    sessionStorage.removeItem("ai_drive_user_email");
    sessionStorage.removeItem("ai_drive_user_token");
    localStorage.removeItem("ai_drive_user_id");
    localStorage.removeItem("ai_drive_user_email");
    localStorage.removeItem("ai_drive_user_token");
    setUserId(null);
    setPortalEmail("");
    setGoogleEmail("");
    setIsConnected(false);
    setDriveFiles([]);
    setSelectedFileIds([]);
    setNotification({
      type: "success",
      message: "You have successfully signed out of the User Portal.",
    });
  };

  const handleDisconnectAndLogout = async () => {
    setIsDisconnectingBeforeLogout(true);
    try {
      if (userId) {
        await fetch(`${BACKEND_URL}/api/auth/disconnect?user_id=${userId}`, {
          method: "DELETE",
        });
      }
      setIsConnected(false);
      setGoogleEmail("");
      setDriveFiles([]);
      setSelectedFileIds([]);
      setDriveError(null);
      setIsDisconnectRequiredModalOpen(false);

      if (userId) {
        sessionStorage.removeItem(`ai_drive_user_admin_token_${userId}`);
      }
      sessionStorage.removeItem("ai_drive_user_id");
      sessionStorage.removeItem("ai_drive_user_email");
      sessionStorage.removeItem("ai_drive_user_token");
      localStorage.removeItem("ai_drive_user_id");
      localStorage.removeItem("ai_drive_user_email");
      localStorage.removeItem("ai_drive_user_token");
      setUserId(null);
      setPortalEmail("");
      setNotification({
        type: "success",
        message: "Google Drive was disconnected and you have signed out successfully.",
      });
    } catch (err) {
      console.error("Error disconnecting before logout:", err);
      setNotification({
        type: "error",
        message: "Failed to disconnect Google Drive: " + err.message,
      });
    } finally {
      setIsDisconnectingBeforeLogout(false);
    }
  };

  const fetchDriveFiles = async (uid, forceRefresh = false) => {
    const id = uid || userId;
    if (!id) return;
    if (forceRefresh) {
      setIsReloadingFiles(true);
    } else {
      setIsLoadingFiles(true);
    }
    try {
      const url = forceRefresh
        ? `${BACKEND_URL}/api/drive/files?user_id=${id}&refresh=true`
        : `${BACKEND_URL}/api/drive/files?user_id=${id}`;
      const res = await fetch(url);
      if (res.ok) {
        const d = await res.json();
        if (d.error) {
          setDriveError(d);
          setDriveFiles([]);
          setSelectedFileIds([]);
          if (forceRefresh) {
            setNotification({
              type: "error",
              message: d.message || "Failed to load files from Google Drive.",
            });
          }
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
          if (forceRefresh) {
            setNotification({
              type: "success",
              message: `Drive files reloaded successfully (${loadedFiles.length} ${
                loadedFiles.length === 1 ? "item" : "items"
              } loaded).`,
            });
          }
        }
      } else {
        if (forceRefresh) {
          const errData = await res.json().catch(() => ({}));
          setNotification({
            type: "error",
            message: errData.detail || "Failed to reload Google Drive files.",
          });
        }
      }
    } catch (err) {
      console.error("Error fetching files:", err);
      if (forceRefresh) {
        setNotification({
          type: "error",
          message: "Error reloading files: " + err.message,
        });
      }
    } finally {
      setIsLoadingFiles(false);
      setIsReloadingFiles(false);
    }
  };

  const handleReloadFiles = () => {
    fetchDriveFiles(userId, true);
  };

  const handleFetchFolderChildren = async (folderId) => {
    if (!userId || !folderId) return [];
    try {
      const res = await fetch(
        `${BACKEND_URL}/api/drive/folder-children?user_id=${userId}&folder_id=${folderId}`
      );
      if (res.ok) {
        const d = await res.json();
        const children = d.files || [];
        if (children.length > 0) {
          setDriveFiles((prev) => {
            const existingIds = new Set(prev.map((f) => f.id));
            const newChildren = children.filter((c) => !existingIds.has(c.id));
            return [...prev, ...newChildren];
          });
        }
        return children;
      }
    } catch (err) {
      console.error("Error fetching folder children:", err);
    }
    return [];
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
      const authUrlEndpoint = userId
        ? `${BACKEND_URL}/api/auth/google/url?redirect_state=${encodeURIComponent(userId)}`
        : `${BACKEND_URL}/api/auth/google/url`;
      const res = await fetch(authUrlEndpoint);
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
        setGoogleEmail("");
        setDriveFiles([]);
        setSelectedFileIds([]);
        setDriveError(null);
        setNotification({
          type: "success",
          message: "Google Drive disconnected successfully. Your User Portal account remains active.",
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

  const handleAskQuestion = async (
    queryText,
    fileIds = selectedFileIds,
    allowGeneralAnswer = false,
    matchedFileIds = [],
    forceDriveSearch = false,
    requestedQueryId,
    sessionId = null
  ) => {
    if (!userId) throw new Error("Please sign in to the User Portal first.");
    if (!isConnected) throw new Error("Please connect your Google Drive above to analyze your documents.");
    setIsProcessingQuery(true);
    setCurrentStep("ANALYZING");
    const queryId = requestedQueryId || crypto.randomUUID();
    const controller = new AbortController();
    activeQueryRef.current = { queryId, controller };
    try {
      const res = await fetchBackend(`${BACKEND_URL}/api/rag/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          session_id: sessionId,
          query_id: queryId,
          query: queryText,
          selected_file_ids: fileIds,
          matched_file_ids: matchedFileIds,
          allow_general_answer: allowGeneralAnswer,
          force_drive_search: forceDriveSearch,
        }),
        signal: controller.signal,
      });
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        throw new Error(e.detail || `Server error ${res.status}`);
      }
      const data = await res.json();
      // Refresh file list in background — must NOT block the return value
      if (data.analysis_required !== false) {
        fetchDriveFiles(userId).catch(console.error);
      }
      return { ...data, query_id: queryId };
    } finally {
      if (queryId && activeQueryRef.current?.queryId === queryId) {
        activeQueryRef.current = null;
      }
      setIsProcessingQuery(false);
      setCurrentStep(null);
    }
  };

  const handleResponseDisplayed = async (queryId, elapsedMs, status) => {
    const res = await fetchBackend(`${BACKEND_URL}/api/rag/ask/displayed`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query_id: queryId,
        elapsed_ms: elapsedMs,
        status,
      }),
    });
    if (!res.ok) {
      throw new Error(`Failed to report response display time (server error ${res.status})`);
    }
  };

  const handleRecordFallbackDecision = async (message, decision) => {
    const res = await fetch(`${BACKEND_URL}/api/rag/fallback-decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: userId,
        query: message.originalQuery,
        intent: message.intent,
        selected_file_ids: message.originalFileIds,
        decision,
      }),
    });
    if (!res.ok) {
      const e = await res.json().catch(() => ({}));
      throw new Error(e.detail || `Server error ${res.status}`);
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
      {currentPortal === "admin" ? (
        <AdminPortal
          onBackToUserPortal={() => setCurrentPortal("user")}
          userId={userId}
          userEmail={portalEmail}
        />
      ) : (
        <>
          <Navbar
            isConnected={isConnected}
            portalEmail={portalEmail}
            googleEmail={googleEmail}
            onRefresh={handleReloadFiles}
            isRefreshing={isReloadingFiles}
            onOpenAudit={handleOpenAuditModal}
            currentPortal={currentPortal}
            onSelectPortal={setCurrentPortal}
            isUserAuthenticated={Boolean(userId)}
            onUserLogout={handleUserLogout}
          />

          {!userId ? (
            <UserPortalAuth onAuthenticated={handleUserAuthenticated} />
          ) : (
            <>
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
                  portalEmail={portalEmail}
                  googleEmail={googleEmail}
                  onConnect={handleConnectDrive}
                  onDisconnect={handleDisconnectDrive}
                  onReloadFiles={handleReloadFiles}
                  isLoading={isConnecting}
                  isDisconnecting={isDisconnecting}
                  isReloading={isReloadingFiles}
                />

                {/* 2-Column Grid: Drive Catalog (left) & Chat Workspace (right) */}
                <div className="grid grid-cols-1 lg:grid-cols-[330px_1fr] gap-5 items-start">
                  <FileList
                    files={driveFiles}
                    isLoading={isLoadingFiles}
                    isReloading={isReloadingFiles}
                    driveError={driveError}
                    isConnected={isConnected}
                    onReconnect={handleConnectDrive}
                    onReloadFiles={handleReloadFiles}
                    onFetchFolderChildren={handleFetchFolderChildren}
                    selectedFileIds={selectedFileIds}
                    onToggleSelectFile={handleToggleSelectFile}
                    onSelectAll={handleSelectAll}
                    onClearSelection={handleClearSelection}
                  />

                  <ChatInterface
                    userId={userId}
                    portalEmail={portalEmail}
                    onAskQuestion={handleAskQuestion}
                    onResponseDisplayed={handleResponseDisplayed}
                    onCancelQuery={handleCancelQuery}
                    onRecordFallbackDecision={handleRecordFallbackDecision}
                    isProcessing={isProcessingQuery}
                    currentStep={currentStep}
                    selectedFiles={selectedFilesList}
                    selectedFileIds={selectedFileIds}
                    onDeselectFile={handleDeselectFile}
                  />
                </div>
              </div>
            </>
          )}

          <AuditLogsModal
            isOpen={isAuditModalOpen}
            onClose={() => setIsAuditModalOpen(false)}
            logs={auditLogs}
          />
        </>
      )}

      {/* Modal: Google Drive Disconnect Required Before Logout */}
      {isDisconnectRequiredModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-fade-in">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl border border-slate-200 animate-scale-in relative">
            <button
              onClick={() => setIsDisconnectRequiredModalOpen(false)}
              className="absolute top-4 right-4 p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
            >
              <X size={18} />
            </button>

            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-2xl bg-amber-50 border border-amber-200/80 flex items-center justify-center text-amber-600 flex-shrink-0">
                <AlertTriangle size={24} />
              </div>
              <div>
                <h3 className="font-heading text-base font-bold text-slate-900">
                  Disconnect Google Drive Required
                </h3>
                <p className="text-xs text-slate-500">Security & Privacy Guardrail</p>
              </div>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed mb-4">
              Before signing out of the User Portal, you must disconnect your connected Google Drive account{" "}
              {googleEmail && (
                <span className="font-semibold text-slate-900">({googleEmail})</span>
              )}.
            </p>

            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80 text-[11px] text-slate-600 mb-5 leading-normal">
              Disconnecting Google Drive revokes access to your Drive files for this session, ensuring your documents remain private and protected.
            </div>

            <div className="flex flex-col sm:flex-row items-center justify-end gap-2.5">
              <button
                type="button"
                onClick={() => setIsDisconnectRequiredModalOpen(false)}
                className="w-full sm:w-auto px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition-all"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isDisconnectingBeforeLogout}
                onClick={handleDisconnectAndLogout}
                className="w-full sm:w-auto flex items-center justify-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 transition-all shadow-md shadow-rose-500/20 disabled:opacity-50"
              >
                {isDisconnectingBeforeLogout ? (
                  <>
                    <RefreshCw size={13} className="animate-spin" />
                    Disconnecting...
                  </>
                ) : (
                  <>
                    <LogOut size={13} />
                    Disconnect Drive & Sign Out
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
