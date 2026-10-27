"use client";

import { useState, useRef, useEffect } from "react";
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
  FileCheck2
} from "lucide-react";

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

export default function ChatInterface({
  onAskQuestion,
  onCancelQuery,
  isProcessing,
  currentStep,
  selectedFiles = [],
  selectedFileIds = [],
  onDeselectFile,
}) {
  const [messages, setMessages] = useState([
    {
      id: "welcome-1",
      sender: "ai",
      text: "Hello! I'm your AI Drive Assistant. You can select specific documents from your Google Drive catalog on the left, or simply ask a question and I'll automatically find the relevant files for you. Your documents are protected by built-in privacy and security checks.",
      time: "Just now",
      showSecurityNotice: true,
      citations: [],
      blockedFiles: [],
    },
  ]);
  const [inputQuery, setInputQuery] = useState("");
  const [copiedId, setCopiedId] = useState(null);
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom whenever messages change or processing state changes
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isProcessing]);

  const handleCopy = (id, text) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleSend = async (e) => {
    if (e) e.preventDefault();
    if (!inputQuery.trim() || isProcessing) return;

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

    console.log("[Chat] Sending query:", userText);

    try {
      const response = await onAskQuestion(userText, selectedFileIds);
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
          needsGeneralConfirmation: response?.needs_general_confirmation || false,
          originalQuery: userText,
          originalFileIds: [...selectedFileIds],
        },
      ]);
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
    }
  };

  const handleSuggestionClick = (queryText) => {
    setInputQuery(queryText);
  };

  const handleGeneralConfirmation = async (message, approved) => {
    if (!approved) {
      setMessages((prev) =>
        prev.map((item) =>
          item.id === message.id
            ? { ...item, needsGeneralConfirmation: false }
            : item
        )
      );
      return;
    }

    if (isProcessing) return;

    const timeStr = new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
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
        true
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
        },
      ]);
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
    }
  };

  return (
    <div className="bg-white border border-slate-200/80 rounded-2xl shadow-xs flex flex-col h-[700px] overflow-hidden">
      {/* 1. Stepper Bar (matching exact design in screenshot) */}
      <div className="px-6 pt-5 pb-2">
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
        {messages.map((msg) => {
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

                  <p className="whitespace-pre-wrap">{msg.text}</p>

                  {msg.needsGeneralConfirmation && (
                    <div className="mt-3 flex gap-2">
                      <button
                        type="button"
                        disabled={isProcessing}
                        onClick={() => handleGeneralConfirmation(msg, true)}
                        className="rounded-lg bg-blue-600 px-3 py-1.5 text-[11px] font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                      >
                        Yes, answer generally
                      </button>
                      <button
                        type="button"
                        disabled={isProcessing}
                        onClick={() => handleGeneralConfirmation(msg, false)}
                        className="rounded-lg border border-slate-200 px-3 py-1.5 text-[11px] font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                      >
                        No, thanks
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
                        className="p-1 rounded hover:bg-slate-100 hover:text-slate-600 transition-colors"
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
                        className="p-1 rounded hover:bg-slate-100 hover:text-slate-600 transition-colors"
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
        })}

        {/* Processing Spinner Indicator */}
        {isProcessing && (
          <div className="flex items-start gap-3 self-start animate-fade-in">
            <div className="w-7 h-7 rounded-full bg-indigo-600 text-white flex items-center justify-center flex-shrink-0 shadow-xs">
              <Sparkles size={14} className="animate-spin" />
            </div>
            <div className="bg-white border border-slate-200/80 rounded-2xl rounded-tl-sm px-4 py-2.5 text-xs text-slate-500 shadow-xs flex items-center gap-2">
              <div className="w-3.5 h-3.5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
              <span>Processing your question...</span>
              <button
                type="button"
                onClick={onCancelQuery}
                className="ml-2 inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-medium text-rose-600 hover:bg-rose-50"
                title="Cancel the current query"
              >
                <Square size={10} fill="currentColor" />
                Cancel
              </button>
            </div>
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
              className="text-[11px] text-slate-600 bg-white border border-slate-200/80 hover:border-slate-300 hover:bg-slate-50 px-2.5 py-0.5 rounded-full shadow-2xs transition-colors flex-shrink-0"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
