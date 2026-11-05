"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
  Send,
  Square,
  Sparkles,
  ShieldCheck,
  AlertTriangle,
  FileText,
  Search,
  CheckCircle2,
  Copy,
  Check,
  ThumbsUp,
  X,
  ChevronRight,
  FileCheck2,
  MessageSquare,
  Plus,
  Trash2,
  RotateCcw,
  ChevronDown,
} from "lucide-react";
import MarkdownRenderer from "./MarkdownRenderer";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

const PIPELINE_STEPS = [
  { key: "ANALYZING", stepNum: "1", label: "Finding Relevant Files" },
  { key: "GUARDRAILS", stepNum: "2", label: "Privacy & Security Check" },
  { key: "EMBEDDING", stepNum: "3", label: "Reading Content" },
  { key: "ANSWERING", stepNum: "4", label: "Generating Answer" },
];

const STEP_ORDER = ["ANALYZING", "GUARDRAILS", "EMBEDDING", "ANSWERING"];

function getStepState(stepKey, currentStep) {
  if (!currentStep) return "idle";
  if (currentStep === "DIRECT_ANSWER") {
    return stepKey === "ANSWERING" ? "active" : "idle";
  }
  const ci = STEP_ORDER.indexOf(currentStep);
  const si = STEP_ORDER.indexOf(stepKey);
  if (si < ci) return "completed";
  if (si === ci) return "active";
  return "idle";
}

const DEFAULT_WELCOME_MESSAGE = {
  id: "welcome-1",
  sender: "ai",
  text: "Hello! I'm your AI Drive Assistant. You can select specific documents from your Google Drive catalog on the left, or simply ask a question and I'll automatically find the relevant files for you. Your documents are protected by built-in privacy and security checks.",
  time: "Just now",
  showSecurityNotice: true,
  citations: [],
  blockedFiles: [],
};

export default function ChatInterface({
  userId,
  portalEmail,
  onAskQuestion,
  onResponseDisplayed,
  onCancelQuery,
  onRecordFallbackDecision,
  isProcessing,
  currentStep,
  selectedFiles = [],
  selectedFileIds = [],
  onDeselectFile,
}) {
  const [messages, setMessages] = useState([DEFAULT_WELCOME_MESSAGE]);
  const [inputQuery, setInputQuery] = useState("");
  const [copiedId, setCopiedId] = useState(null);
  const messagesEndRef = useRef(null);

  // Sessions State
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [isSessionMenuOpen, setIsSessionMenuOpen] = useState(false);
  const sessionMenuRef = useRef(null);

  // Close session dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (sessionMenuRef.current && !sessionMenuRef.current.contains(event.target)) {
        setIsSessionMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // 1. Zero-delay Hydration from localStorage on mount
  useEffect(() => {
    if (!userId || typeof window === "undefined") return;
    try {
      const savedSessionId = localStorage.getItem(`ai_drive_active_session_${userId}`);
      if (savedSessionId) {
        setActiveSessionId(savedSessionId);
        const cached = localStorage.getItem(`ai_drive_session_msgs_${savedSessionId}`);
        if (cached) {
          const parsed = JSON.parse(cached);
          if (Array.isArray(parsed) && parsed.length > 0) {
            setMessages(parsed);
          }
        }
      }
    } catch (e) {
      console.error("[Chat] Error reading localStorage session cache:", e);
    }
  }, [userId]);

  // 2. Fetch Sessions List & sync with server
  const loadSessions = useCallback(async () => {
    if (!userId) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/rag/sessions?user_id=${userId}`);
      if (res.ok) {
        const data = await res.json();
        const sessionList = data.sessions || [];
        setSessions(sessionList);

        if (sessionList.length > 0) {
          const savedSessionId = localStorage.getItem(`ai_drive_active_session_${userId}`);
          const targetSession = sessionList.find((s) => s.id === savedSessionId) || sessionList[0];
          setActiveSessionId(targetSession.id);
          localStorage.setItem(`ai_drive_active_session_${userId}`, targetSession.id);

          // Fetch full messages from server for target session
          const msgUrl = userId
            ? `${BACKEND_URL}/api/rag/sessions/${targetSession.id}?user_id=${encodeURIComponent(userId)}`
            : `${BACKEND_URL}/api/rag/sessions/${targetSession.id}`;
          const msgRes = await fetch(msgUrl);
          if (msgRes.ok) {
            const sData = await msgRes.json();
            if (Array.isArray(sData.messages) && sData.messages.length > 0) {
              setMessages(sData.messages);
              localStorage.setItem(`ai_drive_session_msgs_${targetSession.id}`, JSON.stringify(sData.messages));
            }
          }
        } else {
          // No active sessions
          setActiveSessionId(null);
          setMessages([]);
        }
      }
    } catch (err) {
      console.error("[Chat] Failed to load sessions from server:", err);
    }
  }, [userId]);

  useEffect(() => {
    if (userId) {
      loadSessions();
    }
  }, [userId, loadSessions]);

  // 3. Auto-save messages to localStorage & sync to backend whenever messages change
  useEffect(() => {
    if (!activeSessionId || messages.length === 0 || typeof window === "undefined") return;
    try {
      localStorage.setItem(`ai_drive_session_msgs_${activeSessionId}`, JSON.stringify(messages));
    } catch (e) {
      console.error("[Chat] Failed to store messages locally:", e);
    }

    if (userId) {
      const controller = new AbortController();
      const timer = setTimeout(() => {
        fetch(`${BACKEND_URL}/api/rag/sessions/${activeSessionId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: userId,
            messages: messages,
          }),
          signal: controller.signal,
        }).catch(() => {});
      }, 600);

      return () => {
        clearTimeout(timer);
        controller.abort();
      };
    }
  }, [messages, activeSessionId, userId]);

  // Auto-scroll to bottom whenever messages change or processing state changes
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isProcessing]);

  const handleCopy = (id, text) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const reportResponseDisplayed = async (queryId, startedAt, status) => {
    await new Promise((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(resolve))
    );
    try {
      await onResponseDisplayed?.(
        queryId,
        performance.now() - startedAt,
        status
      );
    } catch (err) {
      console.error("[Chat] Failed to report response display time:", err);
    }
  };

  // Create a new session
  const createNewSession = async (title = "New Chat") => {
    if (!userId) return;
    const initialMsgs = [
      {
        ...DEFAULT_WELCOME_MESSAGE,
        id: `welcome-${Date.now()}`,
        time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      },
    ];
    try {
      const res = await fetch(`${BACKEND_URL}/api/rag/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          title: title,
          messages: initialMsgs,
        }),
      });
      if (res.ok) {
        const newSession = await res.json();
        setSessions((prev) => [newSession, ...prev]);
        setActiveSessionId(newSession.id);
        setMessages(initialMsgs);
        localStorage.setItem(`ai_drive_active_session_${userId}`, newSession.id);
        localStorage.setItem(`ai_drive_session_msgs_${newSession.id}`, JSON.stringify(initialMsgs));
        setIsSessionMenuOpen(false);
        return newSession;
      }
    } catch (err) {
      console.error("[Chat] Failed to create new session:", err);
    }
  };

  // Select an existing session
  const handleSelectSession = async (sessionId) => {
    if (sessionId === activeSessionId) {
      setIsSessionMenuOpen(false);
      return;
    }
    setActiveSessionId(sessionId);
    localStorage.setItem(`ai_drive_active_session_${userId}`, sessionId);
    setIsSessionMenuOpen(false);

    // Read cached messages immediately
    const cached = localStorage.getItem(`ai_drive_session_msgs_${sessionId}`);
    if (cached) {
      try {
        const parsed = JSON.parse(cached);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setMessages(parsed);
        }
      } catch (e) {}
    }

    // Refresh from server
    try {
      const url = userId
        ? `${BACKEND_URL}/api/rag/sessions/${sessionId}?user_id=${encodeURIComponent(userId)}`
        : `${BACKEND_URL}/api/rag/sessions/${sessionId}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.messages) && data.messages.length > 0) {
          setMessages(data.messages);
          localStorage.setItem(`ai_drive_session_msgs_${sessionId}`, JSON.stringify(data.messages));
        }
      }
    } catch (err) {
      console.error("[Chat] Failed to fetch session messages:", err);
    }
  };

  // Delete a session
  const handleDeleteSession = async (e, sessionId) => {
    e.stopPropagation();
    try {
      const url = userId
        ? `${BACKEND_URL}/api/rag/sessions/${sessionId}?user_id=${encodeURIComponent(userId)}`
        : `${BACKEND_URL}/api/rag/sessions/${sessionId}`;
      const res = await fetch(url, {
        method: "DELETE",
      });
      if (res.ok) {
        localStorage.removeItem(`ai_drive_session_msgs_${sessionId}`);
        const remaining = sessions.filter((s) => s.id !== sessionId);

        if (remaining.length > 0) {
          setSessions(remaining);
          if (activeSessionId === sessionId) {
            const nextSession = remaining[0];
            setActiveSessionId(nextSession.id);
            localStorage.setItem(`ai_drive_active_session_${userId}`, nextSession.id);
            // Fetch messages for next active session
            try {
              const nextMsgUrl = userId
                ? `${BACKEND_URL}/api/rag/sessions/${nextSession.id}?user_id=${encodeURIComponent(userId)}`
                : `${BACKEND_URL}/api/rag/sessions/${nextSession.id}`;
              const nextRes = await fetch(nextMsgUrl);
              if (nextRes.ok) {
                const nextData = await nextRes.json();
                const msgs = Array.isArray(nextData.messages) && nextData.messages.length > 0
                  ? nextData.messages
                  : [
                      {
                        ...DEFAULT_WELCOME_MESSAGE,
                        id: `welcome-${Date.now()}`,
                        time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
                      },
                    ];
                setMessages(msgs);
                localStorage.setItem(`ai_drive_session_msgs_${nextSession.id}`, JSON.stringify(msgs));
              }
            } catch (err) {
              console.error("[Chat] Failed to load next session messages:", err);
            }
          }
        } else {
          // If NO sessions remain: cleanly delete without resurrecting a new chat
          setSessions([]);
          setActiveSessionId(null);
          setMessages([]);
          localStorage.removeItem(`ai_drive_active_session_${userId}`);
        }
      }
    } catch (err) {
      console.error("[Chat] Failed to delete session:", err);
    }
  };

  // Explicit Clear Chat button
  const handleClearChat = async () => {
    const clearedMessages = [
      {
        ...DEFAULT_WELCOME_MESSAGE,
        id: `welcome-${Date.now()}`,
        time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      },
    ];
    setMessages(clearedMessages);
    if (activeSessionId) {
      localStorage.setItem(`ai_drive_session_msgs_${activeSessionId}`, JSON.stringify(clearedMessages));
      try {
        const url = userId
          ? `${BACKEND_URL}/api/rag/sessions/${activeSessionId}/clear?user_id=${encodeURIComponent(userId)}`
          : `${BACKEND_URL}/api/rag/sessions/${activeSessionId}/clear`;
        await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        });
      } catch (err) {
        console.error("[Chat] Failed to clear chat on backend:", err);
      }
    }
  };

  // Auto-name session from first query with Gemini-generated 3 to 4 word summary
  const checkAndUpdateSessionTitle = async (queryText, targetSessionId = activeSessionId) => {
    if (!targetSessionId || !userId) return;
    const currentSession = sessions.find((s) => s.id === targetSessionId);
    if (!currentSession || currentSession.title === "New Chat" || !currentSession.title || currentSession.title === "Untitled Chat") {
      try {
        const res = await fetch(`${BACKEND_URL}/api/rag/generate-title`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: queryText }),
        });
        if (res.ok) {
          const data = await res.json();
          const cleanTitle = data.title;
          if (cleanTitle) {
            setSessions((prev) =>
              prev.map((s) => (s.id === targetSessionId ? { ...s, title: cleanTitle } : s))
            );
            fetch(`${BACKEND_URL}/api/rag/sessions/${targetSessionId}`, {
              method: "PUT",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                user_id: userId,
                title: cleanTitle,
              }),
            }).catch(() => {});
          }
        }
      } catch (err) {
        console.error("[Chat] Failed to generate summarized session title:", err);
      }
    }
  };

  const handleSend = async (e) => {
    if (e) e.preventDefault();
    if (!inputQuery.trim() || isProcessing) return;

    let targetSessionId = activeSessionId;
    if (!targetSessionId) {
      const freshSession = await createNewSession("New Chat");
      if (freshSession) {
        targetSessionId = freshSession.id;
      }
    }

    const startedAt = performance.now();
    const queryId = crypto.randomUUID();
    const userText = inputQuery.trim();
    setInputQuery("");

    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    const userMsgId = `user-${Date.now()}`;
    const aiMsgId = `ai-${Date.now() + 1}`;

    setMessages((prev) => [
      ...prev,
      {
        id: userMsgId,
        sender: "user",
        text: userText,
        time: timeStr,
      },
    ]);

    checkAndUpdateSessionTitle(userText, targetSessionId);
    console.log("[Chat] Sending query:", userText);

    try {
      const response = await onAskQuestion(
        userText,
        selectedFileIds,
        false,
        [],
        false,
        queryId,
        targetSessionId
      );
      console.log("[RAG Response]", response);
      setMessages((prev) => [
        ...prev,
        {
          id: aiMsgId,
          sender: "ai",
          text: response?.answer || "No response received.",
          time: timeStr,
          citations: Array.isArray(response?.retrieved_sources) ? response.retrieved_sources : [],
          blockedFiles: Array.isArray(response?.blocked_confidential_files) ? response.blocked_confidential_files : [],
          autoDiscovered: response?.auto_discovered || false,
          candidateFiles: Array.isArray(response?.candidate_files) ? response.candidate_files.filter(Boolean) : [],
          answerSource: response?.answer_source,
          needsGeneralConfirmation: response?.needs_general_confirmation || false,
          originalQuery: userText,
          originalFileIds: [...selectedFileIds],
          matchedFileIds: response?.matched_file_ids || [],
          intent: response?.intent || "general",
        },
      ]);
      await reportResponseDisplayed(queryId, startedAt, "success");
    } catch (err) {
      if (err.name === "AbortError") {
        setMessages((prev) => [
          ...prev,
          {
            id: aiMsgId,
            sender: "ai",
            text: "Query cancelled.",
            time: timeStr,
            citations: [],
            blockedFiles: [],
            candidateFiles: [],
          },
        ]);
        await reportResponseDisplayed(queryId, startedAt, "cancelled");
        return;
      }
      console.error("[Chat] Query error:", err);
      setMessages((prev) => [
        ...prev,
        {
          id: aiMsgId,
          sender: "ai",
          text: `Error: ${err.message || "Failed to process query."}`,
          time: timeStr,
          isError: true,
          citations: [],
          blockedFiles: [],
          candidateFiles: [],
        },
      ]);
      await reportResponseDisplayed(queryId, startedAt, "error");
    }
  };

  const handleSuggestionClick = (queryText) => {
    setInputQuery(queryText);
  };

  const handleGeneralConfirmation = async (message, approved) => {
    if (!approved) {
      setMessages((prev) => [
        ...prev.map((item) =>
          item.id === message.id
            ? { ...item, needsGeneralConfirmation: false }
            : item
        ),
        {
          id: `ai-${Date.now()}`,
          sender: "ai",
          text: "Understood. Please feel free to select specific files from the left sidebar or clarify your question so I can search more effectively.",
          time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          answerSource: "assistant",
        },
      ]);
      try {
        await onRecordFallbackDecision?.(message, "declined");
      } catch (err) {
        console.error("[Chat] Failed to record fallback decision:", err);
      }
      return;
    }

    if (isProcessing) return;

    const timeStr = new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
    const startedAt = performance.now();
    const queryId = crypto.randomUUID();
    setMessages((prev) => [
      ...prev.map((item) =>
        item.id === message.id
          ? { ...item, needsGeneralConfirmation: false }
          : item
      ),
      {
        id: `user-${Date.now()}`,
        sender: "user",
        text: "Yes, please answer generally.",
        time: timeStr,
      },
    ]);

    try {
      const response = await onAskQuestion(
        message.originalQuery,
        message.originalFileIds,
        true,
        message.matchedFileIds || [],
        false,
        queryId,
        activeSessionId
      );
      setMessages((prev) => [
        ...prev,
        {
          id: `ai-${Date.now()}`,
          sender: "ai",
          text: response?.answer || "No response received.",
          time: timeStr,
          citations: Array.isArray(response?.retrieved_sources) ? response.retrieved_sources : [],
          blockedFiles: Array.isArray(response?.blocked_confidential_files) ? response.blocked_confidential_files : [],
          autoDiscovered: response?.auto_discovered || false,
          candidateFiles: Array.isArray(response?.candidate_files) ? response.candidate_files.filter(Boolean) : [],
          answerSource: response?.answer_source,
          originalQuery: message.originalQuery,
          originalFileIds: message.originalFileIds,
        },
      ]);
      await reportResponseDisplayed(queryId, startedAt, "success");
    } catch (err) {
      console.error("[Chat] General answer error:", err);
      setMessages((prev) => [
        ...prev,
        {
          id: `ai-${Date.now()}`,
          sender: "ai",
          text: `Error: ${err.message || "Failed to process query."}`,
          time: timeStr,
          isError: true,
        },
      ]);
      await reportResponseDisplayed(queryId, startedAt, "error");
    }
  };

  const handleForceDriveSearch = async (message) => {
    if (isProcessing) return;
    const startedAt = performance.now();
    const queryId = crypto.randomUUID();
    const timeStr = new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
    setMessages((prev) => [
      ...prev,
      {
        id: `user-${Date.now()}`,
        sender: "user",
        text: `Search Drive files for: "${message.originalQuery}"`,
        time: timeStr,
      },
    ]);
    try {
      const response = await onAskQuestion(
        message.originalQuery,
        message.originalFileIds || [],
        false,
        message.matchedFileIds || [],
        true,
        queryId,
        activeSessionId
      );
      setMessages((prev) => [
        ...prev,
        {
          id: `ai-${Date.now()}`,
          sender: "ai",
          text: response?.answer || "No response received.",
          time: timeStr,
          citations: Array.isArray(response?.retrieved_sources) ? response.retrieved_sources : [],
          blockedFiles: Array.isArray(response?.blocked_confidential_files) ? response.blocked_confidential_files : [],
          autoDiscovered: response?.auto_discovered || false,
          candidateFiles: Array.isArray(response?.candidate_files) ? response.candidate_files.filter(Boolean) : [],
          answerSource: response?.answer_source,
          originalQuery: message.originalQuery,
          originalFileIds: message.originalFileIds,
          fromDriveSearch: true,
        },
      ]);
      await reportResponseDisplayed(queryId, startedAt, "success");
    } catch (err) {
      console.error("[Chat] Force Drive search error:", err);
      setMessages((prev) => [
        ...prev,
        {
          id: `ai-${Date.now()}`,
          sender: "ai",
          text: `Error: ${err.message || "Failed to search Drive files."}`,
          time: timeStr,
          isError: true,
        },
      ]);
      await reportResponseDisplayed(queryId, startedAt, "error");
    }
  };

  const currentSessionTitle =
    sessions.find((s) => s.id === activeSessionId)?.title ||
    (sessions.length === 0 ? "No Active Chat" : "Active Chat");

  return (
    <div className="bg-white border border-slate-200/80 rounded-2xl shadow-xs flex flex-col h-[700px] overflow-hidden">
      {/* 0. Top Chat Sessions Navigation Bar */}
      <div className="px-6 py-2.5 border-b border-slate-100 flex items-center justify-between gap-3 bg-slate-50/60">
        <div className="relative" ref={sessionMenuRef}>
          <button
            type="button"
            onClick={() => setIsSessionMenuOpen(!isSessionMenuOpen)}
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-xl border border-slate-200/90 bg-white hover:bg-slate-50 text-xs font-semibold text-slate-800 transition-all shadow-2xs cursor-pointer"
            title="Switch chat session"
          >
            <MessageSquare size={13} className="text-blue-600 flex-shrink-0" />
            <span className="truncate max-w-[180px] sm:max-w-[240px]">
              {currentSessionTitle}
            </span>
            <ChevronDown size={13} className="text-slate-400 flex-shrink-0" />
          </button>

          {isSessionMenuOpen && (
            <div className="absolute left-0 mt-1.5 w-72 bg-white border border-slate-200 rounded-xl shadow-lg z-50 py-1.5 animate-fade-in">
              <div className="px-3 py-1.5 text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center justify-between border-b border-slate-100">
                <span>Chat Sessions ({sessions.length})</span>
                <button
                  type="button"
                  onClick={() => createNewSession("New Chat")}
                  className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-700 font-medium normal-case cursor-pointer"
                >
                  <Plus size={12} /> New
                </button>
              </div>
              <div className="max-h-60 overflow-y-auto py-1">
                {sessions.length === 0 ? (
                  <div className="px-4 py-3 text-center text-xs text-slate-400">
                    No active chat sessions.
                  </div>
                ) : (
                  sessions.map((sess) => {
                    const isActive = sess.id === activeSessionId;
                    return (
                      <div
                        key={sess.id}
                        onClick={() => handleSelectSession(sess.id)}
                        className={`px-3 py-2 flex items-center justify-between cursor-pointer transition-colors ${
                          isActive ? "bg-blue-50 text-blue-900 font-semibold" : "hover:bg-slate-50 text-slate-700"
                        }`}
                      >
                        <div className="flex items-center gap-2 min-w-0 pr-2">
                          <MessageSquare size={12} className={isActive ? "text-blue-600" : "text-slate-400"} />
                          <span className="text-xs truncate">{sess.title || "Untitled Chat"}</span>
                        </div>
                        <div className="flex items-center gap-1 flex-shrink-0">
                          {sess.message_count > 0 && (
                            <span className="text-[10px] text-slate-400 px-1 rounded bg-slate-100">
                              {sess.message_count}
                            </span>
                          )}
                          <button
                            type="button"
                            onClick={(e) => handleDeleteSession(e, sess.id)}
                            className="p-1 text-slate-400 hover:text-rose-600 rounded transition-colors"
                            title="Delete session"
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => createNewSession("New Chat")}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-200/90 bg-white hover:bg-slate-50 text-xs font-medium text-slate-700 transition-colors shadow-2xs cursor-pointer"
            title="Create a new chat session"
          >
            <Plus size={13} className="text-blue-600" />
            <span className="hidden sm:inline">New Chat</span>
          </button>

          <button
            type="button"
            onClick={handleClearChat}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-200/90 bg-white hover:bg-rose-50 hover:border-rose-200 hover:text-rose-700 text-xs font-medium text-slate-600 transition-colors shadow-2xs cursor-pointer"
            title="Clear current chat messages"
          >
            <RotateCcw size={12} />
            <span className="hidden sm:inline">Clear Chat</span>
          </button>
        </div>
      </div>

      {/* 1. Stepper Bar (matching exact design in screenshot) */}
      <div className="px-6 pt-3 pb-2">
        <div className="flex items-center gap-2 overflow-x-auto scrollbar-none py-1">
          {PIPELINE_STEPS.map((step, idx) => {
            const state = getStepState(step.key, currentStep);
            const isFirst = idx === 0 && !currentStep; // Highlight first step as idle default
            const isActive = state === "active" || (isFirst && !currentStep);
            const isCompleted = state === "completed";

            return (
              <div key={step.key} className="flex items-center gap-2 flex-shrink-0">
                <div
                  className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium transition-all ${
                    isActive
                      ? "bg-blue-50/80 border border-blue-200 text-blue-700 font-semibold shadow-2xs"
                      : isCompleted
                      ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                      : "text-slate-400"
                  }`}
                >
                  <span
                    className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold ${
                      isActive
                        ? "bg-blue-600 text-white"
                        : isCompleted
                        ? "bg-emerald-600 text-white"
                        : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {isCompleted ? "✓" : step.stepNum}
                  </span>
                  <span>{step.label}</span>
                </div>

                {idx < PIPELINE_STEPS.length - 1 && (
                  <ChevronRight size={13} className="text-slate-300 flex-shrink-0" />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* 2. Target Files / Auto-Discovery Banner (matching lavender banner in screenshot) */}
      <div className="px-6 pt-1">
        {selectedFiles.length > 0 ? (
          <div className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-blue-50/70 border border-blue-200/70 text-xs text-blue-950 overflow-x-auto scrollbar-none">
            <span className="flex items-center gap-1 font-semibold text-blue-700 flex-shrink-0">
              <FileCheck2 size={14} />
              Query Target ({selectedFiles.length}):
            </span>
            <div className="flex items-center gap-1.5 flex-wrap">
              {selectedFiles.map((sf) => (
                <span
                  key={sf.id}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-white text-slate-700 text-[11px] font-medium border border-blue-200/60 shadow-2xs"
                  title={sf.name}
                >
                  <span className="truncate max-w-[140px]">{sf.name}</span>
                  {onDeselectFile && (
                    <button
                      type="button"
                      onClick={() => onDeselectFile(sf.id)}
                      className="text-slate-400 hover:text-rose-500 transition-colors ml-0.5"
                    >
                      <X size={11} />
                    </button>
                  )}
                </span>
              ))}
            </div>
          </div>
        ) : (
          <div className="bg-purple-50/70 border border-purple-200/60 rounded-xl px-4 py-2.5 flex items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2 min-w-0">
              <Search size={14} className="text-purple-600 flex-shrink-0" />
              <span className="truncate text-slate-700">
                <strong className="text-purple-900 font-semibold">Smart Query Routing:</strong>{" "}
                Drive-related questions search relevant documents; general questions are answered directly.
              </span>
            </div>
            <span className="bg-purple-100 text-purple-700 font-semibold text-[10px] px-2.5 py-0.5 rounded-full flex-shrink-0">
              Smart Index Mode
            </span>
          </div>
        )}
      </div>

      {/* 3. Messages Stream */}
      <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-5 scrollbar-thin scrollbar-thumb-slate-200">
        {!activeSessionId || sessions.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center py-20 px-4 text-center my-auto animate-fade-in">
            <div className="w-16 h-16 rounded-3xl bg-blue-50 border border-blue-200/80 flex items-center justify-center text-blue-600 mb-4 shadow-sm shadow-blue-500/10">
              <MessageSquare size={32} />
            </div>
            <h3 className="font-heading text-lg font-bold text-slate-800 mb-1.5">
              No Active Chat Session
            </h3>
            <p className="text-xs text-slate-500 max-w-sm mb-6 leading-relaxed">
              Start a new conversation to ask questions about your documents, analyze spreadsheets, or chat with AI Drive Assistant.
            </p>
            <button
              type="button"
              onClick={() => createNewSession("New Chat")}
              className="inline-flex items-center gap-2 px-6 py-3 rounded-2xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold shadow-lg shadow-blue-500/25 active:scale-95 transition-all cursor-pointer"
            >
              <Plus size={16} />
              <span>Start Chat</span>
            </button>
          </div>
        ) : (
          messages.map((msg) => {
          const isUser = msg.sender === "user";

          if (isUser) {
            return (
              <div key={msg.id} className="flex flex-col items-end gap-1 self-end max-w-[80%] animate-slide-up">
                {/* User Header */}
                <div className="flex items-center gap-1.5 text-[11px] text-slate-400 pr-1">
                  <span>{msg.time || "12:34 PM"}</span>
                  <span className="font-medium text-slate-600">You</span>
                  <span className="w-5 h-5 rounded-full bg-blue-100 text-blue-700 text-[10px] font-bold flex items-center justify-center">
                    U
                  </span>
                </div>

                {/* User Bubble (matching royal blue bubble in screenshot) */}
                <div className="bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 text-xs shadow-sm leading-relaxed">
                  {msg.text}
                </div>
              </div>
            );
          }

          // Assistant message
          return (
            <div key={msg.id} className="flex items-start gap-3 self-start max-w-[85%] animate-slide-up">
              {/* AI Avatar */}
              <div className="w-7 h-7 rounded-full bg-indigo-600 text-white flex items-center justify-center flex-shrink-0 shadow-xs mt-0.5">
                <Sparkles size={14} />
              </div>

              {/* Message Container */}
              <div className="flex flex-col gap-1 min-w-0">
                {/* Assistant Header */}
                <div className="flex items-center gap-1.5 text-[11px]">
                  <span className="font-bold text-slate-800">AI Drive Assistant</span>
                  <span className="text-slate-400 text-[10px]">{msg.time || "Just now"}</span>
                </div>

                {/* Bubble (clean white card with subtle border) */}
                <div className="bg-white border border-slate-200/80 rounded-2xl rounded-tl-sm p-4 text-xs text-slate-700 leading-relaxed shadow-xs">
                  {/* Auto-discovered source files banner */}
                  {msg.autoDiscovered && msg.candidateFiles?.length > 0 && (
                    <div className="mb-2.5 flex items-center gap-2 px-3 py-1.5 rounded-lg bg-blue-50/70 border border-blue-200/60 text-xs text-blue-900">
                      <Search size={13} className="text-blue-600 flex-shrink-0" />
                      <span>
                        <strong>Identified Document(s):</strong> {msg.candidateFiles.join(", ")}
                      </span>
                    </div>
                  )}

                  {msg.answerSource && (
                    <span className="mb-1 inline-flex w-fit rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                      {msg.answerSource === "google_drive"
                        ? "Based on Google Drive documents"
                        : msg.answerSource === "general_knowledge"
                          ? "General knowledge — not from your documents"
                          : msg.answerSource === "insufficient_drive_evidence"
                            ? "No sufficient document evidence"
                            : "Assistant information"}
                    </span>
                  )}
                  <MarkdownRenderer content={msg.text} />

                  {msg.answerSource === "general_knowledge" && !msg.fromDriveSearch && msg.originalQuery && (
                    <div className="mt-2.5 pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
                      <span>Answered from general knowledge.</span>
                      <button
                        type="button"
                        disabled={isProcessing}
                        onClick={() => handleForceDriveSearch(msg)}
                        className="inline-flex items-center gap-1 font-semibold text-blue-600 hover:text-blue-800 hover:underline cursor-pointer"
                      >
                        <Search size={11} />
                        Search Drive documents instead
                      </button>
                    </div>
                  )}

                  {msg.needsGeneralConfirmation && (
                    <div className="mt-3 flex gap-2">
                      <button
                        type="button"
                        disabled={isProcessing}
                        onClick={() => handleGeneralConfirmation(msg, true)}
                        className="rounded-lg bg-blue-600 px-3 py-1.5 text-[11px] font-semibold text-white hover:bg-blue-700 disabled:opacity-50 cursor-pointer"
                      >
                        Yes, answer generally
                      </button>
                      <button
                        type="button"
                        disabled={isProcessing}
                        onClick={() => handleGeneralConfirmation(msg, false)}
                        className="rounded-lg border border-slate-200 px-3 py-1.5 text-[11px] font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-50 cursor-pointer"
                      >
                        No, clarify query
                      </button>
                    </div>
                  )}

                  {/* Confidential Notice */}
                  {msg.blockedFiles?.length > 0 && (
                    <div className="mt-3 bg-rose-50 border-l-4 border-rose-500 rounded-lg px-3.5 py-2.5">
                      <div className="flex items-center gap-1.5 font-semibold text-xs text-rose-800 mb-1">
                        <AlertTriangle size={13} className="text-rose-600" />
                        Privacy Notice — Sensitive Information Protected
                      </div>
                      {msg.blockedFiles.map((b, bi) => (
                        <p key={bi} className="text-[11px] text-rose-700 mt-0.5">
                          • <strong>{b.name}</strong>: {b.reason}
                        </p>
                      ))}
                    </div>
                  )}

                  {/* Citations */}
                  {msg.citations?.length > 0 && (
                    <div className="mt-3 pt-2.5 border-t border-slate-100">
                      <span className="text-[10px] font-semibold text-slate-400 block mb-1 uppercase tracking-wider">
                        Referenced Sources:
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {msg.citations.map((c, ci) => (
                          <span
                            key={ci}
                            className="inline-flex items-center gap-1 bg-slate-50 border border-slate-200 text-slate-700 px-2 py-0.5 rounded-md text-[11px] font-mono"
                          >
                            <FileText size={11} className="text-blue-500" />
                            {c?.file_name} ({Math.round((c?.similarity ?? 0) * 100)}% match)
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Bottom Bar: Security Notice & Action Icons (matching screenshot) */}
                  <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center justify-between gap-3 text-[11px] text-slate-400">
                    <div className="flex items-center gap-1.5 text-emerald-700 font-medium text-[11px]">
                      <ShieldCheck size={13} className="text-emerald-600 flex-shrink-0" />
                      <span>Protected by built-in privacy and security checks</span>
                    </div>

                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => handleCopy(msg.id, msg.text)}
                        className="p-1 rounded hover:bg-slate-100 hover:text-slate-600 transition-colors cursor-pointer"
                        title="Copy answer"
                      >
                        {copiedId === msg.id ? (
                          <Check size={12} className="text-emerald-600" />
                        ) : (
                          <Copy size={12} />
                        )}
                      </button>
                      <button
                        type="button"
                        className="p-1 rounded hover:bg-slate-100 hover:text-slate-600 transition-colors cursor-pointer"
                        title="Helpful"
                      >
                        <ThumbsUp size={12} />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          );
        })
      )}

        {/* Processing Spinner Indicator */}
        {isProcessing && (
          <div className="flex items-start gap-3 self-start animate-fade-in">
            <div className="w-7 h-7 rounded-full bg-indigo-600 text-white flex items-center justify-center flex-shrink-0 shadow-xs">
              <Sparkles size={14} className="animate-spin" />
            </div>
            <div className="bg-white border border-slate-200/80 rounded-2xl rounded-tl-sm px-4 py-2.5 text-xs text-slate-500 shadow-xs flex items-center gap-2">
              <div className="w-3.5 h-3.5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
              <span>Checking files and preparing your answer...</span>
              <button
                type="button"
                onClick={onCancelQuery}
                className="ml-2 inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-medium text-rose-600 hover:bg-rose-50 cursor-pointer"
                title="Cancel the current query"
              >
                <Square size={10} fill="currentColor" />
                Cancel
              </button>
            </div>
            <p className="mt-1 ml-5 text-[10px] leading-relaxed text-slate-400">
              First-time checks and indexing can take longer. Safe files are indexed to speed up follow-up questions.
            </p>
          </div>
        )}

        {/* Clear Chat Button at the end of each chat */}
        {messages.length > 1 && (
          <div className="flex justify-center my-3 animate-fade-in">
            <button
              type="button"
              onClick={handleClearChat}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-medium text-slate-500 bg-slate-100 hover:bg-slate-200 hover:text-rose-600 border border-slate-200/80 transition-all shadow-2xs cursor-pointer"
              title="Clear all messages in this chat session"
            >
              <RotateCcw size={12} />
              <span>Clear Chat</span>
            </button>
          </div>
        )}

        {/* Auto-scroll anchor */}
        <div ref={messagesEndRef} />
      </div>

      {/* 4. Bottom Input Bar & Suggestion Pills (matching screenshot) */}
      <div className="px-6 py-4 border-t border-slate-100 bg-white">
        <form onSubmit={handleSend} className="relative flex items-center">
          <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            className="w-full bg-slate-50/80 border border-slate-200/90 rounded-2xl pl-9 pr-24 py-2.5 text-xs text-slate-800 placeholder-slate-400 outline-none transition-all focus:border-blue-500 focus:bg-white focus:ring-2 focus:ring-blue-100 font-sans"
            placeholder={
              selectedFiles.length > 0
                ? `Ask anything about ${selectedFiles.length === 1 ? selectedFiles[0].name : `${selectedFiles.length} selected files`}...`
                : "Ask a question — I'll answer generally or search relevant Drive files..."
            }
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            disabled={isProcessing}
          />

          <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1.5">
            <span className="text-[10px] text-slate-400 bg-white border border-slate-200 px-1.5 py-0.5 rounded font-mono shadow-2xs">
              Enter ↵
            </span>
            <button
              type="submit"
              disabled={isProcessing || !inputQuery.trim()}
              className="w-8 h-8 rounded-xl bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white flex items-center justify-center transition-all shadow-sm shadow-blue-500/20 disabled:opacity-40 disabled:shadow-none cursor-pointer"
              title="Submit query"
            >
              <Send size={13} className="ml-0.5" />
            </button>
          </div>
        </form>

        {/* Suggestion Pills below input matching screenshot */}
        <div className="flex items-center gap-1.5 mt-2.5 overflow-x-auto scrollbar-none text-xs">
          <span className="text-[11px] text-slate-400 font-medium mr-0.5 flex-shrink-0">
            Try asking:
          </span>
          {[
            "Summarize my documents",
            "Find important agreements",
            "Analyze my files",
          ].map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => handleSuggestionClick(suggestion)}
              className="text-[11px] text-slate-600 bg-white border border-slate-200/80 hover:border-slate-300 hover:bg-slate-50 px-2.5 py-0.5 rounded-full shadow-2xs transition-colors flex-shrink-0 cursor-pointer"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
