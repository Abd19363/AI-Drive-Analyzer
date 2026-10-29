"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, Copy } from "lucide-react";

function CodeBlock({ children, className }) {
  const [copied, setCopied] = useState(false);
  const codeString = String(children).replace(/\n$/, "");

  const handleCopy = () => {
    navigator.clipboard.writeText(codeString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group my-3 rounded-xl overflow-hidden border border-slate-700/60 bg-slate-900 shadow-sm">
      <div className="flex items-center justify-between px-3.5 py-1.5 bg-slate-800/80 border-b border-slate-700/60 text-[10px] text-slate-400 font-mono">
        <span>{className ? className.replace("language-", "") : "code"}</span>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1 text-slate-400 hover:text-white transition-colors"
          title="Copy code"
        >
          {copied ? (
            <>
              <Check size={11} className="text-emerald-400" />
              <span className="text-emerald-400">Copied</span>
            </>
          ) : (
            <>
              <Copy size={11} />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="p-3.5 overflow-x-auto text-xs text-slate-100 font-mono leading-relaxed">
        <code>{codeString}</code>
      </pre>
    </div>
  );
}

export default function MarkdownRenderer({ content }) {
  if (!content) return null;

  // Clean up any rogue orphan asterisks or weird standalone markup artifacts
  const normalizedContent = content
    .replace(/^(\s*)\*\*(\s*)$/gm, "")
    .replace(/\n{3,}/g, "\n\n");

  return (
    <div className="markdown-body text-xs text-slate-700 leading-relaxed space-y-2.5">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="text-sm font-bold text-slate-900 mt-4 mb-2 pb-1 border-b border-slate-100 first:mt-0 font-heading">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-[13px] font-bold text-slate-900 mt-3.5 mb-1.5 pb-0.5 first:mt-0 font-heading">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-xs font-bold text-slate-800 mt-3 mb-1 first:mt-0 font-heading">
              {children}
            </h3>
          ),
          h4: ({ children }) => (
            <h4 className="text-xs font-semibold text-slate-800 mt-2 mb-1 first:mt-0 font-heading">
              {children}
            </h4>
          ),
          p: ({ children }) => (
            <p className="leading-relaxed mb-2 last:mb-0 text-slate-700">
              {children}
            </p>
          ),
          strong: ({ children }) => (
            <strong className="font-semibold text-slate-900">
              {children}
            </strong>
          ),
          em: ({ children }) => (
            <em className="italic text-slate-600">
              {children}
            </em>
          ),
          ul: ({ children }) => (
            <ul className="list-disc list-outside pl-4 space-y-1 mb-2.5 text-slate-700">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal list-outside pl-4 space-y-1 mb-2.5 text-slate-700">
              {children}
            </ol>
          ),
          li: ({ children }) => (
            <li className="leading-relaxed pl-1 marker:text-slate-400">
              {children}
            </li>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-blue-500 pl-3 my-2.5 italic text-slate-600 bg-blue-50/30 py-1 rounded-r-lg">
              {children}
            </blockquote>
          ),
          hr: () => <hr className="my-3 border-slate-200" />,
          table: ({ children }) => (
            <div className="overflow-x-auto my-3 rounded-xl border border-slate-200 shadow-2xs">
              <table className="min-w-full text-xs text-left divide-y divide-slate-200">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-slate-50/90 text-slate-800 font-semibold border-b border-slate-200">
              {children}
            </thead>
          ),
          tbody: ({ children }) => (
            <tbody className="divide-y divide-slate-100 bg-white">
              {children}
            </tbody>
          ),
          th: ({ children }) => (
            <th className="px-3.5 py-2 text-[11px] font-semibold text-slate-800">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="px-3.5 py-2 text-[11px] text-slate-700">
              {children}
            </td>
          ),
          code: ({ className, children, ...props }) => {
            const isBlock = /language-(\w+)/.test(className || "");
            if (!isBlock) {
              return (
                <code
                  className="px-1.5 py-0.5 rounded-md bg-slate-100 text-blue-700 font-mono text-[11px] border border-slate-200/80 font-medium"
                  {...props}
                >
                  {children}
                </code>
              );
            }
            return <CodeBlock className={className}>{children}</CodeBlock>;
          },
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:text-blue-700 underline font-medium"
            >
              {children}
            </a>
          ),
        }}
      >
        {normalizedContent}
      </ReactMarkdown>
    </div>
  );
}
