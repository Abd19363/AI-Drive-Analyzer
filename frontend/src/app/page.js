"use client";

import { useState, useEffect, useRef } from "react";
import Navbar from "./components/Navbar";
import DriveConnector from "./components/DriveConnector";
import FileList from "./components/FileList";
import ChatInterface from "./components/ChatInterface";
import AuditLogsModal from "./components/AuditLogsModal";
import AdminPortal from "./components/AdminPortal";
import UserPortalAuth from "./components/UserPortalAuth";
import LandingPage from "./components/LandingPage";
import { AlertCircle, CheckCircle2, X, AlertTriangle, LogOut, RefreshCw, HardDrive, Zap, Sparkles, ArrowRight, ShieldCheck } from "lucide-react";

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
  const [showLanding, setShowLanding] = useState(true);
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
  const [assistantMode, setAssistantMode] = useState(null); // null (shows mode selection screen) | "drive" | "general"
  const activeQueryRef = useRef(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const portalParam = params.get("portal");
      if (portalParam === "admin") {
        setCurrentPortal("admin");
        setShowLanding(false);
      }
      const urlUserId = params.get("user_id");
      const connectedParam = params.get("connected");
      if (connectedParam === "true") {
        setShowLanding(false);
        setAssistantMode("drive");
        sessionStorage.setItem("ai_drive_assistant_mode", "drive");
      }
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
        const savedMode = sessionStorage.getItem("ai_drive_assistant_mode");
        if (savedMode) {
          setAssistantMode(savedMode);
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
      setAssistantMode(null);
      sessionStorage.removeItem("ai_drive_assistant_mode");
      setGoogleEmail("");
    }
    setAssistantMode(null);
    sessionStorage.removeItem("ai_drive_assistant_mode");
    setNotification({
      type: "success",
      message: `Welcome, ${data.full_name || data.email}! Please select an assistant mode below.`,
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
    setAssistantMode(null);
    sessionStorage.removeItem("ai_drive_assistant_mode");
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
      setAssistantMode(null);
      sessionStorage.removeItem("ai_drive_assistant_mode");
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
    const isGeneral = allowGeneralAnswer || assistantMode === "general";
    setIsProcessingQuery(true);
    setCurrentStep(isGeneral ? "ANSWERING" : "ANALYZING");
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
          selected_file_ids: isGeneral ? [] : fileIds,
          matched_file_ids: isGeneral ? [] : matchedFileIds,
          allow_general_answer: isGeneral,
          force_drive_search: isGeneral ? false : forceDriveSearch,
          mode: isGeneral ? "general" : "drive",
        }),
        signal: controller.signal,
      });
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        throw new Error(e.detail || `Server error ${res.status}`);
      }
      const data = await res.json();
      // Refresh file list in background — only for drive mode
      if (!isGeneral && data.analysis_required !== false) {
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

  if (showLanding) {
    return (
      <LandingPage
        onContinue={() => {
          setShowLanding(false);
          if (typeof window !== "undefined") {
            sessionStorage.setItem("ai_drive_visited_landing", "true");
          }
        }}
      />
    );
  }

  return (
    <main className="min-h-screen">
      {currentPortal === "admin" ? (
        <AdminPortal
          onBackToUserPortal={() => setCurrentPortal("user")}
          userId={userId}
          userEmail={portalEmail}
          onGoToLanding={() => setShowLanding(true)}
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
            onGoToLanding={() => setShowLanding(true)}
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

              {/* ──────────────── ASSISTANT INQUIRY MODE SELECTION OR WORKSPACE ──────────────── */}
              {assistantMode === null ? (
                /* 1. Mode Selection Screen (Shown upon signing in instead of chatbot) */
                <div className="max-w-4xl mx-auto px-6 py-12 flex flex-col items-center animate-fade-in text-center my-auto">
                  <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-blue-50 border border-blue-200/90 text-xs text-blue-700 font-bold mb-4 shadow-2xs">
                    <Sparkles size={14} className="text-blue-600" />
                    <span>Choose Your Inquiry Mode</span>
                  </div>

                  <h2 className="font-heading text-2xl sm:text-3xl font-extrabold text-slate-900 mb-3 tracking-tight">
                    How would you like to assist you today?
                  </h2>
                  <p className="text-slate-600 text-xs sm:text-sm max-w-xl mx-auto mb-10 leading-relaxed font-normal">
                    Select an inquiry mode below to begin. You can seamlessly switch between your Google Drive files and general questions at any time.
                  </p>

                  {/* Two Main Option Cards */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6 w-full text-left">
                    {/* Option 1: Google Drive Knowledge Base */}
                    <div
                      onClick={() => {
                        setAssistantMode("drive");
                        sessionStorage.setItem("ai_drive_assistant_mode", "drive");
                      }}
                      className="group relative p-7 rounded-3xl bg-white border border-slate-200/90 shadow-md hover:shadow-xl hover:border-blue-400 transition-all cursor-pointer flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-center justify-between mb-5">
                          <div className="w-12 h-12 rounded-2xl bg-blue-50 group-hover:bg-blue-600 text-blue-600 group-hover:text-white border border-blue-100 flex items-center justify-center transition-colors shadow-2xs">
                            <HardDrive size={22} />
                          </div>
                          <span className="text-[10px] font-bold text-blue-700 bg-blue-50 px-2.5 py-1 rounded-full border border-blue-200">
                            Document Grounded
                          </span>
                        </div>

                        <h3 className="font-heading text-lg font-bold text-slate-900 group-hover:text-blue-600 transition-colors mb-2">
                          Query Google Drive Documents
                        </h3>
                        <p className="text-xs text-slate-600 leading-relaxed mb-6">
                          Search through your private Drive files, analyze complex spreadsheets, and retrieve cited answers with built-in zero-knowledge privacy.
                        </p>

                        <div className="space-y-2 text-xs text-slate-600 border-t border-slate-100 pt-4 mb-6">
                          <div className="flex items-center gap-2">
                            <CheckCircle2 size={13} className="text-emerald-600 flex-shrink-0" />
                            <span>Instant PDF, Sheet & Doc catalog navigation</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <CheckCircle2 size={13} className="text-emerald-600 flex-shrink-0" />
                            <span>Exact page & table source citations</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <CheckCircle2 size={13} className="text-emerald-600 flex-shrink-0" />
                            <span>Multi-layer zero-knowledge privacy filter</span>
                          </div>
                        </div>
                      </div>

                      <button
                        type="button"
                        className="w-full inline-flex items-center justify-center gap-2 py-3 rounded-xl bg-blue-600 group-hover:bg-blue-700 text-white font-bold text-xs shadow-md shadow-blue-500/20 transition-all cursor-pointer"
                      >
                        <span>{isConnected ? "Open Drive Knowledge Base" : "Connect Google Drive & Query"}</span>
                        <ArrowRight size={14} className="group-hover:translate-x-0.5 transition-transform" />
                      </button>
                    </div>

                    {/* Option 2: General Knowledge Questions */}
                    <div
                      onClick={() => {
                        setAssistantMode("general");
                        sessionStorage.setItem("ai_drive_assistant_mode", "general");
                      }}
                      className="group relative p-7 rounded-3xl bg-white border border-slate-200/90 shadow-md hover:shadow-xl hover:border-indigo-400 transition-all cursor-pointer flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-center justify-between mb-5">
                          <div className="w-12 h-12 rounded-2xl bg-indigo-50 group-hover:bg-indigo-600 text-indigo-600 group-hover:text-white border border-indigo-100 flex items-center justify-center transition-colors shadow-2xs">
                            <Zap size={22} />
                          </div>
                          <span className="text-[10px] font-bold text-indigo-700 bg-indigo-50 px-2.5 py-1 rounded-full border border-indigo-200">
                            Zero Setup Required
                          </span>
                        </div>

                        <h3 className="font-heading text-lg font-bold text-slate-900 group-hover:text-indigo-600 transition-colors mb-2">
                          Ask General Questions
                        </h3>
                        <p className="text-xs text-slate-600 leading-relaxed mb-6">
                          Get immediate answers for programming guidance, document drafting, mathematics, research, and general problem-solving without connecting Google Drive.
                        </p>

                        <div className="space-y-2 text-xs text-slate-600 border-t border-slate-100 pt-4 mb-6">
                          <div className="flex items-center gap-2">
                            <CheckCircle2 size={13} className="text-emerald-600 flex-shrink-0" />
                            <span>Instant reasoning powered by Gemini 2.5 Flash</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <CheckCircle2 size={13} className="text-emerald-600 flex-shrink-0" />
                            <span>No Google Drive connection required</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <CheckCircle2 size={13} className="text-emerald-600 flex-shrink-0" />
                            <span>Interactive multi-session chat with auto-titling</span>
                          </div>
                        </div>
                      </div>

                      <button
                        type="button"
                        className="w-full inline-flex items-center justify-center gap-2 py-3 rounded-xl bg-indigo-600 group-hover:bg-indigo-700 text-white font-bold text-xs shadow-md shadow-indigo-500/20 transition-all cursor-pointer"
                      >
                        <span>Start General Chat</span>
                        <ArrowRight size={14} className="group-hover:translate-x-0.5 transition-transform" />
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                /* 2. Main Assistant Workspace (Drive Mode or General Mode) */
                <div className="max-w-[1440px] mx-auto px-6 py-4 flex flex-col gap-4 animate-fade-in">
                  {/* Mode Navigation Bar */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 rounded-2xl bg-white border border-slate-200/90 shadow-2xs">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-slate-400">Current Mode:</span>
                      <span
                        className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-bold ${
                          assistantMode === "drive"
                            ? "bg-blue-50 text-blue-700 border border-blue-200"
                            : "bg-indigo-50 text-indigo-700 border border-indigo-200"
                        }`}
                      >
                        {assistantMode === "drive" ? (
                          <>
                            <HardDrive size={13} />
                            <span>Google Drive Knowledge Base</span>
                          </>
                        ) : (
                          <>
                            <Zap size={13} />
                            <span>General Knowledge Assistant</span>
                          </>
                        )}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          const nextMode = assistantMode === "drive" ? "general" : "drive";
                          setAssistantMode(nextMode);
                          sessionStorage.setItem("ai_drive_assistant_mode", nextMode);
                        }}
                        className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold text-slate-700 bg-slate-100 hover:bg-slate-200/80 transition-all cursor-pointer"
                      >
                        <RefreshCw size={12} className="text-slate-500" />
                        <span>
                          Switch to {assistantMode === "drive" ? "General Questions" : "Google Drive"}
                        </span>
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setAssistantMode(null);
                          sessionStorage.removeItem("ai_drive_assistant_mode");
                        }}
                        className="px-2.5 py-1.5 rounded-xl text-xs font-medium text-slate-500 hover:text-slate-800 transition-colors cursor-pointer"
                        title="Return to mode selection screen"
                      >
                        Change Mode
                      </button>
                    </div>
                  </div>

                  {/* ── Mode 1: Google Drive Knowledge Base ── */}
                  {assistantMode === "drive" && (
                    <>
                      {/* If NOT connected: Show the clean Connect Google Drive view */}
                      {!isConnected ? (
                        <div className="max-w-2xl mx-auto py-12 px-6 text-center animate-fade-in bg-white rounded-3xl border border-slate-200/90 shadow-xl my-4">
                          <div className="w-16 h-16 rounded-2xl bg-blue-50 border border-blue-200 flex items-center justify-center text-blue-600 mx-auto mb-4 shadow-sm">
                            <HardDrive size={30} />
                          </div>
                          <span className="inline-flex items-center gap-1 text-[11px] font-bold text-blue-700 bg-blue-50 px-3 py-0.5 rounded-full border border-blue-200 mb-3">
                            Google Drive Authorization Required
                          </span>
                          <h2 className="font-heading text-2xl font-bold text-slate-900 mb-2">
                            Connect Your Google Drive
                          </h2>
                          <p className="text-slate-600 text-xs sm:text-sm max-w-md mx-auto mb-8 leading-relaxed">
                            Authorize read-only access to your Google Drive to index documents, analyze financial spreadsheets, and chat with exact source citations.
                          </p>

                          <div className="flex flex-col sm:flex-row items-center justify-center gap-3.5 mb-6">
                            <button
                              type="button"
                              onClick={handleConnectDrive}
                              disabled={isConnecting}
                              className="w-full sm:w-auto inline-flex items-center justify-center gap-2.5 px-8 py-3.5 rounded-2xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow-lg shadow-blue-500/25 transition-all cursor-pointer disabled:opacity-50"
                            >
                              {isConnecting ? (
                                <>
                                  <RefreshCw size={14} className="animate-spin" />
                                  <span>Connecting to Google...</span>
                                </>
                              ) : (
                                <>
                                  <HardDrive size={15} />
                                  <span>Connect Google Drive</span>
                                  <ArrowRight size={14} />
                                </>
                              )}
                            </button>

                            <button
                              type="button"
                              onClick={() => {
                                setAssistantMode("general");
                                sessionStorage.setItem("ai_drive_assistant_mode", "general");
                              }}
                              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-3.5 rounded-2xl bg-slate-50 hover:bg-slate-100 text-slate-700 font-semibold text-xs border border-slate-200 transition-all cursor-pointer"
                            >
                              <Zap size={14} className="text-indigo-600" />
                              <span>Ask General Questions Instead</span>
                            </button>
                          </div>

                          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-50 border border-slate-200/80 text-[11px] text-slate-500">
                            <ShieldCheck size={14} className="text-emerald-600" />
                            <span>Read-only permissions • Multi-layer zero-knowledge PII redaction</span>
                          </div>
                        </div>
                      ) : (
                        /* If Connected: Show Drive connector banner + 2-Column Catalog & Chat */
                        <>
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
                              isGeneralMode={false}
                            />
                          </div>
                        </>
                      )}
                    </>
                  )}

                  {/* ── Mode 2: General Knowledge Questions ── */}
                  {assistantMode === "general" && (
                    <div className="max-w-5xl mx-auto w-full animate-fade-in">
                      <ChatInterface
                        userId={userId}
                        portalEmail={portalEmail}
                        onAskQuestion={handleAskQuestion}
                        onResponseDisplayed={handleResponseDisplayed}
                        onCancelQuery={handleCancelQuery}
                        onRecordFallbackDecision={handleRecordFallbackDecision}
                        isProcessing={isProcessingQuery}
                        currentStep={currentStep}
                        selectedFiles={[]}
                        selectedFileIds={[]}
                        onDeselectFile={() => {}}
                        isGeneralMode={true}
                      />
                    </div>
                  )}
                </div>
              )}
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
