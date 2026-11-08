"use client";

import { useState } from "react";
import Link from "next/link";
import {
  HardDrive,
  ArrowRight,
  ShieldCheck,
  Zap,
  Sparkles,
  Database,
  Lock,
  FileText,
  FileSpreadsheet,
  CheckCircle2,
  Activity,
  FolderOpen,
  Terminal,
  Cpu,
  Layers,
  KeyRound,
  ShieldAlert,
  ExternalLink,
  X
} from "lucide-react";

export default function LandingPage({ onContinue }) {
  const [activePolicyModal, setActivePolicyModal] = useState(null); // "privacy" | "security" | "terms" | null

  // Option B: High-Contrast Infinite Diagonal Conveyor Stream
  // Rich mixture of clean UI cards and dark-slate tech cards for enhanced depth and contrast

  const driveColumnCards = (
    <>
      {/* 1. Drive Catalog Explorer (Light UI Card) */}
      <div className="p-4 rounded-2xl bg-white/95 border border-slate-300 shadow-md backdrop-blur-md space-y-2.5">
        <div className="flex items-center justify-between border-b border-slate-100 pb-2">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
              <FolderOpen size={15} className="text-amber-500" />
            </div>
            <span className="text-[11px] font-bold text-slate-900">Drive Catalog Explorer</span>
          </div>
          <span className="text-[9px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-300 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            LIVE SYNC
          </span>
        </div>
        <div className="space-y-1.5 text-[10px]">
          <div className="flex items-center justify-between p-2 rounded-xl bg-slate-50 border border-slate-200">
            <div className="flex items-center gap-2 truncate">
              <FileText size={13} className="text-rose-500 flex-shrink-0" />
              <span className="font-semibold text-slate-800 truncate">AI Developer Roadmap.pdf</span>
            </div>
            <span className="text-[9px] text-slate-500 font-mono">1.2 MB</span>
          </div>
          <div className="flex items-center justify-between p-2 rounded-xl bg-slate-50 border border-slate-200">
            <div className="flex items-center gap-2 truncate">
              <FileSpreadsheet size={13} className="text-emerald-600 flex-shrink-0" />
              <span className="font-semibold text-slate-800 truncate">Q3_Budget_Audit.xlsx</span>
            </div>
            <span className="text-[9px] text-slate-500 font-mono">45 KB</span>
          </div>
        </div>
        <div className="text-[9px] text-slate-600 font-medium flex items-center justify-between pt-1">
          <span className="text-blue-700 font-bold">100+ Documents Indexed</span>
          <span className="text-emerald-700 font-semibold">✓ OAuth Verified</span>
        </div>
      </div>

      {/* 2. Vector Chunking Pipeline (Dark Tech Card) */}
      <div className="p-4 rounded-2xl bg-slate-900/95 border border-slate-700/80 shadow-lg text-slate-200 space-y-2">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-lg bg-indigo-500/20 text-indigo-400 flex items-center justify-center">
              <Terminal size={13} />
            </div>
            <span className="text-[11px] font-bold text-white">Embeddings & Vector Chunking</span>
          </div>
          <span className="text-[9px] font-mono text-indigo-400 bg-indigo-950/80 px-2 py-0.5 rounded border border-indigo-800/80">
            text-embedding-004
          </span>
        </div>
        <div className="p-2 rounded-lg bg-slate-950 border border-slate-800 font-mono text-[9px] text-slate-300 space-y-1">
          <div className="text-emerald-400 flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <span>Recursive Splitter: 1000 chunk / 150 overlap</span>
          </div>
          <div className="text-slate-400">Dim: 768 | Stored in PostgreSQL (pgvector)</div>
          <div className="text-sky-300">Top-k Semantic Matching: cosine 0.941</div>
        </div>
      </div>

      {/* 3. Folder Tree Catalog (Light UI Card) */}
      <div className="p-4 rounded-2xl bg-white/95 border border-slate-300 shadow-md backdrop-blur-md space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-bold text-slate-900 flex items-center gap-1.5">
            <HardDrive size={13} className="text-blue-600" />
            Folder Hierarchy Explorer
          </span>
          <span className="text-[9px] font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
            All Files Tab
          </span>
        </div>
        <div className="p-2 rounded-xl bg-slate-50 border border-slate-200 text-[10px] text-slate-700 space-y-1.5">
          <div className="flex items-center gap-1.5">
            <FolderOpen size={12} className="text-amber-500" />
            <span className="font-bold text-slate-800">/Engineering/Roadmaps/</span>
          </div>
          <div className="flex items-center justify-between pl-4 text-[9px] text-slate-600">
            <span>• Full_Stack_Roadmap.pdf</span>
            <span className="font-semibold text-emerald-600">Indexed</span>
          </div>
          <div className="flex items-center justify-between pl-4 text-[9px] text-slate-600">
            <span>• Backend_API_Architecture.docx</span>
            <span className="font-semibold text-emerald-600">Indexed</span>
          </div>
        </div>
      </div>

      {/* 4. Drive Webhook Pulse (Dark Tech Card) */}
      <div className="p-3.5 rounded-2xl bg-slate-900/95 border border-slate-700/80 shadow-lg text-slate-200 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-bold text-emerald-400 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
            Drive Webhook Active
          </span>
          <span className="text-[9px] font-mono text-slate-400">Live Ingest</span>
        </div>
        <p className="text-[9px] text-slate-300 font-mono leading-relaxed">
          &gt; Change detected on Google Drive root.<br />
          &gt; Ingesting spreadsheet chunks... <span className="text-emerald-400 font-bold">[DONE]</span>
        </p>
      </div>

      {/* 5. Document Type Parser (Light UI Card) */}
      <div className="p-3.5 rounded-2xl bg-white/95 border border-slate-300 shadow-md backdrop-blur-md space-y-1.5">
        <div className="flex items-center justify-between text-[10px] font-bold text-slate-800">
          <span className="flex items-center gap-1.5">
            <Layers size={13} className="text-indigo-600" />
            Multi-Modal Parser
          </span>
          <span className="text-[8px] bg-indigo-50 text-indigo-700 px-1.5 py-0.5 rounded font-bold">
            PDF + XLSX + DOCX
          </span>
        </div>
        <p className="text-[9px] text-slate-600 leading-snug">
          Preserves table columns, sheet formulas, headers, and code blocks for pinpoint citation extraction.
        </p>
      </div>
    </>
  );

  const privacyColumnCards = (
    <>
      {/* 1. Real-Time PII Redaction Filter (Light UI Card) */}
      <div className="p-4 rounded-2xl bg-white/95 border border-slate-300 shadow-md backdrop-blur-md space-y-2.5">
        <div className="flex items-center justify-between border-b border-slate-100 pb-2">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <ShieldCheck size={15} />
            </div>
            <span className="text-[11px] font-bold text-slate-900">Zero-Knowledge Guardrails</span>
          </div>
          <span className="text-[9px] font-bold text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded-full border border-emerald-300 font-mono">
            PASSED
          </span>
        </div>
        <div className="p-2.5 rounded-xl bg-emerald-50/80 border border-emerald-300 text-[10px] text-emerald-950 space-y-1.5 relative overflow-hidden">
          <div className="absolute inset-x-0 h-0.5 bg-emerald-500 animate-scan" />
          <div className="text-[9px] font-bold text-slate-700">Document Chunk Inspection:</div>
          <div className="p-2 rounded-lg bg-white/95 border border-emerald-200 font-mono text-[9px] text-slate-800 space-y-0.5 shadow-2xs">
            <div>CNIC: 35201-XXXXXXX-X <span className="text-rose-600 font-bold">[WITHHELD]</span></div>
            <div>PSID: 1000000000 <span className="text-rose-600 font-bold">[WITHHELD]</span></div>
            <div>PHONE: +92-300-XXXXXXX <span className="text-rose-600 font-bold">[REDACTED]</span></div>
          </div>
        </div>
        <div className="text-[9px] text-emerald-800 font-bold flex items-center gap-1">
          <CheckCircle2 size={12} className="text-emerald-600" />
          <span>Zero PII sent to LLM synthesis engine</span>
        </div>
      </div>

      {/* 2. Security Gateway Log (Dark Tech Card) */}
      <div className="p-4 rounded-2xl bg-slate-900/95 border border-slate-700/80 shadow-lg text-slate-200 space-y-2">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-lg bg-rose-500/20 text-rose-400 flex items-center justify-center">
              <ShieldAlert size={13} />
            </div>
            <span className="text-[11px] font-bold text-white">Privacy Interceptor Log</span>
          </div>
          <span className="text-[9px] font-mono text-emerald-400 bg-emerald-950/80 px-2 py-0.5 rounded border border-emerald-800/80">
            SANITIZED
          </span>
        </div>
        <div className="p-2 rounded-lg bg-slate-950 border border-slate-800 font-mono text-[9px] text-slate-300 space-y-1">
          <div className="text-rose-400">&gt; Pattern Detected: Pakistan CNIC (13 digits)</div>
          <div className="text-slate-400">&gt; Action: Masked with [WITHHELD] token</div>
          <div className="text-emerald-400">&gt; Verification: Passed to RAG Pipeline safe</div>
        </div>
      </div>

      {/* 3. No Query Logging Guarantee (Light UI Card) */}
      <div className="p-4 rounded-2xl bg-white/95 border border-slate-300 shadow-md backdrop-blur-md space-y-2">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <Lock size={13} />
          </div>
          <span className="text-[11px] font-bold text-slate-900">Zero Query Text Logging</span>
        </div>
        <p className="text-[10px] text-slate-600 leading-relaxed font-normal">
          Neither the database nor the telemetry consoles ever record user query text or LLM answers.
        </p>
        <div className="p-1.5 rounded-lg bg-slate-50 border border-slate-200 text-[8px] font-mono text-slate-600">
          QueryTelemetry: (id, user_id, tokens, latency, cost)
        </div>
      </div>

      {/* 4. Cryptographic Role Gateway (Dark Tech Card) */}
      <div className="p-3.5 rounded-2xl bg-slate-900/95 border border-slate-700/80 shadow-lg text-slate-200 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-bold text-purple-400 flex items-center gap-1.5">
            <KeyRound size={12} />
            Role-Based Access Control
          </span>
          <span className="text-[9px] font-mono text-slate-400">JWT SHA-256</span>
        </div>
        <div className="text-[9px] font-mono text-slate-300 space-y-0.5">
          <div>• Lead Admin: Token assignment & master telemetry</div>
          <div>• User Admin: Real-time user audits & token counters</div>
        </div>
      </div>

      {/* 5. Data Privacy Seal (Light UI Card) */}
      <div className="p-3.5 rounded-2xl bg-white/95 border border-slate-300 shadow-md backdrop-blur-md flex items-center gap-3">
        <div className="w-8 h-8 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center flex-shrink-0">
          <ShieldCheck size={18} />
        </div>
        <div>
          <div className="text-[10px] font-bold text-slate-900">Enterprise SOC2 Ready</div>
          <div className="text-[8px] text-slate-500">Zero data retention for training models</div>
        </div>
      </div>
    </>
  );

  const aiColumnCards = (
    <>
      {/* 1. Dual-Mode AI Synthesis (Light UI Card) */}
      <div className="p-4 rounded-2xl bg-white/95 border border-slate-300 shadow-md backdrop-blur-md space-y-2.5">
        <div className="flex items-center justify-between border-b border-slate-100 pb-2">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
              <Zap size={14} />
            </div>
            <span className="text-[11px] font-bold text-slate-900">Dual-Mode AI Synthesis</span>
          </div>
          <span className="text-[9px] font-bold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded-full border border-indigo-200 font-mono">
            RAG ROUTER
          </span>
        </div>
        <div className="space-y-2 text-[10px]">
          <div className="p-2 rounded-xl bg-blue-600 text-white text-[10px] self-end ml-4 shadow-xs font-medium">
            &ldquo;Give me the Full Stack Roadmap.&rdquo;
          </div>
          <div className="p-2 rounded-xl bg-slate-50 border border-slate-200 text-[10px] text-slate-700 space-y-1">
            <div className="text-[9px] font-bold text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 inline-block">
              Title: Full Stack Roadmap (3 words)
            </div>
            <p className="text-slate-600 leading-snug">
              Phase 1: Frontend Basics • Phase 2: Backend APIs • Phase 3: Cloud & DevOps.
            </p>
            <div className="text-[8px] text-slate-500 flex items-center gap-1 font-semibold">
              📎 Citation: <span className="text-blue-600">AI Developer Roadmap.pdf</span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Telemetry & Quota Governance (Dark Tech Card) */}
      <div className="p-4 rounded-2xl bg-slate-900/95 border border-slate-700/80 shadow-lg text-slate-200 space-y-2.5">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-lg bg-purple-500/20 text-purple-400 flex items-center justify-center">
              <Activity size={13} />
            </div>
            <span className="text-[11px] font-bold text-white">Live Telemetry & Budgeting</span>
          </div>
          <span className="text-[9px] font-mono text-purple-300 bg-purple-950/80 px-2 py-0.5 rounded border border-purple-800/80">
            142ms AVG
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2 text-center">
          <div className="p-2 rounded-xl bg-slate-950 border border-slate-800">
            <div className="text-[14px] font-extrabold text-white">160,000</div>
            <div className="text-[8px] text-slate-400 uppercase font-semibold">Assigned Quota</div>
          </div>
          <div className="p-2 rounded-xl bg-slate-950 border border-slate-800">
            <div className="text-[14px] font-extrabold text-emerald-400">$0.0004</div>
            <div className="text-[8px] text-slate-400 uppercase font-semibold">Estimated Cost</div>
          </div>
        </div>
        <div className="p-1.5 rounded-lg bg-emerald-950/60 border border-emerald-800/70 text-[8px] text-emerald-300 flex items-center gap-1 font-mono">
          <CheckCircle2 size={11} className="text-emerald-400 flex-shrink-0" />
          <span>Tokens are permanent & never reversed upon chat clear</span>
        </div>
      </div>

      {/* 3. Disconnected Drive Fallback (Light UI Card) */}
      <div className="p-4 rounded-2xl bg-white/95 border border-slate-300 shadow-md backdrop-blur-md space-y-2">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-sky-50 text-sky-600 flex items-center justify-center">
            <Sparkles size={13} />
          </div>
          <span className="text-[11px] font-bold text-slate-900">Zero-Dependency Guidance</span>
        </div>
        <p className="text-[10px] text-slate-600 leading-relaxed font-normal">
          Answers programming and general domain queries instantly via Gemini 2.5 Flash, even before Google Drive is connected.
        </p>
      </div>

      {/* 4. Live Token Speedometer (Dark Tech Card) */}
      <div className="p-3.5 rounded-2xl bg-slate-900/95 border border-slate-700/80 shadow-lg text-slate-200 space-y-1.5 font-mono text-[9px]">
        <div className="flex items-center justify-between text-slate-400">
          <span>[Token Engine]</span>
          <span className="text-emerald-400">STATUS: HEALTHY</span>
        </div>
        <div className="text-slate-300">Prompt: 28 tokens | Completion: 142 tokens</div>
        <div className="w-full bg-slate-800 h-1 rounded-full overflow-hidden">
          <div className="bg-gradient-to-r from-blue-500 to-indigo-500 h-full w-[35%]" />
        </div>
      </div>

      {/* 5. Smart Chat Titling (Light UI Card) */}
      <div className="p-3.5 rounded-2xl bg-white/95 border border-slate-300 shadow-md backdrop-blur-md space-y-1">
        <span className="text-[10px] font-bold text-slate-900 flex items-center gap-1.5">
          <Cpu size={12} className="text-blue-600" />
          3–4 Word Session Titling
        </span>
        <p className="text-[9px] text-slate-600">
          User questions are summarized into clean session titles (&ldquo;Full Stack Roadmap&rdquo;) without cluttering the chat history.
        </p>
      </div>
    </>
  );

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-100 via-white to-blue-50/60 text-slate-900 flex flex-col justify-between relative overflow-hidden select-none font-sans">

      {/* ──────────────── 1. OPTION B: HIGH-CONTRAST DIAGONAL CONVEYOR STREAM ──────────────── */}
      <div className="absolute inset-[-25%] w-[150%] h-[150%] pointer-events-none overflow-hidden select-none z-0 transform -rotate-[7deg]">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 sm:gap-8 w-full h-full opacity-[0.62] [mask-image:linear-gradient(to_bottom,transparent,black_12%,black_88%,transparent)]">

          {/* Column 1: Drive Ingestion Stream (Drifting Upward) */}
          <div className="hidden lg:flex flex-col gap-5 animate-marquee-up">
            {driveColumnCards}
            {driveColumnCards}
          </div>

          {/* Column 2: Zero-Knowledge Privacy Stream (Drifting Downward) */}
          <div className="flex flex-col gap-5 animate-marquee-down">
            {privacyColumnCards}
            {privacyColumnCards}
          </div>

          {/* Column 3: AI Synthesis & Telemetry Stream (Drifting Upward Fast) */}
          <div className="hidden md:flex flex-col gap-5 animate-marquee-up-fast">
            {aiColumnCards}
            {aiColumnCards}
          </div>

        </div>
      </div>

      {/* High-Definition Contrast Vignette over Center (keeps hero text 100% sharp while letting background depth shine) */}
      <div
        className="absolute inset-0 pointer-events-none z-1"
        style={{
          background: "radial-gradient(ellipse 65% 60% at 50% 48%, rgba(255, 255, 255, 0.88) 0%, rgba(255, 255, 255, 0.72) 42%, rgba(248, 250, 252, 0.32) 75%, rgba(226, 232, 240, 0.55) 100%)"
        }}
      />

      {/* Deeper Ambient Radial Accent Glows */}
      <div className="absolute top-[-8%] left-[-8%] w-[550px] h-[550px] rounded-full bg-blue-500/15 blur-[140px] pointer-events-none z-1" />
      <div className="absolute bottom-[-8%] right-[-8%] w-[600px] h-[600px] rounded-full bg-indigo-500/15 blur-[150px] pointer-events-none z-1" />
      <div className="absolute top-[35%] right-[10%] w-[450px] h-[450px] rounded-full bg-purple-500/10 blur-[130px] pointer-events-none z-1" />

      {/* ──────────────── 2. TOP HEADER ──────────────── */}
      <header className="relative z-10 max-w-7xl mx-auto w-full px-6 py-5 flex items-center justify-between border-b border-slate-200/80 bg-white/80 backdrop-blur-md shadow-xs">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-md shadow-blue-500/20 flex-shrink-0">
            <HardDrive size={22} className="stroke-[2.2]" />
          </div>
          <div>
            <span className="font-heading text-lg font-bold tracking-tight text-slate-900 block">
              AI Drive Assistant
            </span>
            <span className="text-[10px] text-slate-500 font-medium tracking-wider uppercase block">
              Document Intelligence & Co-Pilot
            </span>
          </div>
        </div>

        {/* Top-Right: Enterprise Privacy Badge Only (Open Portal button removed) */}
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-300 shadow-2xs">
            <ShieldCheck size={13} className="text-emerald-600" />
            Enterprise Privacy
          </span>
        </div>
      </header>

      {/* ──────────────── 3. HERO CONTENT SECTION ──────────────── */}
      <main className="relative z-10 max-w-5xl mx-auto px-6 pt-16 pb-20 flex flex-col items-center text-center my-auto">
        {/* Sub-pill badge */}
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-blue-50/95 border border-blue-300/80 text-xs text-blue-700 font-bold mb-6 shadow-2xs backdrop-blur-sm">
          <Sparkles size={14} className="text-blue-600" />
          <span>Continuous Document Intelligence & Semantic Synthesis</span>
        </div>

        {/* Hero Title */}
        <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight font-heading leading-[1.1] mb-5 text-slate-900 drop-shadow-2xs">
          Meet Your <br className="hidden sm:inline" />
          <span className="bg-gradient-to-r from-blue-600 via-indigo-600 to-sky-600 bg-clip-text text-transparent">
            AI Drive Assistant
          </span>
        </h1>

        {/* Hero Subtitle */}
        <p className="max-w-2xl text-base sm:text-lg text-slate-700 leading-relaxed font-normal mb-10 drop-shadow-2xs">
          Struggling to find answers in scattered Google Drive files? Ask questions directly, analyze spreadsheets, extract verified citations, and chat with zero-knowledge privacy.
        </p>

        {/* Single Primary Action Button */}
        <div className="flex items-center justify-center w-full sm:w-auto mb-16">
          <button
            type="button"
            onClick={onContinue}
            className="group relative inline-flex items-center justify-center gap-3 px-9 py-4 rounded-2xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-bold text-base shadow-xl shadow-blue-600/30 active:scale-[0.98] transition-all cursor-pointer border border-blue-700/40 w-full sm:w-auto"
          >
            <span>Continue to Assistant</span>
            <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
          </button>
        </div>

        {/* ──────────────── 4. 3 FEATURE PILLARS CARDS ──────────────── */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 max-w-4xl w-full text-left">
          <div className="p-6 rounded-2xl bg-white/95 border border-slate-200/90 shadow-md hover:shadow-lg hover:border-blue-400 transition-all backdrop-blur-md">
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 border border-blue-100 flex items-center justify-center mb-3.5 shadow-2xs">
              <Database size={19} />
            </div>
            <h4 className="text-sm font-bold text-slate-900 mb-1.5">Google Drive Catalog</h4>
            <p className="text-xs text-slate-600 leading-relaxed">
              Instantly index PDFs, Sheets, and Docs with automatic folder navigation and selective query targeting.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-white/95 border border-slate-200/90 shadow-md hover:shadow-lg hover:border-indigo-400 transition-all backdrop-blur-md">
            <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 border border-indigo-100 flex items-center justify-center mb-3.5 shadow-2xs">
              <Zap size={19} />
            </div>
            <h4 className="text-sm font-bold text-slate-900 mb-1.5">Dual-Mode Intelligence</h4>
            <p className="text-xs text-slate-600 leading-relaxed">
              Get direct answers from Drive documents, or general knowledge guidance even before connecting Drive.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-white/95 border border-slate-200/90 shadow-md hover:shadow-lg hover:border-emerald-400 transition-all backdrop-blur-md">
            <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 border border-emerald-100 flex items-center justify-center mb-3.5 shadow-2xs">
              <Lock size={19} />
            </div>
            <h4 className="text-sm font-bold text-slate-900 mb-1.5">Zero-Knowledge Guardrails</h4>
            <p className="text-xs text-slate-600 leading-relaxed">
              Confidential numbers, financial IDs, and phone numbers are safeguarded with strict redaction layers.
            </p>
          </div>
        </div>
      </main>

      {/* ──────────────── 5. ENHANCED ENTERPRISE FOOTER ──────────────── */}
      <footer className="relative z-10 w-full border-t border-slate-200/80 bg-white/75 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-6 py-8">
          {/* Top Row: Brand Statement & Trust Badges */}
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6 pb-6 border-b border-slate-100">
            {/* Brand identity */}
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-sm shadow-blue-500/20 flex-shrink-0">
                <HardDrive size={17} className="stroke-[2.2]" />
              </div>
              <div>
                <span className="font-heading text-sm font-bold text-slate-900 tracking-tight block">
                  AI Drive Assistant
                </span>
                <span className="text-[11px] text-slate-500 font-normal">
                  Intelligent document synthesis with zero-knowledge privacy.
                </span>
              </div>
            </div>

            {/* Trust & Governance Badges */}
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold">
                <button
                  type="button"
                  onClick={() => setActivePolicyModal("privacy")}
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/80 shadow-2xs hover:bg-emerald-100 transition-all cursor-pointer"
                  title="View Zero-Knowledge Privacy Details"
                >
                  <ShieldCheck size={13} className="text-emerald-600" />
                  Zero-Knowledge Verified
              </button>
              <button
                type="button"
                onClick={() => setActivePolicyModal("privacy")}
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-50 text-blue-700 border border-blue-200/80 shadow-2xs hover:bg-blue-100 transition-all cursor-pointer"
                title="View No Query Storage Policy"
              >
                <Lock size={12} className="text-blue-600" />
                No Query Storage Policy
              </button>
              <button
                type="button"
                onClick={() => setActivePolicyModal("security")}
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-50 text-slate-700 border border-slate-200/80 shadow-2xs hover:bg-slate-100 transition-all cursor-pointer"
                title="View Encryption & Security Standards"
              >
                <CheckCircle2 size={12} className="text-emerald-600" />
                Encrypted at Rest & Transit
            </button>
          </div>
        </div>

        {/* Bottom Row: Copyright, Operational Status & Standards */}
        <div className="pt-6 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 gap-4">
          <div>
            © {new Date().getFullYear()} AI Drive Assistant. All rights reserved.
          </div>

          {/* Operational Status & Links */}
          <div className="flex flex-wrap items-center gap-5">
            <span className="flex items-center gap-2 text-slate-700 font-medium">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              All Systems Operational
            </span>
            <span className="text-slate-300 hidden sm:inline">•</span>
            <Link
              href="/privacy-policy"
              className="text-slate-600 hover:text-blue-600 font-medium transition-colors cursor-pointer hover:underline"
            >
              Privacy Policy
            </Link>
            <span className="text-slate-300 hidden sm:inline">•</span>
            <button
              type="button"
              onClick={() => setActivePolicyModal("security")}
              className="text-slate-600 hover:text-blue-600 font-medium transition-colors cursor-pointer hover:underline"
            >
              Security Standards
            </button>
            <span className="text-slate-300 hidden sm:inline">•</span>
            <button
              type="button"
              onClick={() => setActivePolicyModal("terms")}
              className="text-slate-600 hover:text-blue-600 font-medium transition-colors cursor-pointer hover:underline"
            >
              Terms of Service
            </button>
          </div>
        </div>
    </div>
          </footer >

    {/* ──────────────── 6. POLICY & STANDARDS MODAL ──────────────── */ }
  {
    activePolicyModal && (
      <div
        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-fade-in"
        onClick={() => setActivePolicyModal(null)}
      >
        <div
          className="w-full max-w-2xl max-h-[85vh] flex flex-col rounded-3xl bg-white border border-slate-200/90 shadow-2xl overflow-hidden select-text text-left"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Modal Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/80">
            <div className="flex items-center gap-2.5">
              {activePolicyModal === "privacy" && (
                <div className="w-8 h-8 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center border border-emerald-100">
                  <ShieldCheck size={18} />
                </div>
              )}
              {activePolicyModal === "security" && (
                <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center border border-blue-100">
                  <Lock size={17} />
                </div>
              )}
              {activePolicyModal === "terms" && (
                <div className="w-8 h-8 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center border border-indigo-100">
                  <FileText size={17} />
                </div>
              )}
              <div>
                <h3 className="font-heading text-base font-bold text-slate-900 leading-tight">
                  {activePolicyModal === "privacy" && "Enterprise Privacy Policy"}
                  {activePolicyModal === "security" && "Security Standards & Compliance"}
                  {activePolicyModal === "terms" && "Terms of Service & Usage Governance"}
                </h3>
                <p className="text-[11px] text-slate-500">
                  AI Drive Assistant • Official Documentation
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setActivePolicyModal(null)}
              className="w-8 h-8 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 flex items-center justify-center transition-colors cursor-pointer"
              title="Close"
            >
              <X size={18} />
            </button>
          </div>

          {/* Modal Sub-Navigation Tabs */}
          <div className="flex items-center gap-1.5 px-6 pt-3 pb-2 border-b border-slate-100 bg-white">
            <button
              type="button"
              onClick={() => setActivePolicyModal("privacy")}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${activePolicyModal === "privacy"
                  ? "bg-emerald-50 text-emerald-700 border border-emerald-200/80 shadow-2xs"
                  : "text-slate-500 hover:text-slate-800"
                }`}
            >
              Privacy Policy
            </button>
            <button
              type="button"
              onClick={() => setActivePolicyModal("security")}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${activePolicyModal === "security"
                  ? "bg-blue-50 text-blue-700 border border-blue-200/80 shadow-2xs"
                  : "text-slate-500 hover:text-slate-800"
                }`}
            >
              Security Standards
            </button>
            <button
              type="button"
              onClick={() => setActivePolicyModal("terms")}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${activePolicyModal === "terms"
                  ? "bg-indigo-50 text-indigo-700 border border-indigo-200/80 shadow-2xs"
                  : "text-slate-500 hover:text-slate-800"
                }`}
            >
              Terms of Service
            </button>
          </div>

          {/* Modal Body Content */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4 text-xs text-slate-600 leading-relaxed scrollbar-thin scrollbar-thumb-slate-200">
            {activePolicyModal === "privacy" && (
              <div className="space-y-4 animate-fade-in">
                {/* Official Link Banner */}
                <div className="flex items-center justify-between p-3 rounded-2xl bg-emerald-50/80 border border-emerald-200/80 text-xs">
                  <div>
                    <span className="font-bold text-emerald-900 block">Official Application Privacy Policy</span>
                    <span className="text-[11px] text-emerald-700">Last updated: November 8, 2026</span>
                  </div>
                  <Link
                    href="/privacy-policy"
                    target="_blank"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-600 text-white font-semibold text-xs hover:bg-emerald-700 transition-colors shadow-2xs"
                  >
                    <span>View Dedicated Page</span>
                    <ExternalLink size={12} />
                  </Link>
                </div>

                {/* Highlight card for No Query Storage Policy */}
                <div className="p-3.5 rounded-2xl bg-blue-50/80 border border-blue-200/80 space-y-1.5">
                  <div className="flex items-center gap-1.5 font-bold text-blue-900 text-[13px]">
                    <Lock size={15} className="text-blue-600 flex-shrink-0" />
                    <span>What is our &ldquo;No Query Storage Policy&rdquo;?</span>
                  </div>
                  <p className="text-[11px] text-blue-800 leading-relaxed">
                    AI Drive Assistant enforces a strict <strong>Zero-Retention guarantee</strong> for user questions. When you submit a question, the assistant synthesizes your answer in real time without ever saving, logging, or recording the query text or answer contents into our telemetry databases.
                  </p>
                  <div className="text-[10px] text-blue-700 font-mono pt-1">
                    QueryTelemetry table records: (tokens, latency_ms, cost, timestamp) • Zero prompt text is stored.
                  </div>
                </div>

                <div className="space-y-1">
                  <h4 className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                    <ShieldCheck size={14} className="text-emerald-600" />
                    1. Real-Time Zero-Knowledge Redaction
                  </h4>
                  <p>
                    Multi-layer guardrails scan document chunks before synthesis, automatically redacting Pakistani CNIC numbers (13 digits), PSID transaction identifiers, and private telephone numbers.
                  </p>
                </div>

                <div className="space-y-1">
                  <h4 className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                    <Database size={14} className="text-indigo-600" />
                    2. Read-Only Google Drive OAuth
                  </h4>
                  <p>
                    We access your Google Drive using strict read-only permissions. Files are never modified, shared across different users, or used to train third-party foundation models.
                  </p>
                </div>

                <div className="space-y-1">
                  <h4 className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                    <CheckCircle2 size={14} className="text-emerald-600" />
                    3. User Session Sovereignty
                  </h4>
                  <p>
                    You maintain full sovereignty over your chat history. When you clear or delete a chat session, it is immediately and permanently purged from active browser state.
                  </p>
                </div>
              </div>
            )}

            {activePolicyModal === "security" && (
              <div className="space-y-4 animate-fade-in">
                <div className="p-3.5 rounded-2xl bg-emerald-50/80 border border-emerald-200/80 space-y-1">
                  <div className="flex items-center gap-1.5 font-bold text-emerald-900 text-[13px]">
                    <ShieldCheck size={15} className="text-emerald-600 flex-shrink-0" />
                    <span>Enterprise Security Architecture</span>
                  </div>
                  <p className="text-[11px] text-emerald-800 leading-relaxed">
                    Our infrastructure follows defense-in-depth principles with cryptographic authentication, isolated vector stores, and automated guardrail inspection.
                  </p>
                </div>

                <div className="space-y-1">
                  <h4 className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                    <Lock size={14} className="text-blue-600" />
                    1. Encryption at Rest & In Transit
                  </h4>
                  <p>
                    All communications are secured via TLS 1.3 / HTTPS encryption. Persistent data, vector embeddings, and database credentials are fully encrypted at rest using AES-256.
                  </p>
                </div>

                <div className="space-y-1">
                  <h4 className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                    <KeyRound size={14} className="text-purple-600" />
                    2. Cryptographic Role Gateways (RBAC)
                  </h4>
                  <p>
                    Lead Admin and User Admin portals are secured with stateless JWT tokens with SHA-256 cryptographic signatures. Privilege separation prevents unauthorized quota or audit tampering.
                  </p>
                </div>

                <div className="space-y-1">
                  <h4 className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                    <Terminal size={14} className="text-indigo-600" />
                    3. Strict Tenant Vector Isolation
                  </h4>
                  <p>
                    Document embeddings and vector index spaces are isolated with strict tenant-level filters in PostgreSQL (`pgvector`), preventing cross-user data exposure.
                  </p>
                </div>
              </div>
            )}

            {activePolicyModal === "terms" && (
              <div className="space-y-4 animate-fade-in">
                <div className="p-3.5 rounded-2xl bg-indigo-50/80 border border-indigo-200/80 space-y-1">
                  <div className="flex items-center gap-1.5 font-bold text-indigo-900 text-[13px]">
                    <FileText size={15} className="text-indigo-600 flex-shrink-0" />
                    <span>Terms of Service & Usage Governance</span>
                  </div>
                  <p className="text-[11px] text-indigo-800 leading-relaxed">
                    By using AI Drive Assistant, you agree to these operational rules, fair use standards, and token budget governance.
                  </p>
                </div>

                <div className="space-y-1">
                  <h4 className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                    <Activity size={14} className="text-purple-600" />
                    1. Token Quota & Permanent Non-Reversal Policy
                  </h4>
                  <p>
                    Tokens consumed during query synthesis are permanently deducted from your allocated quota. <strong>Tokens consumed are permanent and never reversed upon chat deletion.</strong>
                  </p>
                </div>

                <div className="space-y-1">
                  <h4 className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                    <HardDrive size={14} className="text-blue-600" />
                    2. Authorized Document Ingestion
                  </h4>
                  <p>
                    Users agree to connect only Google Drive accounts and documents that they own or have explicit legal authority to access. Uploading prohibited or infringing content is strictly prohibited.
                  </p>
                </div>

                <div className="space-y-1">
                  <h4 className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                    <Zap size={14} className="text-amber-500" />
                    3. Dual-Mode Availability
                  </h4>
                  <p>
                    General knowledge queries are processed even when Google Drive is disconnected. Document intelligence features automatically activate when a valid Google Drive is connected.
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Modal Footer */}
          <div className="px-6 py-3.5 border-t border-slate-100 bg-slate-50/70 flex items-center justify-between">
            <span className="text-[11px] text-slate-400">
              Effective: {new Date().getFullYear()} • Enterprise Grade
            </span>
            <button
              type="button"
              onClick={() => setActivePolicyModal(null)}
              className="px-5 py-2 rounded-xl text-xs font-bold text-white bg-slate-900 hover:bg-slate-800 transition-all cursor-pointer shadow-xs active:scale-95"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    )
  }
        </div >
      );
}
