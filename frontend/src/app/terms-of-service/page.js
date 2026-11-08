import Link from "next/link";
import {
  FileText,
  ArrowLeft,
  ShieldCheck,
  Lock,
  Database,
  ExternalLink,
  Mail,
  Globe,
  Server,
  Cpu,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Scale,
  Ban,
  UserCheck,
  HelpCircle,
} from "lucide-react";

export const metadata = {
  title: "Terms of Service | AI Drive Assistant",
  description:
    "Official Terms of Service for AI Drive Assistant. Understand your rights, acceptable use, Google Drive read-only access, and AI-generated responses.",
};

const sections = [
  { id: "about", title: "1. About AI Drive Assistant" },
  { id: "eligibility", title: "2. Eligibility & User Accounts" },
  { id: "google-access", title: "3. Google Account & Drive Access" },
  { id: "acceptable-use", title: "4. Acceptable Use" },
  { id: "ownership", title: "5. Document Ownership & Permissions" },
  { id: "ai-responses", title: "6. AI & Generated Responses" },
  { id: "third-party", title: "7. Third-Party Services" },
  { id: "privacy", title: "8. Privacy & Data Handling" },
  { id: "disconnection-deletion", title: "9. Account Disconnection & Deletion" },
  { id: "availability", title: "10. Service Availability & Changes" },
  { id: "intellectual-property", title: "11. Intellectual Property" },
  { id: "disclaimer", title: "12. Disclaimer of Warranties" },
  { id: "liability", title: "13. Limitation of Liability" },
  { id: "termination", title: "14. Suspension & Termination" },
  { id: "changes", title: "15. Changes to These Terms" },
  { id: "governing-law", title: "16. Governing Law" },
  { id: "contact", title: "17. Contact Information" },
];

export default function TermsOfServicePage() {
  return (
    <div className="min-h-screen bg-[#f8fafc] text-slate-800 font-sans selection:bg-blue-100 selection:text-blue-900">
      {/* ── TOP NAV ── */}
      <header className="sticky top-0 z-40 bg-white/90 backdrop-blur-md border-b border-slate-200/80 shadow-2xs">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link
            href="/"
            className="flex items-center gap-2.5 group cursor-pointer"
            title="Return to AI Drive Assistant"
          >
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 text-white flex items-center justify-center shadow-sm shadow-blue-500/25 group-hover:scale-105 transition-transform">
              <FileText size={20} />
            </div>
            <div>
              <span className="font-heading font-bold text-slate-900 text-base tracking-tight block leading-tight">
                AI Drive Assistant
              </span>
              <span className="text-[10px] text-slate-500 font-medium tracking-wide uppercase">
                Terms of Service & Usage Governance
              </span>
            </div>
          </Link>

          <Link
            href="/"
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold text-slate-700 bg-slate-100/90 hover:bg-slate-200/80 border border-slate-200 transition-all cursor-pointer shadow-2xs"
          >
            <ArrowLeft size={14} />
            <span>Back to Application</span>
          </Link>
        </div>
      </header>

      {/* ── HERO BANNER ── */}
      <div className="bg-gradient-to-b from-white via-indigo-50/20 to-[#f8fafc] border-b border-slate-200/70 pt-12 pb-10">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-200/80 text-indigo-800 text-[11px] font-semibold mb-4 shadow-2xs">
            <Scale size={13} className="text-indigo-600" />
            Official Service Governance • Binding Agreement
          </div>

          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-slate-900 tracking-tight font-heading mb-3">
            Terms of Service
          </h1>

          <p className="text-sm sm:text-base text-slate-600 max-w-3xl leading-relaxed">
            These Terms of Service govern your access to and use of <strong>AI Drive Assistant</strong>. By accessing or using the Service, you agree to these Terms and our data governance principles.
          </p>

          <div className="mt-5 flex flex-wrap items-center gap-4 text-xs text-slate-500 pt-3 border-t border-slate-200/60">
            <div className="flex items-center gap-1.5 font-medium text-slate-700">
              <Clock size={14} className="text-indigo-600" />
              <span>Effective Date: <strong>November 8, 2026</strong></span>
            </div>
            <span>•</span>
            <div className="flex items-center gap-1.5">
              <Globe size={14} className="text-slate-400" />
              <span>Application: AI Drive Assistant</span>
            </div>
            <span>•</span>
            <div className="flex items-center gap-1.5">
              <ShieldCheck size={14} className="text-emerald-600" />
              <span>Read-Only Google Drive Access</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── MAIN CONTENT AREA ── */}
      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-10">
          {/* SIDEBAR TABLE OF CONTENTS */}
          <aside className="lg:col-span-4 hidden lg:block">
            <div className="sticky top-24 p-5 rounded-2xl bg-white border border-slate-200/80 shadow-xs space-y-4">
              <div className="flex items-center gap-2 text-xs font-bold text-slate-900 uppercase tracking-wider pb-2 border-b border-slate-100">
                <FileText size={15} className="text-indigo-600" />
                <span>Table of Contents</span>
              </div>

              <nav className="space-y-1 text-xs">
                {sections.map((section) => (
                  <a
                    key={section.id}
                    href={`#${section.id}`}
                    className="block px-2.5 py-1.5 rounded-lg text-slate-600 hover:text-indigo-700 hover:bg-indigo-50/70 font-medium transition-colors"
                  >
                    {section.title}
                  </a>
                ))}
              </nav>

              <div className="pt-3 border-t border-slate-100 text-[11px] text-slate-500 space-y-1">
                <p className="font-semibold text-slate-700">Related Documents</p>
                <p>
                  Review our{" "}
                  <Link
                    href="/privacy-policy"
                    className="text-blue-600 hover:underline font-medium"
                  >
                    Privacy Policy
                  </Link>
                </p>
              </div>
            </div>
          </aside>

          {/* TERMS CONTENT BODY */}
          <article className="lg:col-span-8 space-y-8 text-slate-700 leading-relaxed text-sm">
            {/* Preamble */}
            <div className="p-5 rounded-2xl bg-white border border-slate-200/80 shadow-xs space-y-2">
              <p>
                Welcome to <strong>AI Drive Assistant</strong>. These Terms of Service (&ldquo;Terms&rdquo;) govern your access to and use of the AI Drive Assistant website, application, and related services (&ldquo;Service&rdquo;).
              </p>
              <p className="font-medium text-slate-900 bg-indigo-50/60 p-3.5 rounded-xl border border-indigo-200/60 text-xs">
                By accessing or using AI Drive Assistant, you agree to these Terms. If you do not agree, please do not use the Service.
              </p>
            </div>

            {/* 1. About AI Drive Assistant */}
            <section
              id="about"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-4 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-sm border border-indigo-100">
                  1
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  1. About AI Drive Assistant
                </h2>
              </div>

              <p>
                AI Drive Assistant is an AI-powered document analysis and question-answering application that allows users to connect their Google Drive accounts, process documents, and ask questions about their document content.
              </p>
              <p>
                The Service may use artificial intelligence, document extraction, optical character recognition (OCR), embeddings, and retrieval-augmented generation (RAG) technologies to provide responses.
              </p>
            </section>

            {/* 2. Eligibility and User Accounts */}
            <section
              id="eligibility"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-4 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-sm border border-indigo-100">
                  2
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  2. Eligibility and User Accounts
                </h2>
              </div>

              <p>To use the Service, you must:</p>
              <ul className="list-disc list-inside space-y-1.5 text-xs text-slate-700 ml-1">
                <li>Be legally capable of entering into a binding agreement.</li>
                <li>Provide accurate information when creating or accessing an account.</li>
                <li>Maintain the security of your account and authentication credentials.</li>
                <li>Notify us if you suspect unauthorized access to your account.</li>
                <li>Use the Service in compliance with applicable laws and these Terms.</li>
              </ul>
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/70 text-xs text-slate-700 font-semibold">
                You are responsible for activities performed through your account.
              </div>
            </section>

            {/* 3. Google Account and Drive Access */}
            <section
              id="google-access"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-4 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-sm border border-indigo-100">
                  3
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  3. Google Account and Drive Access
                </h2>
              </div>

              <p>
                AI Drive Assistant allows you to connect your Google account through Google OAuth authentication.
              </p>
              <p>When you authorize access:</p>
              <ul className="list-disc list-inside space-y-1.5 text-xs text-slate-700 ml-1">
                <li>The application may access permitted Google Drive files and metadata.</li>
                <li>Google Drive access is requested using read-only permissions.</li>
                <li>The Service may extract document text and process supported file formats.</li>
                <li>Extracted content, document chunks, and embeddings may be stored to provide search and question-answering functionality.</li>
              </ul>

              <div className="p-3.5 bg-emerald-50/80 rounded-xl border border-emerald-200/70 text-xs text-emerald-900 font-semibold flex items-center gap-2">
                <CheckCircle2 size={16} className="text-emerald-600 flex-shrink-0" />
                <span>AI Drive Assistant does not intentionally modify or delete your original Google Drive files.</span>
              </div>

              <p className="text-xs text-slate-600">
                Your use of Google services remains subject to Google&apos;s applicable terms and policies.
              </p>
              <p className="text-xs text-slate-600">
                You can disconnect your Google account through the application&apos;s available controls. Disconnecting removes stored Google OAuth credentials and cached answers, but does not automatically delete your account or all previously indexed document content.
              </p>
            </section>

            {/* 4. Acceptable Use */}
            <section
              id="acceptable-use"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-4 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center font-bold text-sm border border-rose-100">
                  4
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  4. Acceptable Use
                </h2>
              </div>

              <p>You agree not to:</p>
              <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                {[
                  "Use the Service for unlawful, fraudulent, or harmful activities.",
                  "Access documents or Google Drive accounts without proper authorization.",
                  "Upload, process, or use documents that violate another person's intellectual property or privacy rights.",
                  "Attempt to gain unauthorized access to the application, its servers, databases, or infrastructure.",
                  "Interfere with the operation, security, or availability of the Service.",
                  "Introduce malicious software, harmful code, or automated attacks.",
                  "Reverse engineer or exploit the Service except where permitted by applicable law.",
                ].map((item, idx) => (
                  <li
                    key={idx}
                    className="p-3 rounded-xl bg-slate-50 border border-slate-200/70 text-slate-700 flex items-start gap-2"
                  >
                    <Ban size={14} className="text-rose-600 mt-0.5 flex-shrink-0" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>

              <div className="p-3 bg-amber-50/80 rounded-xl border border-amber-200/70 text-xs text-amber-900 font-medium">
                We reserve the right to restrict or suspend access when we reasonably believe these Terms have been violated.
              </div>
            </section>

            {/* 5. Document Ownership and Permissions */}
            <section
              id="ownership"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-4 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-sm border border-indigo-100">
                  5
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  5. Document Ownership and Permissions
                </h2>
              </div>

              <p>
                You retain ownership of documents and other content that you access or process through AI Drive Assistant.
              </p>
              <p>By using the Service, you confirm that:</p>
              <ul className="list-disc list-inside space-y-1 text-xs text-slate-700 ml-1">
                <li>You own the content or have permission to access and process it.</li>
                <li>Your use of the content does not violate applicable laws or third-party rights.</li>
                <li>You authorize us to process the content as necessary to provide the Service.</li>
              </ul>
              <p className="text-xs text-slate-600">
                You grant AI Drive Assistant a limited, non-exclusive permission to access, extract, process, store, and analyze authorized content solely for operating and improving the functionality of the Service.
              </p>
              <div className="p-3.5 bg-blue-50/70 rounded-xl border border-blue-200/70 text-xs text-blue-900 font-semibold">
                This permission does not transfer ownership of your documents to us.
              </div>
            </section>

            {/* 6. Artificial Intelligence and Generated Responses */}
            <section
              id="ai-responses"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-4 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-sm border border-indigo-100">
                  6
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  6. Artificial Intelligence and Generated Responses
                </h2>
              </div>

              <p>
                AI Drive Assistant uses third-party artificial intelligence services, including Google&apos;s Gemini models, to generate responses based on user questions and relevant document content.
              </p>
              <p>You acknowledge that:</p>
              <ul className="list-disc list-inside space-y-1.5 text-xs text-slate-700 ml-1">
                <li>AI-generated responses may be inaccurate, incomplete, outdated, or misleading.</li>
                <li>The Service may misunderstand document content or fail to retrieve relevant information.</li>
                <li>Responses should not be treated as professional legal, medical, financial, or other expert advice.</li>
                <li>You are responsible for independently verifying important information before relying on it.</li>
              </ul>
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-600 italic">
                We do not guarantee that AI-generated answers will always be accurate or suitable for a particular purpose.
              </div>
            </section>

            {/* 7. Third-Party Services */}
            <section
              id="third-party"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-4 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-sm border border-indigo-100">
                  7
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  7. Third-Party Services
                </h2>
              </div>

              <p>The Service depends on third-party providers and technologies, which may include:</p>
              <ul className="list-disc list-inside space-y-1 text-xs text-slate-700 ml-1">
                <li>Google OAuth and Google Drive APIs.</li>
                <li>Google Gemini AI services.</li>
                <li>Cloud hosting and database infrastructure providers.</li>
                <li>Other software libraries and infrastructure services.</li>
              </ul>
              <p className="text-xs text-slate-600">
                Your use of third-party services may also be subject to their own terms, conditions, and privacy policies.
              </p>
              <p className="text-xs text-slate-600">
                We are not responsible for interruptions, changes, or failures caused by third-party services beyond our reasonable control.
              </p>
            </section>

            {/* 8. Privacy and Data Handling */}
            <section
              id="privacy"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-4 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-sm border border-indigo-100">
                  8
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  8. Privacy and Data Handling
                </h2>
              </div>

              <p>Your use of AI Drive Assistant is also governed by our Privacy Policy:</p>

              <div className="p-4 rounded-2xl bg-blue-50/70 border border-blue-200/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                <div>
                  <span className="font-bold text-blue-900 block">AI Drive Assistant Privacy Policy</span>
                  <span className="text-blue-700 font-mono text-[11px]">https://ai-drive-assistant.duckdns.org/privacy-policy</span>
                </div>
                <Link
                  href="/privacy-policy"
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-blue-600 text-white font-semibold hover:bg-blue-700 transition-colors self-start sm:self-auto"
                >
                  <span>Read Privacy Policy</span>
                  <ExternalLink size={12} />
                </Link>
              </div>

              <p className="text-xs text-slate-600">
                The Privacy Policy explains what information may be collected, how documents are processed, how third-party services are involved, and how account information is handled.
              </p>
              <p className="text-xs text-slate-600 font-medium">
                You should review the Privacy Policy before connecting your Google Drive account.
              </p>
            </section>

            {/* 9. Account Disconnection and Deletion */}
            <section
              id="disconnection-deletion"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-4 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-sm border border-indigo-100">
                  9
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  9. Account Disconnection and Deletion
                </h2>
              </div>

              <p>
                You may disconnect your Google account using the application&apos;s available functionality.
              </p>
              <p className="text-xs text-slate-600">
                Disconnecting your Google account removes stored OAuth credentials and cached answers, but does not automatically remove your account or all indexed document content.
              </p>
              <p className="text-xs text-slate-600">
                Account deletion may currently require administrative assistance.
              </p>
              <p className="text-xs text-slate-600">
                Where an account deletion is performed, associated application data may be deleted in accordance with the application&apos;s data-management processes and applicable retention requirements.
              </p>
              <p className="text-xs text-slate-600">
                For account deletion assistance, contact us using the contact information provided below.
              </p>
            </section>

            {/* 10. Service Availability and Changes */}
            <section
              id="availability"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-4 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-sm border border-indigo-100">
                  10
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  10. Service Availability and Changes
                </h2>
              </div>

              <p>
                We aim to maintain the availability and functionality of AI Drive Assistant, but we do not guarantee uninterrupted or error-free operation.
              </p>
              <p>We may:</p>
              <ul className="list-disc list-inside space-y-1 text-xs text-slate-700 ml-1">
                <li>Modify or improve application functionality.</li>
                <li>Introduce new features or remove existing features.</li>
                <li>Perform maintenance or temporarily restrict access.</li>
                <li>Suspend or discontinue parts of the Service when necessary.</li>
              </ul>
              <p className="text-xs text-slate-600">
                We will make reasonable efforts to minimize disruptions where practical.
              </p>
            </section>

            {/* 11. Intellectual Property */}
            <section
              id="intellectual-property"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-4 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-sm border border-indigo-100">
                  11
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  11. Intellectual Property
                </h2>
              </div>

              <p>
                The AI Drive Assistant application, including its software, interface, design, branding, and original materials, is protected by applicable intellectual property laws.
              </p>
              <p className="text-xs text-slate-600">
                Except for content you own or have permission to use, you may not copy, distribute, modify, or commercially exploit protected application materials without appropriate authorization.
              </p>
            </section>

            {/* 12. Disclaimer of Warranties */}
            <section
              id="disclaimer"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-4 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center font-bold text-sm border border-amber-100">
                  12
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  12. Disclaimer of Warranties
                </h2>
              </div>

              <p className="font-semibold text-slate-900">
                AI Drive Assistant is provided on an &ldquo;AS IS&rdquo; and &ldquo;AS AVAILABLE&rdquo; basis, to the extent permitted by applicable law.
              </p>
              <p>We make no warranties, express or implied, regarding:</p>
              <ul className="list-disc list-inside space-y-1 text-xs text-slate-700 ml-1">
                <li>Accuracy or reliability of AI-generated responses.</li>
                <li>Continuous availability of the Service.</li>
                <li>Compatibility with every document format.</li>
                <li>Error-free operation or uninterrupted access.</li>
                <li>Suitability of the Service for a particular purpose.</li>
              </ul>
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/70 text-xs text-slate-700 font-semibold">
                You use the Service at your own discretion and risk.
              </div>
            </section>

            {/* 13. Limitation of Liability */}
            <section
              id="liability"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-4 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center font-bold text-sm border border-rose-100">
                  13
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  13. Limitation of Liability
                </h2>
              </div>

              <p>
                To the maximum extent permitted by applicable law, AI Drive Assistant and its operators shall not be liable for indirect, incidental, special, consequential, or punitive damages arising from:
              </p>
              <ul className="list-disc list-inside space-y-1 text-xs text-slate-700 ml-1">
                <li>Your use or inability to use the Service.</li>
                <li>Reliance on AI-generated responses.</li>
                <li>Loss of data or service interruptions.</li>
                <li>Unauthorized access resulting from circumstances beyond our reasonable control.</li>
                <li>Third-party services or integrations.</li>
              </ul>
              <p className="text-xs text-slate-600">
                Nothing in these Terms excludes liability that cannot legally be excluded under applicable law.
              </p>
            </section>

            {/* 14. Suspension and Termination */}
            <section
              id="termination"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-4 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-sm border border-indigo-100">
                  14
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  14. Suspension and Termination
                </h2>
              </div>

              <p>We may suspend or terminate your access to AI Drive Assistant if:</p>
              <ul className="list-disc list-inside space-y-1 text-xs text-slate-700 ml-1">
                <li>You violate these Terms.</li>
                <li>Your use creates security or operational risks.</li>
                <li>Your activities violate applicable laws.</li>
                <li>Suspension is necessary to protect the Service or its users.</li>
              </ul>
              <p className="text-xs text-slate-600">
                You may stop using the Service at any time.
              </p>
              <p className="text-xs text-slate-600">
                Termination does not automatically mean that every record associated with your account is immediately deleted. Data handling following termination is governed by our Privacy Policy and applicable requirements.
              </p>
            </section>

            {/* 15. Changes to These Terms */}
            <section
              id="changes"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-4 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-sm border border-indigo-100">
                  15
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  15. Changes to These Terms
                </h2>
              </div>

              <p>
                We may update these Terms from time to time to reflect changes in our application, services, legal obligations, or business practices.
              </p>
              <p className="text-xs text-slate-600">
                Updated Terms will be published on this page with a revised effective date.
              </p>
              <p className="text-xs text-slate-600">
                Your continued use of the Service after updated Terms become effective constitutes acceptance of the revised Terms, to the extent permitted by applicable law.
              </p>
            </section>

            {/* 16. Governing Law */}
            <section
              id="governing-law"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-4 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-sm border border-indigo-100">
                  16
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  16. Governing Law
                </h2>
              </div>

              <p>
                These Terms shall be interpreted in accordance with the applicable laws of the jurisdiction in which the Service operator is legally established, without disregarding any mandatory consumer protections that apply to you.
              </p>
            </section>

            {/* 17. Contact Information */}
            <section
              id="contact"
              className="p-6 sm:p-7 rounded-3xl bg-white border-2 border-indigo-200/80 shadow-xs space-y-5 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-indigo-600 text-white flex items-center justify-center font-bold text-sm">
                  17
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  17. Contact Information
                </h2>
              </div>

              <p className="text-xs sm:text-sm">
                If you have questions about these Terms, account deletion, or the operation of AI Drive Assistant, contact us:
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                <div className="p-4 rounded-2xl bg-indigo-50/70 border border-indigo-200/80 space-y-1">
                  <div className="flex items-center gap-2 text-xs font-bold text-indigo-900">
                    <Mail size={16} className="text-indigo-600" />
                    <span>Email Inquiries</span>
                  </div>
                  <a
                    href="mailto:daralc19@gmail.com"
                    className="text-xs text-indigo-700 hover:text-indigo-900 font-semibold hover:underline block pt-1"
                  >
                    daralc19@gmail.com
                  </a>
                </div>

                <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80 space-y-1">
                  <div className="flex items-center gap-2 text-xs font-bold text-slate-900">
                    <Globe size={16} className="text-indigo-600" />
                    <span>Application & Website</span>
                  </div>
                  <p className="text-xs text-slate-600">
                    AI Drive Assistant
                  </p>
                  <a
                    href="https://ai-drive-assistant.duckdns.org"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-blue-600 hover:underline font-semibold flex items-center gap-1 pt-0.5"
                  >
                    <span>ai-drive-assistant.duckdns.org</span>
                    <ExternalLink size={12} />
                  </a>
                </div>
              </div>

              <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-600">
                By using AI Drive Assistant, you acknowledge that you have read and agree to these Terms of Service.
              </div>
            </section>
          </article>
        </div>
      </main>

      {/* ── FOOTER ── */}
      <footer className="mt-16 border-t border-slate-200 bg-white py-8">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-500">
          <p>© {new Date().getFullYear()} AI Drive Assistant. All rights reserved.</p>
          <div className="flex items-center gap-4">
            <Link href="/" className="hover:text-blue-600 transition-colors">
              Home
            </Link>
            <span>•</span>
            <Link href="/privacy-policy" className="hover:text-blue-600 transition-colors">
              Privacy Policy
            </Link>
            <span>•</span>
            <Link href="/terms-of-service" className="text-blue-600 font-semibold">
              Terms of Service
            </Link>
            <span>•</span>
            <a
              href="mailto:daralc19@gmail.com"
              className="hover:text-blue-600 transition-colors"
            >
              Contact
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}

