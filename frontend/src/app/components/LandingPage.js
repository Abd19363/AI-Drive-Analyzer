"use client";

import { useState, useEffect } from "react";
import {
  HardDrive,
  ArrowRight,
  ShieldCheck,
  Zap,
  Sparkles,
  Database,
  Lock,
  Play,
  Pause,
  Search,
  FileText,
  FileSpreadsheet,
  CheckCircle2,
  Activity,
  Cpu,
  Clock,
  ShieldAlert,
  ChevronRight,
  FolderOpen
} from "lucide-react";

const SYSTEM_STORY_STEPS = [
  {
    id: "ingestion",
    step: "01",
    label: "Google Drive Sync",
    title: "Instant Drive Ingestion & Semantic Cataloging",
    desc: "Connect your Google Drive in one click. The assistant automatically scans, indexes, and catalogs PDFs, Spreadsheets, and Docs into an organized knowledge base with folder tree navigation.",
    highlight: "Drive Catalog Synced • 100+ Documents Indexed",
    color: "blue",
  },
  {
    id: "guardrails",
    step: "02",
    label: "Zero-Knowledge Guardrails",
    title: "Multi-Layer Privacy & Confidentiality Filter",
    desc: "Before any document chunk reaches the AI synthesis layer, multi-layer guardrails automatically detect and redact CNICs, PSIDs, mobile numbers, and confidential transaction identifiers.",
    highlight: "Zero-Knowledge Verified • PII Automatically Redacted",
    color: "emerald",
  },
  {
    id: "synthesis",
    step: "03",
    label: "Dual-Mode AI Synthesis",
    title: "Intelligent Routing & Citations",
    desc: "Ask any question—from coding guidance to spreadsheet formulas. The system smartly routes queries: general knowledge is answered directly, while document inquiries return synthesized insights with exact source citations.",
    highlight: "Smart Query Routing • Exact Page Citations",
    color: "indigo",
  },
  {
    id: "governance",
    step: "04",
    label: "Governance & Telemetry",
    title: "Real-Time Telemetry & Quota Governance",
    desc: "Lead Admin and User Admin consoles track real-time query latency, prompt and completion tokens, estimated API cost, and individual token quota balances without ever logging private query text.",
    highlight: "Sub-Second Latency (142ms) • Zero-Knowledge Logging",
    color: "purple",
  },
];

export default function LandingPage({ onContinue }) {
  const [activeStoryStep, setActiveStoryStep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(true);

  // Auto-play the system story loop like a modern animated video/gif
  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setActiveStoryStep((prev) => (prev + 1) % SYSTEM_STORY_STEPS.length);
    }, 4500);
    return () => clearInterval(interval);
  }, [isPlaying]);

  const currentStory = SYSTEM_STORY_STEPS[activeStoryStep];

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-blue-50/50 text-slate-900 flex flex-col justify-between relative overflow-hidden select-none font-sans">
      
      {/* ──────────────── 1. BACKGROUND STORY ANIMATION CANVAS ──────────────── */}
      {/* Soft light-mode ambient glows */}
      <div className="absolute top-[-10%] left-[-10%] w-[550px] h-[550px] rounded-full bg-blue-400/10 blur-[130px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[600px] h-[600px] rounded-full bg-indigo-400/10 blur-[140px] pointer-events-none" />
      <div className="absolute top-[40%] left-[50%] -translate-x-1/2 -translate-y-1/2 w-[800px] h-[450px] rounded-full bg-sky-300/10 blur-[150px] pointer-events-none" />

      {/* Decorative Grid Pattern Overlay */}
      <div 
        className="absolute inset-0 opacity-[0.35] pointer-events-none"
        style={{
          backgroundImage: `radial-gradient(rgba(148, 163, 184, 0.25) 1px, transparent 1px)`,
          backgroundSize: "28px 28px"
        }}
      />

      {/* Dynamic Animated Flow Beams connecting the system story in the background */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-40 z-0" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="beamGrad1" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.4" />
            <stop offset="50%" stopColor="#6366f1" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#10b981" stopOpacity="0.4" />
          </linearGradient>
        </defs>
        {/* Curving flow paths representing data pipeline from Drive -> Security -> AI -> Telemetry */}
        <path
          d="M 150 180 C 400 120, 600 280, 850 190 C 1100 100, 1250 250, 1400 220"
          fill="none"
          stroke="url(#beamGrad1)"
          strokeWidth="2"
          className="animate-flow-dash"
        />
        <path
          d="M 100 550 C 350 480, 650 620, 950 530 C 1200 440, 1350 600, 1550 550"
          fill="none"
          stroke="url(#beamGrad1)"
          strokeWidth="1.5"
          className="animate-flow-dash"
          style={{ animationDuration: "2.4s" }}
        />
      </svg>

      {/* ──────────────── FLOATING STORY ARCHITECTURE CARDS (BACKGROUND) ──────────────── */}
      {/* Node 1: Drive Discovery (Top-Left Background) */}
      <div className="hidden lg:flex absolute top-28 left-6 w-72 p-3.5 rounded-2xl bg-white/70 border border-slate-200/70 shadow-lg shadow-blue-500/5 backdrop-blur-md pointer-events-none animate-float-slow opacity-60 z-0">
        <div className="flex items-center gap-2.5 mb-2.5">
          <div className="w-7 h-7 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center flex-shrink-0">
            <HardDrive size={15} />
          </div>
          <div>
            <div className="text-[11px] font-bold text-slate-800">1. Drive Cataloging</div>
            <div className="text-[9px] text-emerald-600 font-semibold flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Auto-Indexed
            </div>
          </div>
        </div>
        <div className="space-y-1.5 text-[10px] text-slate-600">
          <div className="flex items-center justify-between px-2 py-1 rounded-md bg-slate-50/80 border border-slate-100">
            <span className="flex items-center gap-1.5 truncate">
              <FileText size={11} className="text-rose-500" />
              AI Developer Roadmap.pdf
            </span>
            <span className="text-[9px] text-emerald-600 font-bold">READY</span>
          </div>
          <div className="flex items-center justify-between px-2 py-1 rounded-md bg-slate-50/80 border border-slate-100">
            <span className="flex items-center gap-1.5 truncate">
              <FileSpreadsheet size={11} className="text-emerald-600" />
              Q3_Financial_Audit.xlsx
            </span>
            <span className="text-[9px] text-emerald-600 font-bold">READY</span>
          </div>
        </div>
      </div>

      {/* Node 2: Zero-Knowledge Guardrails (Top-Right Background) */}
      <div className="hidden lg:flex absolute top-28 right-6 w-72 p-3.5 rounded-2xl bg-white/70 border border-slate-200/70 shadow-lg shadow-emerald-500/5 backdrop-blur-md pointer-events-none animate-float-reverse opacity-60 z-0">
        <div className="flex items-center gap-2.5 mb-2.5">
          <div className="w-7 h-7 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center flex-shrink-0">
            <ShieldCheck size={15} />
          </div>
          <div>
            <div className="text-[11px] font-bold text-slate-800">2. Privacy Guardrails</div>
            <div className="text-[9px] text-indigo-600 font-semibold">Active Redaction Scan</div>
          </div>
        </div>
        <div className="p-2 rounded-lg bg-emerald-50/60 border border-emerald-200/70 text-[10px] text-emerald-800 space-y-1 relative overflow-hidden">
          <div className="absolute inset-x-0 h-0.5 bg-emerald-400/80 animate-scan" />
          <div className="flex items-center justify-between font-semibold">
            <span>Sensitive Data Filter:</span>
            <span className="text-[9px] bg-emerald-100 px-1.5 py-0.2 rounded text-emerald-700">PASSED</span>
          </div>
          <p className="text-[9px] text-slate-500 font-mono">
            PSID: [WITHHELD] | Phone: [REDACTED]
          </p>
        </div>
      </div>

      {/* Node 3: AI Co-Pilot Query (Bottom-Left Background) */}
      <div className="hidden lg:flex absolute bottom-24 left-8 w-72 p-3.5 rounded-2xl bg-white/70 border border-slate-200/70 shadow-lg shadow-indigo-500/5 backdrop-blur-md pointer-events-none animate-float-reverse opacity-60 z-0">
        <div className="flex items-center gap-2.5 mb-2">
          <div className="w-7 h-7 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center flex-shrink-0">
            <Zap size={15} />
          </div>
          <div>
            <div className="text-[11px] font-bold text-slate-800">3. Dual-Mode Synthesis</div>
            <div className="text-[9px] text-slate-400">Gemini 2.5 Flash Engine</div>
          </div>
        </div>
        <div className="p-2 rounded-lg bg-slate-50 border border-slate-100 text-[10px] text-slate-700 leading-relaxed">
          <p className="font-semibold text-blue-700 text-[10px] mb-0.5">&ldquo;What is Phase 1 roadmap?&rdquo;</p>
          <p className="text-slate-600 line-clamp-2">Phase 1 covers Frontend Basics (HTML, CSS, React) followed by Backend...</p>
          <div className="mt-1 inline-flex items-center gap-1 text-[8px] font-semibold text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200/60">
            Source: AI Developer Roadmap
          </div>
        </div>
      </div>

      {/* Node 4: Lead Admin Governance Telemetry (Bottom-Right Background) */}
      <div className="hidden lg:flex absolute bottom-24 right-8 w-72 p-3.5 rounded-2xl bg-white/70 border border-slate-200/70 shadow-lg shadow-purple-500/5 backdrop-blur-md pointer-events-none animate-float-slow opacity-60 z-0">
        <div className="flex items-center gap-2.5 mb-2">
          <div className="w-7 h-7 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center flex-shrink-0">
            <Activity size={15} />
          </div>
          <div>
            <div className="text-[11px] font-bold text-slate-800">4. Telemetry Governance</div>
            <div className="text-[9px] text-slate-400">Zero-Knowledge Metrics</div>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-1.5 text-center">
          <div className="p-1.5 rounded-lg bg-slate-50 border border-slate-100">
            <div className="text-[12px] font-extrabold text-slate-900">142ms</div>
            <div className="text-[8px] text-slate-400 uppercase font-semibold">Avg Latency</div>
          </div>
          <div className="p-1.5 rounded-lg bg-slate-50 border border-slate-100">
            <div className="text-[12px] font-extrabold text-purple-600">160K</div>
            <div className="text-[8px] text-slate-400 uppercase font-semibold">Token Quota</div>
          </div>
        </div>
      </div>

      {/* ──────────────── 2. TOP HEADER ──────────────── */}
      <header className="relative z-10 max-w-7xl mx-auto w-full px-6 py-5 flex items-center justify-between border-b border-slate-200/60 bg-white/70 backdrop-blur-md">
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

        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/80 shadow-2xs">
            <ShieldCheck size={13} className="text-emerald-600" />
            Enterprise Privacy
          </span>
          <button
            type="button"
            onClick={onContinue}
            className="hidden sm:inline-flex items-center gap-1.5 px-4 py-1.5 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 transition-all shadow-sm shadow-blue-500/20 active:scale-95"
          >
            <span>Open Portal</span>
            <ChevronRight size={14} />
          </button>
        </div>
      </header>

      {/* ──────────────── 3. HERO CONTENT SECTION ──────────────── */}
      <main className="relative z-10 max-w-5xl mx-auto px-6 pt-10 pb-16 flex flex-col items-center text-center my-auto">
        {/* Sub-pill badge */}
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-blue-50/90 border border-blue-200/90 text-xs text-blue-700 font-semibold mb-6 shadow-2xs">
          <Sparkles size={14} className="text-blue-600" />
          <span>Continuous Document Intelligence & Semantic Synthesis</span>
        </div>

        {/* Hero Title */}
        <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight font-heading leading-[1.1] mb-5 text-slate-900">
          Meet Your <br className="hidden sm:inline" />
          <span className="bg-gradient-to-r from-blue-600 via-indigo-600 to-sky-600 bg-clip-text text-transparent">
            AI Drive Assistant
          </span>
        </h1>

        {/* Hero Subtitle */}
        <p className="max-w-2xl text-base sm:text-lg text-slate-600 leading-relaxed font-normal mb-8">
          Transform your Google Drive into an interactive knowledge base. Ask questions, analyze spreadsheets, extract citations, and chat seamlessly—with built-in zero-knowledge privacy.
        </p>

        {/* Hero Actions */}
        <div className="flex flex-col sm:flex-row items-center gap-3.5 w-full sm:w-auto mb-14">
          <button
            type="button"
            onClick={onContinue}
            className="group relative inline-flex items-center justify-center gap-3 px-8 py-4 rounded-2xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-bold text-base shadow-xl shadow-blue-600/25 active:scale-[0.98] transition-all cursor-pointer border border-blue-700/40 w-full sm:w-auto"
          >
            <span>Continue to Assistant</span>
            <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
          </button>

          <button
            type="button"
            onClick={() => setIsPlaying(!isPlaying)}
            className="inline-flex items-center gap-2 px-4 py-3.5 rounded-2xl bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold border border-slate-200 shadow-xs transition-all w-full sm:w-auto justify-center"
            title={isPlaying ? "Pause system simulation" : "Play system simulation"}
          >
            {isPlaying ? <Pause size={14} className="text-blue-600" /> : <Play size={14} className="text-blue-600" />}
            <span>{isPlaying ? "Simulating Workflow..." : "Resume Story Walkthrough"}</span>
          </button>
        </div>

        {/* ──────────────── 4. SYSTEM STORY SIMULATION SHOWCASE (VIDEO/GIF STYLE) ──────────────── */}
        <div className="w-full max-w-4xl bg-white/90 border border-slate-200/90 rounded-3xl shadow-xl shadow-slate-200/50 p-6 backdrop-blur-md text-left transition-all relative overflow-hidden">
          
          {/* Top Simulation Player Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4 mb-5">
            <div className="flex items-center gap-2.5">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-ping" />
              <span className="text-xs font-bold text-slate-800 tracking-tight uppercase">
                System Lifecycle Walkthrough
              </span>
              <span className="text-[10px] text-slate-400 bg-slate-100 px-2 py-0.5 rounded-full font-mono">
                {currentStory.step} of 04
              </span>
            </div>

            {/* Stepper Tabs */}
            <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none">
              {SYSTEM_STORY_STEPS.map((s, idx) => {
                const isActive = idx === activeStoryStep;
                return (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => {
                      setActiveStoryStep(idx);
                      setIsPlaying(false);
                    }}
                    className={`px-3 py-1 rounded-xl text-[11px] font-semibold transition-all flex items-center gap-1.5 flex-shrink-0 cursor-pointer ${
                      isActive
                        ? "bg-blue-600 text-white shadow-xs"
                        : "bg-slate-100 text-slate-600 hover:bg-slate-200/80"
                    }`}
                  >
                    <span>{s.step}</span>
                    <span className="hidden md:inline">{s.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Active Story Visual Experience */}
          <div className="grid grid-cols-1 lg:grid-cols-[1.2fr_1fr] gap-6 items-center">
            {/* Story Explanation */}
            <div>
              <div className="inline-flex items-center gap-1.5 text-[11px] font-bold text-blue-700 bg-blue-50 px-2.5 py-1 rounded-lg border border-blue-200/60 mb-2.5">
                <Sparkles size={12} />
                {currentStory.highlight}
              </div>
              <h3 className="font-heading text-xl sm:text-2xl font-bold text-slate-900 mb-2 leading-tight">
                {currentStory.title}
              </h3>
              <p className="text-xs sm:text-sm text-slate-600 leading-relaxed mb-4">
                {currentStory.desc}
              </p>

              {/* Dynamic Factors checklist */}
              <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-700 font-medium">
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 size={13} className="text-emerald-600 flex-shrink-0" />
                  <span>Real-time Google OAuth</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 size={13} className="text-emerald-600 flex-shrink-0" />
                  <span>Vector chunk indexing</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 size={13} className="text-emerald-600 flex-shrink-0" />
                  <span>Redaction safety net</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 size={13} className="text-emerald-600 flex-shrink-0" />
                  <span>Live token budgeting</span>
                </div>
              </div>
            </div>

            {/* Live Interactive UI Simulation Mockup */}
            <div className="bg-slate-50/90 border border-slate-200/80 rounded-2xl p-4 shadow-inner">
              {activeStoryStep === 0 && (
                <div className="space-y-2.5 animate-fade-in">
                  <div className="flex items-center justify-between text-xs font-bold text-slate-700 border-b border-slate-200 pb-2">
                    <span className="flex items-center gap-1.5">
                      <FolderOpen size={14} className="text-amber-500" />
                      Drive Catalog Explorer
                    </span>
                    <span className="text-[10px] text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                      LIVE SYNC
                    </span>
                  </div>
                  <div className="space-y-1.5 text-xs">
                    <div className="flex items-center justify-between p-2 rounded-xl bg-white border border-slate-200/60 shadow-2xs">
                      <div className="flex items-center gap-2 truncate">
                        <FileText size={14} className="text-rose-500" />
                        <span className="font-medium text-slate-800">AI Developer Roadmap.pdf</span>
                      </div>
                      <span className="text-[10px] text-slate-400">PDF • 1.2 MB</span>
                    </div>
                    <div className="flex items-center justify-between p-2 rounded-xl bg-white border border-slate-200/60 shadow-2xs">
                      <div className="flex items-center gap-2 truncate">
                        <FileSpreadsheet size={14} className="text-emerald-600" />
                        <span className="font-medium text-slate-800">Q3_Budget_Audit.xlsx</span>
                      </div>
                      <span className="text-[10px] text-slate-400">Sheet • 45 KB</span>
                    </div>
                  </div>
                </div>
              )}

              {activeStoryStep === 1 && (
                <div className="space-y-2.5 animate-fade-in">
                  <div className="flex items-center justify-between text-xs font-bold text-slate-700 border-b border-slate-200 pb-2">
                    <span className="flex items-center gap-1.5">
                      <ShieldCheck size={14} className="text-emerald-600" />
                      Zero-Knowledge Privacy Layer
                    </span>
                    <span className="text-[10px] text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded">
                      ACTIVE
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-white border border-slate-200/70 text-xs space-y-1.5 shadow-2xs">
                    <div className="text-[11px] font-semibold text-slate-500">Document Chunk Guardrail Inspection:</div>
                    <div className="p-2 rounded bg-rose-50/70 border border-rose-200/70 text-[11px] text-rose-800 font-mono">
                      CNIC: 35201-XXXXXXX-X [WITHHELD]
                    </div>
                    <div className="text-[10px] text-emerald-600 font-semibold flex items-center gap-1">
                      <CheckCircle2 size={12} /> Confidential data blocked before LLM transmission.
                    </div>
                  </div>
                </div>
              )}

              {activeStoryStep === 2 && (
                <div className="space-y-2.5 animate-fade-in">
                  <div className="flex items-center justify-between text-xs font-bold text-slate-700 border-b border-slate-200 pb-2">
                    <span className="flex items-center gap-1.5">
                      <Zap size={14} className="text-indigo-600" />
                      Conversational Co-Pilot
                    </span>
                    <span className="text-[10px] text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200">
                      RAG SYNTHESIS
                    </span>
                  </div>
                  <div className="space-y-2 text-xs">
                    <div className="p-2 rounded-xl bg-blue-600 text-white text-[11px] self-end ml-4 shadow-xs">
                      &ldquo;Give me the Full Stack Roadmap.&rdquo;
                    </div>
                    <div className="p-2 rounded-xl bg-white border border-slate-200 text-[11px] text-slate-800 space-y-1 shadow-2xs">
                      <p className="font-semibold text-slate-900">Summary from AI Developer Roadmap:</p>
                      <p className="text-slate-600 text-[10px]">Phase 1: Frontend Basics • Phase 2: Backend APIs • Phase 3: Cloud & DevOps.</p>
                      <span className="inline-block text-[9px] font-bold text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200">
                        Title: Full Stack Roadmap (3 words)
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {activeStoryStep === 3 && (
                <div className="space-y-2.5 animate-fade-in">
                  <div className="flex items-center justify-between text-xs font-bold text-slate-700 border-b border-slate-200 pb-2">
                    <span className="flex items-center gap-1.5">
                      <Activity size={14} className="text-purple-600" />
                      Governance & Telemetry
                    </span>
                    <span className="text-[10px] text-purple-700 bg-purple-50 px-2 py-0.5 rounded border border-purple-200">
                      ZERO-KNOWLEDGE
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="p-2 rounded-xl bg-white border border-slate-200/80 text-center shadow-2xs">
                      <div className="text-[13px] font-extrabold text-slate-900">160,000</div>
                      <div className="text-[9px] text-slate-400 font-semibold uppercase">Assigned Quota</div>
                    </div>
                    <div className="p-2 rounded-xl bg-white border border-slate-200/80 text-center shadow-2xs">
                      <div className="text-[13px] font-extrabold text-emerald-600">$0.0004</div>
                      <div className="text-[9px] text-slate-400 font-semibold uppercase">API Cost</div>
                    </div>
                  </div>
                  <div className="p-2 rounded-lg bg-emerald-50 text-[10px] text-emerald-800 font-medium border border-emerald-200 flex items-center gap-1.5">
                    <CheckCircle2 size={13} className="text-emerald-600 flex-shrink-0" />
                    <span>Tokens consumed are permanent and never reversed upon chat deletion.</span>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Bottom auto-playing progress indicator */}
          <div className="w-full bg-slate-100 h-1.5 rounded-full mt-6 overflow-hidden">
            <div 
              className="bg-gradient-to-r from-blue-600 via-indigo-600 to-sky-500 h-full transition-all duration-500"
              style={{ width: `${((activeStoryStep + 1) / SYSTEM_STORY_STEPS.length) * 100}%` }}
            />
          </div>
        </div>

        {/* ──────────────── 5. 3 FEATURE PILLARS ──────────────── */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 max-w-4xl w-full mt-12 text-left">
          <div className="p-6 rounded-2xl bg-white/90 border border-slate-200/80 shadow-xs hover:shadow-md hover:border-blue-300 transition-all backdrop-blur-sm">
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 border border-blue-100 flex items-center justify-center mb-3.5 shadow-2xs">
              <Database size={19} />
            </div>
            <h4 className="text-sm font-bold text-slate-900 mb-1.5">Google Drive Catalog</h4>
            <p className="text-xs text-slate-600 leading-relaxed">
              Instantly index PDFs, Sheets, and Docs with automatic folder navigation and selective query targeting.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-white/90 border border-slate-200/80 shadow-xs hover:shadow-md hover:border-indigo-300 transition-all backdrop-blur-sm">
            <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 border border-indigo-100 flex items-center justify-center mb-3.5 shadow-2xs">
              <Zap size={19} />
            </div>
            <h4 className="text-sm font-bold text-slate-900 mb-1.5">Dual-Mode Intelligence</h4>
            <p className="text-xs text-slate-600 leading-relaxed">
              Get direct answers from Drive documents, or general knowledge guidance even before connecting Drive.
            </p>
          </div>

          <div className="p-6 rounded-2xl bg-white/90 border border-slate-200/80 shadow-xs hover:shadow-md hover:border-emerald-300 transition-all backdrop-blur-sm">
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

      {/* ──────────────── 6. FOOTER ──────────────── */}
      <footer className="relative z-10 max-w-7xl mx-auto w-full px-6 py-5 border-t border-slate-200/70 bg-white/40 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 gap-3">
        <div>
          © {new Date().getFullYear()} AI Drive Assistant. All rights reserved.
        </div>
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5 text-slate-600">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            System Online
          </span>
          <span className="text-slate-300">•</span>
          <span className="text-slate-500">FastAPI & Next.js Engine</span>
        </div>
      </footer>
    </div>
  );
}
