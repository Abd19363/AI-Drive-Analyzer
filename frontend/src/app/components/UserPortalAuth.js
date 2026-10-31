"use client";

import { useState } from "react";
import {
  Lock,
  Mail,
  User,
  ArrowRight,
  KeyRound,
  ShieldCheck,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Eye,
  EyeOff,
  Sparkles,
  HardDrive,
} from "lucide-react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export default function UserPortalAuth({ onAuthenticated }) {
  const [authMode, setAuthMode] = useState("login"); // "login" | "register" | "forgot"
  const [forgotPhase, setForgotPhase] = useState("email"); // "email" | "verify"
  
  // Form fields
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [verificationCode, setVerificationCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  
  // UI states
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  const resetFormState = () => {
    setErrorMsg(null);
    setSuccessMsg(null);
  };

  // ─────────────────────────────────────────────────────────────
  // 1. User Sign In
  // ─────────────────────────────────────────────────────────────
  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    resetFormState();

    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim(),
          password: password.trim(),
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Authentication failed. Please check your credentials.");
      }

      // Save user session in localStorage
      localStorage.setItem("ai_drive_user_id", data.user_id);
      localStorage.setItem("ai_drive_user_email", data.email);
      if (data.token) {
        localStorage.setItem("ai_drive_user_token", data.token);
      }

      if (onAuthenticated) {
        onAuthenticated(data);
      }
    } catch (err) {
      setErrorMsg(err.message || "Failed to sign in. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // ─────────────────────────────────────────────────────────────
  // 2. User Registration
  // ─────────────────────────────────────────────────────────────
  const handleRegister = async (e) => {
    e.preventDefault();
    setLoading(true);
    resetFormState();

    if (password.length < 6) {
      setErrorMsg("Password must be at least 6 characters long.");
      setLoading(false);
      return;
    }

    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim(),
          password: password.trim(),
          full_name: fullName.trim(),
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Registration failed.");
      }

      // Save user session in localStorage
      localStorage.setItem("ai_drive_user_id", data.user_id);
      localStorage.setItem("ai_drive_user_email", data.email);
      if (data.token) {
        localStorage.setItem("ai_drive_user_token", data.token);
      }

      setSuccessMsg("Account successfully created! Signing you in...");
      setTimeout(() => {
        if (onAuthenticated) {
          onAuthenticated(data);
        }
      }, 500);
    } catch (err) {
      setErrorMsg(err.message || "Registration failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // ─────────────────────────────────────────────────────────────
  // 3. Forgot Password - Phase 1: Request Code
  // ─────────────────────────────────────────────────────────────
  const handleRequestVerificationCode = async (e) => {
    e.preventDefault();
    setLoading(true);
    resetFormState();

    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Failed to send reset code.");
      }

      setSuccessMsg(`A 6-digit verification code has been dispatched to ${email.trim()}.`);
      setForgotPhase("verify");
    } catch (err) {
      setErrorMsg(err.message || "Failed to request code. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // ─────────────────────────────────────────────────────────────
  // 4. Forgot Password - Phase 2: Verify & Reset
  // ─────────────────────────────────────────────────────────────
  const handleResetPassword = async (e) => {
    e.preventDefault();
    setLoading(true);
    resetFormState();

    if (newPassword !== confirmPassword) {
      setErrorMsg("New passwords do not match. Please re-enter.");
      setLoading(false);
      return;
    }

    if (newPassword.length < 6) {
      setErrorMsg("Password must be at least 6 characters long.");
      setLoading(false);
      return;
    }

    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim(),
          verification_code: verificationCode.trim(),
          new_password: newPassword.trim(),
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Password reset failed.");
      }

      setSuccessMsg("Password reset successfully! Please sign in with your new password.");
      setAuthMode("login");
      setForgotPhase("email");
      setPassword("");
      setVerificationCode("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setErrorMsg(err.message || "Failed to reset password. Please check your verification code.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-[1440px] mx-auto px-6 py-12 flex flex-col items-center justify-center min-h-[72vh]">
      <div className="w-full max-w-md bg-white border border-slate-200/90 rounded-3xl p-8 shadow-xl shadow-slate-200/50 relative overflow-hidden animate-fade-in">
        {/* Top Header */}
        <div className="flex flex-col items-center text-center mb-6">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-lg shadow-blue-500/25 mb-3.5">
            <HardDrive size={26} className="stroke-[2.2]" />
          </div>
          <h2 className="font-heading text-lg font-bold text-slate-900 tracking-tight flex items-center gap-1.5">
            User Portal Gateway
            <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-600 border border-emerald-200/80">
              <ShieldCheck size={11} className="stroke-[2.5]" />
              PROTECTED
            </span>
          </h2>
          <p className="text-xs text-slate-500 mt-1 max-w-[310px]">
            Password-protected user access for private Google Drive analysis, AI synthesis, and confidential query isolation.
          </p>
        </div>

        {/* Tab Switcher: Sign In vs Create Account (hidden during forgot-password flow) */}
        {authMode !== "forgot" && (
          <div className="flex items-center p-1 bg-slate-100/90 rounded-xl mb-5 border border-slate-200/60">
            <button
              type="button"
              onClick={() => {
                setAuthMode("login");
                resetFormState();
              }}
              className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                authMode === "login"
                  ? "bg-white text-slate-900 shadow-2xs border border-slate-200/50"
                  : "text-slate-500 hover:text-slate-800"
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => {
                setAuthMode("register");
                resetFormState();
              }}
              className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                authMode === "register"
                  ? "bg-white text-slate-900 shadow-2xs border border-slate-200/50"
                  : "text-slate-500 hover:text-slate-800"
              }`}
            >
              Create Account
            </button>
          </div>
        )}

        {/* Notification Feedback Banners */}
        {errorMsg && (
          <div className="mb-4 p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700 flex items-start gap-2 animate-fade-in">
            <AlertCircle size={15} className="flex-shrink-0 mt-0.5 text-rose-600" />
            <span>{errorMsg}</span>
          </div>
        )}

        {successMsg && (
          <div className="mb-4 p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-start gap-2 animate-fade-in">
            <CheckCircle2 size={15} className="flex-shrink-0 mt-0.5 text-emerald-600" />
            <span>{successMsg}</span>
          </div>
        )}

        {/* ─────────────────────────────────────────────────────────────
            MODE 1: USER SIGN IN FORM
           ───────────────────────────────────────────────────────────── */}
        {authMode === "login" && (
          <form onSubmit={handleLogin} className="flex flex-col gap-3.5">
            <div>
              <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                Email Address
              </label>
              <div className="relative">
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="user@example.com"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3.5 py-2 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:border-blue-600 focus:ring-1 focus:ring-blue-100 outline-none transition-all"
                />
                <Mail size={14} className="absolute left-3 top-2.5 text-slate-400" />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-[11px] font-semibold text-slate-700">
                  Password
                </label>
                <button
                  type="button"
                  onClick={() => {
                    setAuthMode("forgot");
                    setForgotPhase("email");
                    resetFormState();
                  }}
                  className="text-[11px] font-medium text-blue-600 hover:text-blue-800 transition-colors"
                >
                  Forgot password?
                </button>
              </div>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-10 py-2 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:border-blue-600 focus:ring-1 focus:ring-blue-100 outline-none transition-all"
                />
                <Lock size={14} className="absolute left-3 top-2.5 text-slate-400" />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600"
                >
                  {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="mt-2 w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 active:scale-[0.99] transition-all disabled:opacity-50 shadow-md shadow-blue-500/20"
            >
              {loading ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <ArrowRight size={14} />
              )}
              {loading ? "Signing in..." : "Sign In to User Portal"}
            </button>

            <div className="mt-3 pt-3 border-t border-slate-100 text-center">
              <p className="text-[11px] text-slate-400">
                New user?{" "}
                <button
                  type="button"
                  onClick={() => {
                    setAuthMode("register");
                    resetFormState();
                  }}
                  className="text-blue-600 font-semibold hover:underline"
                >
                  Create an account
                </button>
              </p>
            </div>
          </form>
        )}

        {/* ─────────────────────────────────────────────────────────────
            MODE 2: CREATE ACCOUNT FORM
           ───────────────────────────────────────────────────────────── */}
        {authMode === "register" && (
          <form onSubmit={handleRegister} className="flex flex-col gap-3.5">
            <div>
              <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                Full Name
              </label>
              <div className="relative">
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Jane Doe"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3.5 py-2 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:border-blue-600 focus:ring-1 focus:ring-blue-100 outline-none transition-all"
                />
                <User size={14} className="absolute left-3 top-2.5 text-slate-400" />
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                Email Address
              </label>
              <div className="relative">
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="user@example.com"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3.5 py-2 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:border-blue-600 focus:ring-1 focus:ring-blue-100 outline-none transition-all"
                />
                <Mail size={14} className="absolute left-3 top-2.5 text-slate-400" />
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                Password <span className="text-slate-400 font-normal">(min 6 characters)</span>
              </label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-10 py-2 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:border-blue-600 focus:ring-1 focus:ring-blue-100 outline-none transition-all"
                />
                <Lock size={14} className="absolute left-3 top-2.5 text-slate-400" />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600"
                >
                  {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="mt-2 w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 active:scale-[0.99] transition-all disabled:opacity-50 shadow-md shadow-blue-500/20"
            >
              {loading ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Sparkles size={14} />
              )}
              {loading ? "Creating Account..." : "Create Account & Sign In"}
            </button>

            <div className="mt-3 pt-3 border-t border-slate-100 text-center">
              <p className="text-[11px] text-slate-400">
                Already registered?{" "}
                <button
                  type="button"
                  onClick={() => {
                    setAuthMode("login");
                    resetFormState();
                  }}
                  className="text-blue-600 font-semibold hover:underline"
                >
                  Sign in
                </button>
              </p>
            </div>
          </form>
        )}

        {/* ─────────────────────────────────────────────────────────────
            MODE 3: FORGOT PASSWORD FLOW
           ───────────────────────────────────────────────────────────── */}
        {authMode === "forgot" && (
          <div className="flex flex-col gap-3.5">
            <div className="flex items-center gap-2 pb-1 border-b border-slate-100">
              <KeyRound size={15} className="text-blue-600" />
              <h3 className="text-xs font-bold text-slate-900">
                {forgotPhase === "email" ? "Reset Your Password" : "Enter Verification Code"}
              </h3>
            </div>

            {forgotPhase === "email" ? (
              <form onSubmit={handleRequestVerificationCode} className="flex flex-col gap-3">
                <p className="text-[11px] text-slate-500">
                  Enter your registered email address. We will send a secure 6-digit verification code to update your password.
                </p>

                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                    Registered Email
                  </label>
                  <div className="relative">
                    <input
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="user@example.com"
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3.5 py-2 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:border-blue-600 focus:ring-1 focus:ring-blue-100 outline-none transition-all"
                    />
                    <Mail size={14} className="absolute left-3 top-2.5 text-slate-400" />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="mt-1 w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 transition-all disabled:opacity-50 shadow-md shadow-blue-500/20"
                >
                  {loading ? <Loader2 size={14} className="animate-spin" /> : <KeyRound size={14} />}
                  {loading ? "Sending Code..." : "Send Verification Code"}
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setAuthMode("login");
                    resetFormState();
                  }}
                  className="text-[11px] text-slate-500 hover:text-slate-800 text-center mt-1"
                >
                  Back to Sign In
                </button>
              </form>
            ) : (
              <form onSubmit={handleResetPassword} className="flex flex-col gap-3">
                <p className="text-[11px] text-slate-500">
                  Enter the 6-digit verification code sent to <strong className="text-slate-800">{email}</strong> and set your new password.
                </p>

                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                    6-Digit Verification Code
                  </label>
                  <input
                    type="text"
                    required
                    maxLength={6}
                    value={verificationCode}
                    onChange={(e) => setVerificationCode(e.target.value)}
                    placeholder="123456"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2 text-center text-sm font-mono tracking-widest font-bold text-blue-900 placeholder-slate-400 focus:bg-white focus:border-blue-600 outline-none transition-all"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                    New Password
                  </label>
                  <input
                    type="password"
                    required
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:border-blue-600 outline-none transition-all"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                    Confirm New Password
                  </label>
                  <input
                    type="password"
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:border-blue-600 outline-none transition-all"
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="mt-1 w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 transition-all disabled:opacity-50 shadow-md shadow-emerald-600/20"
                >
                  {loading ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
                  {loading ? "Updating Password..." : "Update Password & Sign In"}
                </button>

                <div className="flex items-center justify-between text-[11px] mt-1 text-slate-500">
                  <button
                    type="button"
                    onClick={() => setForgotPhase("email")}
                    className="hover:underline"
                  >
                    Resend Code
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setAuthMode("login");
                      resetFormState();
                    }}
                    className="hover:underline text-blue-600 font-medium"
                  >
                    Back to Sign In
                  </button>
                </div>
              </form>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
