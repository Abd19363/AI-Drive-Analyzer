import Link from "next/link";
import {
  ShieldCheck,
  ArrowLeft,
  Lock,
  Database,
  ExternalLink,
  Mail,
  Globe,
  FileText,
  Server,
  Cpu,
  UserX,
  Clock,
  EyeOff,
  AlertCircle,
  HelpCircle,
  CheckCircle2,
} from "lucide-react";

export const metadata = {
  title: "Privacy Policy | AI Drive Assistant",
  description:
    "Official Privacy Policy for AI Drive Assistant. Learn how we collect, use, store, and protect your data, Google Drive integration, and AI security guardrails.",
};

const sections = [
  { id: "introduction", title: "1. Introduction" },
  { id: "information-we-collect", title: "2. Information We Collect" },
  { id: "how-we-use-information", title: "3. How We Use Information" },
  { id: "google-drive-access", title: "4. Google Drive Access & Permissions" },
  { id: "ai-and-third-party", title: "5. AI & Third-Party Services" },
  { id: "data-storage-security", title: "6. Data Storage & Security" },
  { id: "data-retention", title: "7. Data Retention" },
  { id: "disconnecting-drive", title: "8. Disconnecting Google Drive" },
  { id: "account-deletion", title: "9. Account & Data Deletion" },
  { id: "information-sharing", title: "10. Information Sharing" },
  { id: "childrens-privacy", title: "11. Children's Privacy" },
  { id: "changes-to-policy", title: "12. Changes to This Policy" },
  { id: "contact-us", title: "13. Contact Us" },
];

export default function PrivacyPolicyPage() {
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
              <ShieldCheck size={20} />
            </div>
            <div>
              <span className="font-heading font-bold text-slate-900 text-base tracking-tight block leading-tight">
                AI Drive Assistant
              </span>
              <span className="text-[10px] text-slate-500 font-medium tracking-wide uppercase">
                Privacy & Data Governance
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
      <div className="bg-gradient-to-b from-white via-blue-50/20 to-[#f8fafc] border-b border-slate-200/70 pt-12 pb-10">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200/80 text-emerald-800 text-[11px] font-semibold mb-4 shadow-2xs">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            Official Application Policy • Google API Services Compliant
          </div>

          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-slate-900 tracking-tight font-heading mb-3">
            Privacy Policy
          </h1>

          <p className="text-sm sm:text-base text-slate-600 max-w-3xl leading-relaxed">
            This Privacy Policy explains how <strong>AI Drive Assistant</strong> collects, uses, stores, and protects your information, detailing our read-only Google Drive access, artificial intelligence processing, and zero-compromise security controls.
          </p>

          <div className="mt-5 flex flex-wrap items-center gap-4 text-xs text-slate-500 pt-3 border-t border-slate-200/60">
            <div className="flex items-center gap-1.5 font-medium text-slate-700">
              <Clock size={14} className="text-blue-600" />
              <span>Last Updated: <strong>November 8, 2026</strong></span>
            </div>
            <span>•</span>
            <div className="flex items-center gap-1.5">
              <Globe size={14} className="text-slate-400" />
              <span>Scope: Public Web Application</span>
            </div>
            <span>•</span>
            <div className="flex items-center gap-1.5">
              <ShieldCheck size={14} className="text-emerald-600" />
              <span>Read-Only Drive Permissions</span>
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
                <FileText size={15} className="text-blue-600" />
                <span>Table of Contents</span>
              </div>

              <nav className="space-y-1 text-xs">
                {sections.map((section) => (
                  <a
                    key={section.id}
                    href={`#${section.id}`}
                    className="block px-2.5 py-1.5 rounded-lg text-slate-600 hover:text-blue-700 hover:bg-blue-50/70 font-medium transition-colors"
                  >
                    {section.title}
                  </a>
                ))}
              </nav>

              <div className="pt-3 border-t border-slate-100 text-[11px] text-slate-500 space-y-1">
                <p className="font-semibold text-slate-700">Need Assistance?</p>
                <p>
                  Contact our data privacy administrator at{" "}
                  <a
                    href="mailto:daralc19@gmail.com"
                    className="text-blue-600 hover:underline font-medium break-all"
                  >
                    daralc19@gmail.com
                  </a>
                </p>
              </div>
            </div>
          </aside>

          {/* POLICY CONTENT BODY */}
          <article className="lg:col-span-8 space-y-8 text-slate-700 leading-relaxed text-sm">
            {/* 1. Introduction */}
            <section
              id="introduction"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-4 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold text-sm border border-blue-100">
                  1
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  1. Introduction
                </h2>
              </div>

              <p>
                Welcome to <strong>AI Drive Assistant</strong> (&ldquo;we&rdquo;, &ldquo;our&rdquo;, or &ldquo;the Application&rdquo;).
              </p>
              <p>
                AI Drive Assistant is an AI-powered document analysis and question-answering application that allows users to connect their Google Drive accounts, process documents, and retrieve information using artificial intelligence.
              </p>
              <p>
                This Privacy Policy explains what information we collect, how we use and store it, when information is shared with third-party services, and what choices users have regarding their data.
              </p>
              <p className="font-medium text-slate-900 bg-slate-50 p-3.5 rounded-xl border border-slate-200/60">
                By using AI Drive Assistant, you acknowledge the practices described in this Privacy Policy.
              </p>
            </section>

            {/* 2. Information We Collect */}
            <section
              id="information-we-collect"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-5 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold text-sm border border-blue-100">
                  2
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  2. Information We Collect
                </h2>
              </div>

              <p>We may collect and process the following categories of information:</p>

              {/* 2.1 */}
              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/70 space-y-2">
                <h3 className="font-bold text-slate-900 text-sm font-heading flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-blue-600" />
                  2.1 Google Account Information
                </h3>
                <p className="text-xs text-slate-600">When you sign in using Google, we may receive:</p>
                <ul className="list-disc list-inside space-y-1 text-xs text-slate-700 ml-1">
                  <li>Your Google account email address.</li>
                  <li>Your name and basic profile information.</li>
                  <li>Your Google account identifier.</li>
                  <li>OAuth authentication credentials, including access tokens and refresh tokens.</li>
                </ul>
                <p className="text-xs text-slate-600 pt-1">
                  We use this information to authenticate users and maintain their Google Drive connection.
                </p>
              </div>

              {/* 2.2 */}
              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/70 space-y-2">
                <h3 className="font-bold text-slate-900 text-sm font-heading flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-600" />
                  2.2 Google Drive Information
                </h3>
                <p className="text-xs text-slate-600">
                  When you connect Google Drive, the Application uses Google&apos;s read-only Drive access permission to:
                </p>
                <ul className="list-disc list-inside space-y-1 text-xs text-slate-700 ml-1">
                  <li>Retrieve document names, file IDs, MIME types, file sizes, and modification dates.</li>
                  <li>Access document content selected for processing.</li>
                  <li>Extract text and relevant information from supported documents.</li>
                  <li>Generate searchable document representations for question answering.</li>
                </ul>
                <div className="p-3 bg-emerald-50/80 rounded-xl border border-emerald-200/70 text-xs text-emerald-900 font-semibold flex items-center gap-2">
                  <CheckCircle2 size={16} className="text-emerald-600 flex-shrink-0" />
                  <span>The Application does not use its Google Drive permission to modify or delete users&apos; original Google Drive files.</span>
                </div>
              </div>

              {/* 2.3 */}
              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/70 space-y-2">
                <h3 className="font-bold text-slate-900 text-sm font-heading flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-indigo-600" />
                  2.3 Document and Extracted Content
                </h3>
                <p className="text-xs text-slate-600">
                  Documents processed through the Application may be downloaded temporarily for processing.
                </p>
                <p className="text-xs text-slate-600">
                  Depending on the document format, we may extract text using document-processing libraries and optical character recognition (OCR).
                </p>
                <p className="text-xs text-slate-600">
                  Extracted document text may be divided into smaller sections (chunks), converted into numerical embeddings, and stored in our database to support semantic search and retrieval.
                </p>
                <p className="text-xs text-slate-600">
                  We may also store document metadata, processing status, document references, and security classification results.
                </p>
              </div>

              {/* 2.4 */}
              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/70 space-y-2">
                <h3 className="font-bold text-slate-900 text-sm font-heading flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-purple-600" />
                  2.4 Chat and Usage Information
                </h3>
                <p className="text-xs text-slate-600">
                  When users interact with the Application, we may process and store:
                </p>
                <ul className="list-disc list-inside space-y-1 text-xs text-slate-700 ml-1">
                  <li>Questions and queries submitted by users.</li>
                  <li>AI-generated answers.</li>
                  <li>Referenced document names and identifiers.</li>
                  <li>Chat session information.</li>
                  <li>Technical usage information, including processing time and token usage.</li>
                  <li>Cache entries used to improve response speed.</li>
                </ul>
              </div>

              {/* 2.5 */}
              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/70 space-y-2">
                <h3 className="font-bold text-slate-900 text-sm font-heading flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-slate-600" />
                  2.5 Account Information
                </h3>
                <p className="text-xs text-slate-600">
                  We may maintain account-related information such as email address, name, authentication-related information, account timestamps, and application usage or subscription-related records.
                </p>
              </div>
            </section>

            {/* 3. How We Use Information */}
            <section
              id="how-we-use-information"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-4 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold text-sm border border-blue-100">
                  3
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  3. How We Use Information
                </h2>
              </div>

              <p>We use collected information for the following purposes:</p>
              <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-xs">
                {[
                  "To authenticate users and manage their accounts.",
                  "To connect to Google Drive with user authorization.",
                  "To retrieve and process documents requested by users.",
                  "To generate document embeddings and enable semantic search.",
                  "To provide AI-powered answers based on users' documents.",
                  "To identify potentially confidential or sensitive document content through security guardrails.",
                  "To maintain chat history and improve application performance.",
                  "To manage application usage, troubleshoot errors, and maintain service security.",
                  "To enforce account and subscription-related restrictions where applicable.",
                ].map((purpose, idx) => (
                  <li
                    key={idx}
                    className="p-3 rounded-xl bg-slate-50 border border-slate-200/70 text-slate-700 flex items-start gap-2"
                  >
                    <CheckCircle2 size={15} className="text-blue-600 mt-0.5 flex-shrink-0" />
                    <span>{purpose}</span>
                  </li>
                ))}
              </ul>

              <div className="p-3.5 bg-blue-50/70 rounded-xl border border-blue-200/70 text-xs text-blue-900 font-semibold">
                We do not use Google Drive information for purposes unrelated to providing the Application&apos;s functionality.
              </div>
            </section>

            {/* 4. Google Drive Access and Permissions */}
            <section
              id="google-drive-access"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-4 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold text-sm border border-blue-100">
                  4
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  4. Google Drive Access and Permissions
                </h2>
              </div>

              <p>
                AI Drive Assistant uses <strong>Google OAuth 2.0</strong> to allow users to connect their Google accounts.
              </p>
              <p>
                The Application requests <strong>read-only Google Drive access</strong> to retrieve and process documents.
              </p>
              <p>
                Google authentication credentials are stored in the Application&apos;s database to maintain authorized connections and support access-token renewal.
              </p>
              <p>
                Users can disconnect Google Drive through the Application. Disconnecting removes the stored Google OAuth credentials and associated cached answers. It does not automatically delete the user&apos;s AI Drive Assistant account or all previously indexed document information.
              </p>
              <p>
                Users can also revoke the Application&apos;s access through their Google Account security settings.
              </p>

              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between text-xs">
                <span>Google&apos;s privacy policy is available at:</span>
                <a
                  href="https://policies.google.com/privacy"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-blue-600 font-semibold hover:underline"
                >
                  <span>Google Privacy Policy</span>
                  <ExternalLink size={13} />
                </a>
              </div>
            </section>

            {/* 5. Artificial Intelligence and Third-Party Services */}
            <section
              id="ai-and-third-party"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-5 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold text-sm border border-blue-100">
                  5
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  5. Artificial Intelligence and Third-Party Services
                </h2>
              </div>

              <p>AI Drive Assistant uses third-party services to operate its functionality.</p>

              {/* 5.1 */}
              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/70 space-y-2">
                <h3 className="font-bold text-slate-900 text-sm font-heading flex items-center gap-2">
                  <Cpu size={16} className="text-blue-600" />
                  5.1 Google Gemini API
                </h3>
                <p className="text-xs text-slate-600">
                  The Application uses Google&apos;s Gemini API to support AI-powered document analysis, content understanding, and question answering.
                </p>
                <p className="text-xs text-slate-600">
                  Depending on the operation, relevant document text, extracted content, document excerpts, and user queries may be transmitted to Google&apos;s AI services for processing.
                </p>
              </div>

              {/* 5.2 */}
              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/70 space-y-2">
                <h3 className="font-bold text-slate-900 text-sm font-heading flex items-center gap-2">
                  <Database size={16} className="text-indigo-600" />
                  5.2 Local Embedding Processing
                </h3>
                <p className="text-xs text-slate-600">
                  The Application uses a locally executed sentence-embedding model to convert extracted document text into numerical representations for semantic search.
                </p>
                <p className="text-xs text-slate-600">
                  These embeddings and associated document chunks are stored in the Application&apos;s database.
                </p>
              </div>

              {/* 5.3 */}
              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/70 space-y-2">
                <h3 className="font-bold text-slate-900 text-sm font-heading flex items-center gap-2">
                  <Server size={16} className="text-amber-600" />
                  5.3 AWS Infrastructure
                </h3>
                <p className="text-xs text-slate-600">
                  The Application uses Amazon Web Services (AWS) infrastructure for application hosting and database services.
                </p>
                <p className="text-xs text-slate-600">
                  Information processed by the Application may therefore be stored on AWS infrastructure used to operate the service.
                </p>
              </div>

              <p className="text-xs text-slate-500 italic">
                Third-party services process information according to their respective terms and privacy policies.
              </p>
            </section>

            {/* 6. Data Storage and Security */}
            <section
              id="data-storage-security"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-4 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold text-sm border border-blue-100">
                  6
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  6. Data Storage and Security
                </h2>
              </div>

              <p>
                We use technical and organizational measures intended to protect user information against unauthorized access, disclosure, alteration, and destruction.
              </p>
              <p>These measures include:</p>
              <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                {[
                  "Authenticated access to application functionality.",
                  "Restricted database access.",
                  "Server-side processing of authentication credentials.",
                  "Environment-based configuration for sensitive application settings.",
                  "Access-control mechanisms and application security checks.",
                  "Confidentiality guardrails for document processing.",
                ].map((item, idx) => (
                  <li
                    key={idx}
                    className="p-3 rounded-xl bg-slate-50 border border-slate-200/70 text-slate-700 flex items-start gap-2"
                  >
                    <Lock size={14} className="text-emerald-600 mt-0.5 flex-shrink-0" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
              <p className="text-xs text-slate-500">
                Although we take reasonable steps to protect information, no internet-based service or storage system can guarantee absolute security.
              </p>
            </section>

            {/* 7. Data Retention */}
            <section
              id="data-retention"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-4 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold text-sm border border-blue-100">
                  7
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  7. Data Retention
                </h2>
              </div>

              <p>
                We retain information for as long as reasonably necessary to provide the Application&apos;s services, maintain user accounts, support application functionality, and meet applicable operational or legal requirements.
              </p>
              <p>This may include:</p>
              <ul className="list-disc list-inside space-y-1 text-xs text-slate-700 ml-1">
                <li>Account and authentication information.</li>
                <li>Google Drive connection information while the connection remains active.</li>
                <li>Document metadata, extracted text, and embeddings.</li>
                <li>Chat sessions and query records.</li>
                <li>Technical usage and telemetry records.</li>
                <li>Cached answers and related information.</li>
              </ul>
              <p className="text-xs text-slate-600">
                Cached answers have configured expiration periods. Expired cache entries are excluded from normal retrieval and are removed during subsequent cache-storage operations. Physical removal may therefore not occur immediately upon expiration.
              </p>
              <p className="text-xs text-slate-600">
                We do not currently promise a fixed deletion period for every category of stored information.
              </p>
            </section>

            {/* 8. Disconnecting Google Drive */}
            <section
              id="disconnecting-drive"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-4 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold text-sm border border-blue-100">
                  8
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  8. Disconnecting Google Drive
                </h2>
              </div>

              <p>Users may disconnect their Google Drive accounts through the Application.</p>
              <p>When Google Drive is disconnected:</p>
              <ul className="list-disc list-inside space-y-1 text-xs text-slate-700 ml-1">
                <li>Stored Google OAuth credentials are removed.</li>
                <li>Associated cached answers are deleted.</li>
                <li>The AI Drive Assistant user account remains available.</li>
              </ul>
              <p className="text-xs text-slate-600 bg-amber-50/70 p-3 rounded-xl border border-amber-200/70 text-amber-900">
                Previously indexed document information may remain stored after disconnection. Disconnecting Google Drive should not be treated as a request to delete all previously processed information.
              </p>
            </section>

            {/* 9. Account and Data Deletion */}
            <section
              id="account-deletion"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-4 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold text-sm border border-blue-100">
                  9
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  9. Account and Data Deletion
                </h2>
              </div>

              <p>
                Users who wish to delete their account or request deletion of associated information may contact us using the contact details provided at the end of this policy.
              </p>
              <p>Account deletion is currently handled through an authorized administrator.</p>
              <p>The account deletion functionality is designed to remove the user&apos;s account and associated records, including:</p>
              <ul className="list-disc list-inside space-y-1 text-xs text-slate-700 ml-1">
                <li>Connected Google account records.</li>
                <li>Indexed Drive file records.</li>
                <li>Document chunks and embeddings.</li>
                <li>Chat sessions and associated queries.</li>
                <li>Related telemetry records.</li>
                <li>Cached answers.</li>
                <li>Associated secondary administrator records, where applicable.</li>
              </ul>
              <p className="text-xs text-slate-600">
                Deletion of an account does not delete the original files stored in the user&apos;s Google Drive.
              </p>
              <p className="text-xs text-slate-600">
                Users may also revoke Google Drive access independently through their Google Account settings.
              </p>
            </section>

            {/* 10. Information Sharing */}
            <section
              id="information-sharing"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-4 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold text-sm border border-blue-100">
                  10
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  10. Information Sharing
                </h2>
              </div>

              <div className="p-3.5 bg-emerald-50/80 rounded-xl border border-emerald-200/70 text-xs text-emerald-900 font-bold flex items-center gap-2">
                <CheckCircle2 size={16} className="text-emerald-600 flex-shrink-0" />
                <span>We do not sell users&apos; personal information.</span>
              </div>

              <p>
                Information may be transmitted to or processed by third-party providers when necessary to provide the Application&apos;s functionality, including:
              </p>
              <ul className="list-disc list-inside space-y-1 text-xs text-slate-700 ml-1">
                <li>Google APIs for authentication and Google Drive access.</li>
                <li>Google Gemini API for AI-powered processing.</li>
                <li>Amazon Web Services for hosting and database infrastructure.</li>
              </ul>
              <p className="text-xs text-slate-600">
                We may also disclose information where required by applicable law or to protect the security and integrity of the Application.
              </p>
            </section>

            {/* 11. Children's Privacy */}
            <section
              id="childrens-privacy"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-4 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold text-sm border border-blue-100">
                  11
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  11. Children&apos;s Privacy
                </h2>
              </div>

              <p>AI Drive Assistant is not intended for children under the age of 13.</p>
              <p className="text-xs text-slate-600">
                We do not knowingly collect personal information from children under 13. If we become aware that such information has been collected, we will take reasonable steps to address it.
              </p>
            </section>

            {/* 12. Changes to This Privacy Policy */}
            <section
              id="changes-to-policy"
              className="p-6 sm:p-7 rounded-3xl bg-white border border-slate-200/80 shadow-xs space-y-4 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold text-sm border border-blue-100">
                  12
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  12. Changes to This Privacy Policy
                </h2>
              </div>

              <p>
                We may update this Privacy Policy when our application functionality, data practices, or legal requirements change.
              </p>
              <p className="text-xs text-slate-600">
                Updated versions will be published on this page with a revised &ldquo;Last Updated&rdquo; date.
              </p>
              <p className="text-xs text-slate-600">
                Users are encouraged to review this page periodically.
              </p>
            </section>

            {/* 13. Contact Us */}
            <section
              id="contact-us"
              className="p-6 sm:p-7 rounded-3xl bg-white border-2 border-blue-200/80 shadow-xs space-y-5 scroll-mt-24"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-blue-600 text-white flex items-center justify-center font-bold text-sm">
                  13
                </div>
                <h2 className="text-lg sm:text-xl font-bold text-slate-900 font-heading">
                  13. Contact Us
                </h2>
              </div>

              <p className="text-xs sm:text-sm">
                For questions about this Privacy Policy, Google Drive access, personal information, or account and data deletion requests, contact:
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                <div className="p-4 rounded-2xl bg-blue-50/70 border border-blue-200/80 space-y-1">
                  <div className="flex items-center gap-2 text-xs font-bold text-blue-900">
                    <Mail size={16} className="text-blue-600" />
                    <span>Email Inquiries</span>
                  </div>
                  <a
                    href="mailto:daralc19@gmail.com"
                    className="text-xs text-blue-700 hover:text-blue-900 font-semibold hover:underline block pt-1"
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
            <Link href="/privacy-policy" className="text-blue-600 font-semibold">
              Privacy Policy
            </Link>
            <span>•</span>
            <Link href="/terms-of-service" className="hover:text-blue-600 transition-colors">
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

