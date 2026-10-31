"use client";

import { useState, useEffect } from "react";
import {
  Shield,
  ShieldCheck,
  ShieldAlert,
  Cpu,
  Activity,
  Zap,
  CheckCircle2,
  AlertCircle,
  X,
  LogOut,
  Check,
  RefreshCw,
  Clock,
  Database,
  FileText,
  Lock,
  User,
  UserPlus,
  Users,
  ArrowRight,
  Loader2,
  Search,
  Sparkles,
  KeyRound,
  Mail,
} from "lucide-react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export default function AdminPortal() {
  const [adminToken, setAdminToken] = useState(null);
  const [adminProfile, setAdminProfile] = useState(null);
  const [selectedRole, setSelectedRole] = useState("LEAD_ADMIN"); // "LEAD_ADMIN" | "USER_ADMIN"
  const [authMode, setAuthMode] = useState("login"); // "login" | "register" | "forgot"
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState(null);
  const [authSuccess, setAuthSuccess] = useState(null);

  // Setup status
  const [setupStatus, setSetupStatus] = useState(null);

  // Form states
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [regFullName, setRegFullName] = useState("");
  const [regEmail, setRegEmail] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regNote, setRegNote] = useState("");

  // Forgot password states
  const [forgotPhase, setForgotPhase] = useState("email"); // "email" | "verify"
  const [forgotEmail, setForgotEmail] = useState("");
  const [forgotCode, setForgotCode] = useState("");
  const [forgotNewPassword, setForgotNewPassword] = useState("");
  const [forgotConfirmPassword, setForgotConfirmPassword] = useState("");

  // Lead Admin view states
  const [superAdminTab, setSuperAdminTab] = useState("metrics"); // "metrics" or "approvals"
  const [metricsData, setMetricsData] = useState(null);
  const [isLoadingMetrics, setIsLoadingMetrics] = useState(false);
  const [pendingRequests, setPendingRequests] = useState([]);
  const [isLoadingRequests, setIsLoadingRequests] = useState(false);
  const [approvalLoadingId, setApprovalLoadingId] = useState(null);

  // User Admin view states
  const [userAudits, setUserAudits] = useState([]);
  const [isLoadingAudits, setIsLoadingAudits] = useState(false);
  const [auditSearch, setAuditSearch] = useState("");

  // Check existing token and setup status on mount
  useEffect(() => {
    checkSetupStatus();
    const savedToken = localStorage.getItem("ai_drive_admin_token");
    if (savedToken) {
      setAdminToken(savedToken);
      fetchAdminProfile(savedToken);
    }
  }, []);

  const checkSetupStatus = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/admin/setup-status`);
      if (res.ok) {
        const data = await res.json();
        setSetupStatus(data);
        if (!data.has_super_admin) {
          setSelectedRole("LEAD_ADMIN");
          setAuthMode("register");
        }
      }
    } catch (err) {
      console.error("Failed to check setup status:", err);
    }
  };

  const fetchAdminProfile = async (token) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/admin/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setAdminProfile(data);
        if (data.role === "SUPER_ADMIN") {
          loadMetrics(token);
          loadPendingRequests(token);
        } else {
          loadUserAudits(token);
        }
      } else {
        // Token expired or invalid
        handleLogout();
      }
    } catch (err) {
      console.error("Failed to fetch admin profile:", err);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setAuthLoading(true);
    setAuthError(null);
    setAuthSuccess(null);

    try {
      const res = await fetch(`${BACKEND_URL}/api/admin/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: loginEmail.trim(),
          password: loginPassword.trim(),
          role_type: selectedRole,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Authentication failed.");
      }

      localStorage.setItem("ai_drive_admin_token", data.token);
      setAdminToken(data.token);
      setAdminProfile({
        email: data.email,
        full_name: data.full_name,
        role: data.role,
      });

      if (data.role === "SUPER_ADMIN") {
        loadMetrics(data.token);
        loadPendingRequests(data.token);
      } else {
        loadUserAudits(data.token);
      }
    } catch (err) {
      setAuthError(err.message);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setAuthLoading(true);
    setAuthError(null);
    setAuthSuccess(null);

    try {
      const isLead = selectedRole === "LEAD_ADMIN";
      const res = await fetch(`${BACKEND_URL}/api/admin/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: regEmail.trim(),
          password: regPassword.trim(),
          full_name: regFullName.trim(),
          request_note: isLead
            ? "Primary Lead Admin (Initial Setup)"
            : regNote.trim(),
          role_type: selectedRole,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Registration request failed.");
      }

      setAuthSuccess(data.message);
      setRegEmail("");
      setRegPassword("");
      setRegFullName("");
      setRegNote("");
      checkSetupStatus();
      if (isLead) {
        setAuthMode("login");
      }
    } catch (err) {
      setAuthError(err.message);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleAdminForgotPassword = async (e) => {
    e.preventDefault();
    setAuthLoading(true);
    setAuthError(null);
    setAuthSuccess(null);

    try {
      const res = await fetch(`${BACKEND_URL}/api/admin/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: forgotEmail.trim() }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Failed to send reset code.");
      }
      setAuthSuccess(`A 6-digit verification code has been dispatched to ${forgotEmail.trim()}.`);
      setForgotPhase("verify");
    } catch (err) {
      setAuthError(err.message || "Failed to request code.");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleAdminResetPassword = async (e) => {
    e.preventDefault();
    setAuthLoading(true);
    setAuthError(null);
    setAuthSuccess(null);

    if (forgotNewPassword !== forgotConfirmPassword) {
      setAuthError("New passwords do not match.");
      setAuthLoading(false);
      return;
    }
    if (forgotNewPassword.length < 6) {
      setAuthError("Password must be at least 6 characters long.");
      setAuthLoading(false);
      return;
    }

    try {
      const res = await fetch(`${BACKEND_URL}/api/admin/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: forgotEmail.trim(),
          verification_code: forgotCode.trim(),
          new_password: forgotNewPassword.trim(),
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Failed to reset password.");
      }
      setAuthSuccess("Password successfully updated! Please sign in with your new password.");
      setAuthMode("login");
      setForgotPhase("email");
      setLoginEmail(forgotEmail);
      setForgotCode("");
      setForgotNewPassword("");
      setForgotConfirmPassword("");
    } catch (err) {
      setAuthError(err.message || "Failed to update password.");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("ai_drive_admin_token");
    setAdminToken(null);
    setAdminProfile(null);
    setMetricsData(null);
    setPendingRequests([]);
    setUserAudits([]);
  };

  const loadMetrics = async (token = adminToken) => {
    if (!token) return;
    setIsLoadingMetrics(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/admin/metrics`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setMetricsData(data);
      }
    } catch (err) {
      console.error("Error loading metrics:", err);
    } finally {
      setIsLoadingMetrics(false);
    }
  };

  const loadPendingRequests = async (token = adminToken) => {
    if (!token) return;
    setIsLoadingRequests(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/admin/pending-requests`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setPendingRequests(data.requests || []);
      }
    } catch (err) {
      console.error("Error loading pending requests:", err);
    } finally {
      setIsLoadingRequests(false);
    }
  };

  const handleApproveOrReject = async (adminId, action) => {
    setApprovalLoadingId(adminId);
    try {
      const res = await fetch(`${BACKEND_URL}/api/admin/handle-request`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${adminToken}`,
        },
        body: JSON.stringify({
          admin_id: adminId,
          action,
        }),
      });
      if (res.ok) {
        await loadPendingRequests();
      }
    } catch (err) {
      console.error("Failed to handle approval:", err);
    } finally {
      setApprovalLoadingId(null);
    }
  };

  const loadUserAudits = async (token = adminToken) => {
    if (!token) return;
    setIsLoadingAudits(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/admin/user-audit`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setUserAudits(data.audits || []);
      }
    } catch (err) {
      console.error("Error loading audits:", err);
    } finally {
      setIsLoadingAudits(false);
    }
  };

  // ─────────────────────────────────────────────────────────────
  // RENDER: Not Logged In (Admin Gateway Sign-In / Register)
  // ─────────────────────────────────────────────────────────────
  if (!adminProfile) {
    const isLeadRole = selectedRole === "LEAD_ADMIN";
    const hasSuperAdmin = setupStatus?.has_super_admin;
    const isLeadSetupPending = isLeadRole && !hasSuperAdmin;

    return (
      <div className="max-w-[1440px] mx-auto px-6 py-10 flex flex-col items-center justify-center min-h-[70vh]">
        <div className="w-full max-w-lg bg-white border border-slate-200/90 rounded-3xl p-8 shadow-xl shadow-slate-200/50 relative overflow-hidden animate-fade-in">
          {/* Top Decorative Header */}
          <div className="flex flex-col items-center text-center mb-6">
            <div
              className={`w-14 h-14 rounded-2xl flex items-center justify-center text-white shadow-lg mb-3.5 ${
                isLeadRole
                  ? "bg-gradient-to-tr from-indigo-600 to-purple-600 shadow-indigo-500/25"
                  : "bg-gradient-to-tr from-blue-600 to-cyan-600 shadow-blue-500/25"
              }`}
            >
              {isLeadRole ? <Shield size={26} className="stroke-[2.2]" /> : <Users size={26} className="stroke-[2.2]" />}
            </div>
            <h2 className="font-heading text-lg font-bold text-slate-900 tracking-tight">
              {isLeadRole ? "Lead Admin Portal" : "User Admin Portal"}
            </h2>
            <p className="text-xs text-slate-500 mt-1 max-w-[340px]">
              {isLeadRole
                ? "Exclusive console for the primary Lead Admin. Zero-knowledge telemetry, KPIs, and User Admin approvals."
                : "Auditor workspace for User Admins. Log in using your User Portal credentials after Lead Admin approval."}
            </p>
          </div>

          {/* Primary Role Selector: Lead Admin vs User Admin */}
          <div className="grid grid-cols-2 p-1.5 bg-slate-100 rounded-2xl mb-5 border border-slate-200/80 gap-1.5">
            <button
              type="button"
              onClick={() => {
                setSelectedRole("LEAD_ADMIN");
                setAuthError(null);
                setAuthSuccess(null);
                if (!hasSuperAdmin) {
                  setAuthMode("register");
                } else {
                  setAuthMode("login");
                }
              }}
              className={`flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl text-xs font-bold transition-all ${
                isLeadRole
                  ? "bg-white text-indigo-700 shadow-xs border border-indigo-100"
                  : "text-slate-500 hover:text-slate-800"
              }`}
            >
              <Shield size={14} className={isLeadRole ? "text-indigo-600" : "text-slate-400"} />
              Lead Admin
            </button>
            <button
              type="button"
              onClick={() => {
                setSelectedRole("USER_ADMIN");
                setAuthError(null);
                setAuthSuccess(null);
                setAuthMode("login");
              }}
              className={`flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl text-xs font-bold transition-all ${
                !isLeadRole
                  ? "bg-white text-blue-700 shadow-xs border border-blue-100"
                  : "text-slate-500 hover:text-slate-800"
              }`}
            >
              <Users size={14} className={!isLeadRole ? "text-blue-600" : "text-slate-400"} />
              User Admin
            </button>
          </div>

          {/* Setup Notice for Lead Admin */}
          {isLeadSetupPending && (
            <div className="mb-5 p-3 rounded-xl bg-indigo-50/90 border border-indigo-200 text-xs text-indigo-900 flex items-start gap-2 animate-fade-in">
              <Sparkles size={16} className="text-indigo-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-bold">Initial Lead Admin Registration</p>
                <p className="text-[11px] text-indigo-700 mt-0.5 leading-relaxed">
                  No Lead Admin exists yet. Registering below permanently activates the primary Lead Admin account with immediate full access.
                </p>
              </div>
            </div>
          )}

          {/* Sub-toggle for User Admin (Sign In vs Request Access) */}
          {!isLeadRole && authMode !== "forgot" && (
            <div className="flex items-center p-1 bg-slate-50 rounded-xl mb-5 border border-slate-200/60">
              <button
                type="button"
                onClick={() => {
                  setAuthMode("login");
                  setAuthError(null);
                  setAuthSuccess(null);
                }}
                className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                  authMode === "login"
                    ? "bg-white text-slate-900 shadow-2xs border border-slate-200/50"
                    : "text-slate-500 hover:text-slate-800"
                }`}
              >
                User Admin Sign In
              </button>
              <button
                type="button"
                onClick={() => {
                  setAuthMode("register");
                  setAuthError(null);
                  setAuthSuccess(null);
                }}
                className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                  authMode === "register"
                    ? "bg-white text-slate-900 shadow-2xs border border-slate-200/50"
                    : "text-slate-500 hover:text-slate-800"
                }`}
              >
                Request User Admin Access
              </button>
            </div>
          )}

          {/* Feedback Banners */}
          {authError && (
            <div className="mb-4 p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700 flex items-start gap-2 animate-fade-in">
              <AlertCircle size={15} className="flex-shrink-0 mt-0.5 text-rose-600" />
              <span>{authError}</span>
            </div>
          )}

          {authSuccess && (
            <div className="mb-4 p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-start gap-2 animate-fade-in">
              <CheckCircle2 size={15} className="flex-shrink-0 mt-0.5 text-emerald-600" />
              <span>{authSuccess}</span>
            </div>
          )}

          {/* ──────────────── FORM 1: LEAD ADMIN REGISTRATION ──────────────── */}
          {isLeadRole && isLeadSetupPending && authMode !== "forgot" && (
            <form onSubmit={handleRegister} className="flex flex-col gap-3.5">
              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                  Lead Admin Full Name
                </label>
                <input
                  type="text"
                  required
                  value={regFullName}
                  onChange={(e) => setRegFullName(e.target.value)}
                  placeholder="e.g. Lead Administrator"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:border-indigo-600 focus:ring-1 focus:ring-indigo-100 outline-none transition-all"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                  Lead Admin Work Email
                </label>
                <input
                  type="email"
                  required
                  value={regEmail}
                  onChange={(e) => setRegEmail(e.target.value)}
                  placeholder="lead.admin@company.com"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:border-indigo-600 focus:ring-1 focus:ring-indigo-100 outline-none transition-all"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                  Choose a Secure Password <span className="text-slate-400 font-normal">(min 6 characters)</span>
                </label>
                <input
                  type="password"
                  required
                  minLength={6}
                  value={regPassword}
                  onChange={(e) => setRegPassword(e.target.value)}
                  placeholder="At least 6 characters"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:border-indigo-600 focus:ring-1 focus:ring-indigo-100 outline-none transition-all"
                />
              </div>

              <button
                type="submit"
                disabled={authLoading}
                className="mt-2 w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 active:scale-[0.99] transition-all disabled:opacity-50 shadow-md shadow-indigo-500/20"
              >
                {authLoading ? <Loader2 size={14} className="animate-spin" /> : <Shield size={14} />}
                {authLoading ? "Registering Lead Admin..." : "Register & Activate Lead Admin"}
              </button>
            </form>
          )}

          {/* ──────────────── FORM 2: LEAD ADMIN SIGN IN ──────────────── */}
          {isLeadRole && !isLeadSetupPending && authMode === "login" && (
            <form onSubmit={handleLogin} className="flex flex-col gap-3.5">
              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                  Lead Admin Email
                </label>
                <input
                  type="email"
                  required
                  value={loginEmail}
                  onChange={(e) => setLoginEmail(e.target.value)}
                  placeholder="lead.admin@company.com"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:border-indigo-600 focus:ring-1 focus:ring-indigo-100 outline-none transition-all"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-[11px] font-semibold text-slate-700">
                    Lead Admin Password
                  </label>
                  <button
                    type="button"
                    onClick={() => {
                      setAuthMode("forgot");
                      setForgotPhase("email");
                      setForgotEmail(loginEmail);
                      setAuthError(null);
                      setAuthSuccess(null);
                    }}
                    className="text-[11px] font-medium text-indigo-600 hover:text-indigo-800 transition-colors"
                  >
                    Forgot password?
                  </button>
                </div>
                <input
                  type="password"
                  required
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:border-indigo-600 focus:ring-1 focus:ring-indigo-100 outline-none transition-all"
                />
              </div>

              <button
                type="submit"
                disabled={authLoading}
                className="mt-2 w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 active:scale-[0.99] transition-all disabled:opacity-50 shadow-md shadow-indigo-500/20"
              >
                {authLoading ? <Loader2 size={14} className="animate-spin" /> : <Lock size={13} />}
                {authLoading ? "Authenticating Lead Admin..." : "Sign In as Lead Admin"}
              </button>
            </form>
          )}

          {/* ──────────────── FORM 3: USER ADMIN SIGN IN ──────────────── */}
          {!isLeadRole && authMode === "login" && (
            <form onSubmit={handleLogin} className="flex flex-col gap-3.5">
              <div className="p-3 rounded-xl bg-blue-50/80 border border-blue-200/80 text-[11px] text-blue-900 leading-relaxed">
                ℹ️ <strong>User Portal Credentials:</strong> Enter the same email and password you use to log in to the <strong>User Portal</strong>.
                <p className="mt-1 text-blue-700">
                  Requires one-time approval by the Lead Admin before your first login. Once approved, you can log in freely anytime.
                </p>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                  User Portal Email
                </label>
                <input
                  type="email"
                  required
                  value={loginEmail}
                  onChange={(e) => setLoginEmail(e.target.value)}
                  placeholder="user@example.com"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:border-blue-600 focus:ring-1 focus:ring-blue-100 outline-none transition-all"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-[11px] font-semibold text-slate-700">
                    User Portal Password
                  </label>
                  <button
                    type="button"
                    onClick={() => {
                      setAuthMode("forgot");
                      setForgotPhase("email");
                      setForgotEmail(loginEmail);
                      setAuthError(null);
                      setAuthSuccess(null);
                    }}
                    className="text-[11px] font-medium text-blue-600 hover:text-blue-800 transition-colors"
                  >
                    Forgot password?
                  </button>
                </div>
                <input
                  type="password"
                  required
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:border-blue-600 focus:ring-1 focus:ring-blue-100 outline-none transition-all"
                />
              </div>

              <button
                type="submit"
                disabled={authLoading}
                className="mt-2 w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 active:scale-[0.99] transition-all disabled:opacity-50 shadow-md shadow-blue-500/20"
              >
                {authLoading ? <Loader2 size={14} className="animate-spin" /> : <Lock size={13} />}
                {authLoading ? "Verifying Credentials..." : "Sign In as User Admin"}
              </button>

              <div className="mt-3 pt-3 border-t border-slate-100 text-center">
                <p className="text-[11px] text-slate-400">
                  Don't have User Admin access yet?{" "}
                  <button
                    type="button"
                    onClick={() => {
                      setAuthMode("register");
                      setAuthError(null);
                      setAuthSuccess(null);
                    }}
                    className="text-blue-600 font-semibold hover:underline"
                  >
                    Request Access
                  </button>
                </p>
              </div>
            </form>
          )}

          {/* ──────────────── FORM 4: REQUEST USER ADMIN ACCESS ──────────────── */}
          {!isLeadRole && authMode === "register" && (
            <form onSubmit={handleRegister} className="flex flex-col gap-3.5">
              <div className="p-3 rounded-xl bg-amber-50/90 border border-amber-200 text-[11px] text-amber-900 leading-relaxed">
                ℹ️ <strong>First-Time Approval:</strong> Enter your User Portal account details and your reason for requesting admin privileges. An email notification will be sent to the Lead Admin. Once approved, you can log in freely.
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                  Full Name
                </label>
                <input
                  type="text"
                  required
                  value={regFullName}
                  onChange={(e) => setRegFullName(e.target.value)}
                  placeholder="e.g. John Doe"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:border-blue-600 focus:ring-1 focus:ring-blue-100 outline-none transition-all"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                  User Portal Email
                </label>
                <input
                  type="email"
                  required
                  value={regEmail}
                  onChange={(e) => setRegEmail(e.target.value)}
                  placeholder="user@example.com"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:border-blue-600 focus:ring-1 focus:ring-blue-100 outline-none transition-all"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                  User Portal Password <span className="text-slate-400 font-normal">(min 6 characters)</span>
                </label>
                <input
                  type="password"
                  required
                  minLength={6}
                  value={regPassword}
                  onChange={(e) => setRegPassword(e.target.value)}
                  placeholder="At least 6 characters"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:border-blue-600 focus:ring-1 focus:ring-blue-100 outline-none transition-all"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                  Reason for Admin Access <span className="text-rose-500">*</span>
                </label>
                <textarea
                  rows={2}
                  required
                  value={regNote}
                  onChange={(e) => setRegNote(e.target.value)}
                  placeholder="e.g., Compliance auditor reviewing Drive queries and source files"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:border-blue-600 focus:ring-1 focus:ring-blue-100 outline-none transition-all resize-none"
                />
              </div>

              <button
                type="submit"
                disabled={authLoading}
                className="mt-1 w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 active:scale-[0.99] transition-all disabled:opacity-50 shadow-md shadow-blue-500/20"
              >
                {authLoading ? <Loader2 size={14} className="animate-spin" /> : <UserPlus size={14} />}
                {authLoading ? "Submitting Request..." : "Submit User Admin Request"}
              </button>

              <div className="mt-3 pt-3 border-t border-slate-100 text-center">
                <p className="text-[11px] text-slate-400">
                  Already submitted or approved?{" "}
                  <button
                    type="button"
                    onClick={() => {
                      setAuthMode("login");
                      setAuthError(null);
                      setAuthSuccess(null);
                    }}
                    className="text-blue-600 font-semibold hover:underline"
                  >
                    Sign In as User Admin
                  </button>
                </p>
              </div>
            </form>
          )}

          {/* ──────────────── FORM 5: FORGOT PASSWORD ──────────────── */}
          {authMode === "forgot" && (
            <div className="flex flex-col gap-3.5">
              <div className="flex items-center gap-2 pb-1 border-b border-slate-100">
                <KeyRound size={15} className={isLeadRole ? "text-indigo-600" : "text-blue-600"} />
                <h3 className="text-xs font-bold text-slate-900">
                  {forgotPhase === "email" ? "Admin Password Reset" : "Verify Reset Code"}
                </h3>
              </div>

              {forgotPhase === "email" ? (
                <form onSubmit={handleAdminForgotPassword} className="flex flex-col gap-3">
                  <p className="text-[11px] text-slate-500">
                    Enter your registered email address. A 6-digit verification code will be dispatched to verify your identity.
                  </p>

                  <div>
                    <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                      {isLeadRole ? "Lead Admin Email" : "User Portal Email"}
                    </label>
                    <div className="relative">
                      <input
                        type="email"
                        required
                        value={forgotEmail}
                        onChange={(e) => setForgotEmail(e.target.value)}
                        placeholder="admin@example.com"
                        className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3.5 py-2 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:border-indigo-600 outline-none transition-all"
                      />
                      <Mail size={14} className="absolute left-3 top-2.5 text-slate-400" />
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={authLoading}
                    className="mt-1 w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 transition-all disabled:opacity-50 shadow-md shadow-indigo-500/20"
                  >
                    {authLoading ? <Loader2 size={14} className="animate-spin" /> : <KeyRound size={14} />}
                    {authLoading ? "Sending Code..." : "Send Verification Code"}
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setAuthMode("login");
                      setAuthError(null);
                      setAuthSuccess(null);
                    }}
                    className="text-[11px] text-slate-500 hover:text-slate-800 text-center mt-1"
                  >
                    Back to Sign In
                  </button>
                </form>
              ) : (
                <form onSubmit={handleAdminResetPassword} className="flex flex-col gap-3">
                  <p className="text-[11px] text-slate-500">
                    Enter the 6-digit verification code sent to <strong className="text-slate-800">{forgotEmail}</strong> and your new password.
                  </p>

                  <div>
                    <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                      6-Digit Verification Code
                    </label>
                    <input
                      type="text"
                      required
                      maxLength={6}
                      value={forgotCode}
                      onChange={(e) => setForgotCode(e.target.value)}
                      placeholder="123456"
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2 text-center text-sm font-mono tracking-widest font-bold text-indigo-900 placeholder-slate-400 focus:bg-white focus:border-indigo-600 outline-none transition-all"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                      New Password
                    </label>
                    <input
                      type="password"
                      required
                      minLength={6}
                      value={forgotNewPassword}
                      onChange={(e) => setForgotNewPassword(e.target.value)}
                      placeholder="••••••••"
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:border-indigo-600 outline-none transition-all"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                      Confirm New Password
                    </label>
                    <input
                      type="password"
                      required
                      minLength={6}
                      value={forgotConfirmPassword}
                      onChange={(e) => setForgotConfirmPassword(e.target.value)}
                      placeholder="••••••••"
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:border-indigo-600 outline-none transition-all"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={authLoading}
                    className="mt-1 w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 transition-all disabled:opacity-50 shadow-md shadow-emerald-600/20"
                  >
                    {authLoading ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
                    {authLoading ? "Updating..." : "Update Password & Sign In"}
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
                        setAuthError(null);
                        setAuthSuccess(null);
                      }}
                      className="hover:underline text-indigo-600 font-medium"
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

  // ─────────────────────────────────────────────────────────────
  // RENDER: LEAD ADMIN DASHBOARD
  // ─────────────────────────────────────────────────────────────
  if (adminProfile.role === "SUPER_ADMIN") {
    const kpis = metricsData?.kpis || {};
    const pendingCount = pendingRequests.filter((r) => r.status === "PENDING").length;

    return (
      <div className="max-w-[1440px] mx-auto px-6 py-6 flex flex-col gap-6 animate-fade-in">
        {/* Top Header Card */}
        <div className="bg-white border border-slate-200/80 rounded-2xl p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-indigo-600 to-blue-600 flex items-center justify-center text-white shadow-md shadow-indigo-500/20 flex-shrink-0">
              <Cpu size={22} className="stroke-[2.2]" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-heading text-base font-bold text-slate-900">
                  Lead Admin Control & Telemetry Console
                </h1>
                <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-indigo-50 text-indigo-700 border border-indigo-200">
                  LEAD ADMIN
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Technical metrics: latency, token usage, cache hit/miss, and User Admin governance.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={() => {
                loadMetrics();
                loadPendingRequests();
              }}
              disabled={isLoadingMetrics}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-slate-700 bg-slate-50 border border-slate-200 hover:bg-slate-100 transition-all"
            >
              <RefreshCw size={12} className={isLoadingMetrics ? "animate-spin text-indigo-600" : ""} />
              Refresh
            </button>
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-rose-600 bg-rose-50 border border-rose-200 hover:bg-rose-100 transition-all"
            >
              <LogOut size={12} />
              Sign Out
            </button>
          </div>
        </div>

        {/* Tab Switcher: Telemetry vs Admin Approvals */}
        <div className="flex items-center gap-2 border-b border-slate-200 pb-2">
          <button
            onClick={() => setSuperAdminTab("metrics")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              superAdminTab === "metrics"
                ? "bg-indigo-600 text-white shadow-sm shadow-indigo-500/20"
                : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
            }`}
          >
            <Activity size={14} />
            Technical Metrics & Telemetry
          </button>
          <button
            onClick={() => setSuperAdminTab("approvals")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all relative ${
              superAdminTab === "approvals"
                ? "bg-indigo-600 text-white shadow-sm shadow-indigo-500/20"
                : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
            }`}
          >
            <Users size={14} />
            User Admin Requests
            {pendingCount > 0 && (
              <span className="inline-flex items-center justify-center px-1.5 py-0.2 rounded-full text-[10px] font-extrabold bg-rose-500 text-white animate-pulse">
                {pendingCount}
              </span>
            )}
          </button>
        </div>

        {/* Tab 1: Technical Metrics */}
        {superAdminTab === "metrics" && (
          <div className="flex flex-col gap-6">
            {/* 4 KPI Metrics Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Metric 1: Latency */}
              <div className="bg-white border border-slate-200/80 rounded-2xl p-4 shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-500">Average Latency</span>
                  <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
                    <Clock size={16} />
                  </div>
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-extrabold text-slate-900">
                    {kpis.avg_latency_ms || 0}
                  </span>
                  <span className="text-xs font-semibold text-slate-400">ms</span>
                </div>
                <p className="text-[11px] text-slate-400 mt-1">End-to-end response time</p>
              </div>

              {/* Metric 2: Tokens Used */}
              <div className="bg-white border border-slate-200/80 rounded-2xl p-4 shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-500">Tokens Consumed</span>
                  <div className="w-8 h-8 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center">
                    <Zap size={16} />
                  </div>
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-extrabold text-slate-900">
                    {Number(kpis.total_tokens || 0).toLocaleString()}
                  </span>
                  <span className="text-xs font-semibold text-slate-400">tokens</span>
                </div>
                <p className="text-[11px] text-slate-400 mt-1">
                  Prompt: {Number(kpis.prompt_tokens || 0).toLocaleString()} | Resp:{" "}
                  {Number(kpis.completion_tokens || 0).toLocaleString()}
                </p>
              </div>

              {/* Metric 3: Cache Hit Ratio */}
              <div className="bg-white border border-slate-200/80 rounded-2xl p-4 shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-500">Cache Hit Ratio</span>
                  <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
                    <Database size={16} />
                  </div>
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-extrabold text-slate-900">
                    {kpis.cache_hit_ratio || 0}%
                  </span>
                  <span className="text-xs font-semibold text-emerald-600 font-medium">
                    {kpis.cache_hits || 0} hits
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 mt-1">
                  {kpis.cache_misses || 0} misses out of {kpis.total_queries || 0} queries
                </p>
              </div>

              {/* Metric 4: API Calls vs Cache */}
              <div className="bg-white border border-slate-200/80 rounded-2xl p-4 shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-500">LLM API Calls</span>
                  <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center">
                    <Sparkles size={16} />
                  </div>
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-extrabold text-slate-900">
                    {kpis.api_calls || 0}
                  </span>
                  <span className="text-xs font-semibold text-slate-400">Gemini calls</span>
                </div>
                <p className="text-[11px] text-slate-400 mt-1">
                  {kpis.cache_served || 0} served zero-cost from cache
                </p>
              </div>
            </div>

            {/* Zero-Knowledge Privacy Notice */}
            <div className="p-3.5 rounded-xl bg-indigo-50/70 border border-indigo-200/80 text-xs text-indigo-900 flex items-center gap-2.5">
              <ShieldCheck size={18} className="text-indigo-600 flex-shrink-0" />
              <span>
                <strong>Zero-Knowledge Lead Admin Privacy Guardrail:</strong> In compliance with security policy, query text and answer content of users are strictly redacted and never visible in the Lead Admin dashboard. Only technical telemetry is collected.
              </span>
            </div>

            {/* Logged-In Users & Session Breakdown */}
            <div className="bg-white border border-slate-200/80 rounded-2xl p-5 shadow-xs flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-heading text-sm font-bold text-slate-900">
                    Registered & Logged-In Users
                  </h3>
                  <p className="text-[11px] text-slate-400">
                    User emails connected through Google Drive and their query counts.
                  </p>
                </div>
                <span className="text-xs font-semibold text-slate-500 bg-slate-100 px-2.5 py-1 rounded-full border border-slate-200/60">
                  {metricsData?.logged_in_users?.length || 0} Users
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200/70 text-slate-400 font-semibold text-[11px]">
                      <th className="py-2.5 px-3">User Email</th>
                      <th className="py-2.5 px-3">First Joined</th>
                      <th className="py-2.5 px-3">Queries Executed</th>
                      <th className="py-2.5 px-3">Last Active</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {metricsData?.logged_in_users?.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="py-6 text-center text-slate-400 text-xs">
                          No user sessions recorded yet.
                        </td>
                      </tr>
                    ) : (
                      metricsData?.logged_in_users?.map((u, i) => (
                        <tr key={i} className="hover:bg-slate-50/60">
                          <td className="py-2.5 px-3 font-semibold text-slate-900 flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-emerald-500" />
                            {u.email}
                          </td>
                          <td className="py-2.5 px-3 text-slate-500">{u.first_joined}</td>
                          <td className="py-2.5 px-3 font-medium text-slate-800">
                            {u.queries_executed}
                          </td>
                          <td className="py-2.5 px-3 text-slate-500">{u.last_active}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Technical Telemetry Event Log */}
            <div className="bg-white border border-slate-200/80 rounded-2xl p-5 shadow-xs flex flex-col gap-3">
              <div>
                <h3 className="font-heading text-sm font-bold text-slate-900">
                  Real-Time Technical Telemetry Logs
                </h3>
                <p className="text-[11px] text-slate-400">
                  Detailed performance breakdowns: execution latency, token counts, cache hit status, and API execution.
                </p>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200/70 text-slate-400 font-semibold text-[11px]">
                      <th className="py-2.5 px-3">Timestamp</th>
                      <th className="py-2.5 px-3">User Email</th>
                      <th className="py-2.5 px-3">Latency</th>
                      <th className="py-2.5 px-3">Tokens (P / C / Tot)</th>
                      <th className="py-2.5 px-3">Cache Status</th>
                      <th className="py-2.5 px-3">Gemini API</th>
                      <th className="py-2.5 px-3">Intent</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {metricsData?.telemetry_logs?.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="py-8 text-center text-slate-400 text-xs">
                          No query telemetry logged yet. Execute queries in the User Portal to view live telemetry.
                        </td>
                      </tr>
                    ) : (
                      metricsData?.telemetry_logs?.map((log) => (
                        <tr key={log.id} className="hover:bg-slate-50/60 font-mono text-[11px]">
                          <td className="py-2.5 px-3 text-slate-500 font-sans">{log.timestamp}</td>
                          <td className="py-2.5 px-3 text-slate-900 font-sans font-medium">
                            {log.user_email}
                          </td>
                          <td className="py-2.5 px-3">
                            <span
                              className={`px-1.5 py-0.5 rounded font-semibold ${
                                log.latency_ms < 1000
                                  ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                  : log.latency_ms < 5000
                                  ? "bg-blue-50 text-blue-700 border border-blue-200"
                                  : "bg-amber-50 text-amber-700 border border-amber-200"
                              }`}
                            >
                              {log.latency_ms} ms
                            </span>
                          </td>
                          <td className="py-2.5 px-3 text-slate-600">
                            {log.prompt_tokens} / {log.completion_tokens} /{" "}
                            <strong>{log.total_tokens}</strong>
                          </td>
                          <td className="py-2.5 px-3">
                            {log.cache_hit ? (
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                CACHE HIT
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-600 border border-slate-200">
                                MISS
                              </span>
                            )}
                          </td>
                          <td className="py-2.5 px-3">
                            {log.api_called ? (
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-200">
                                CALLED
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-50 text-slate-500 border border-slate-200">
                                SKIPPED
                              </span>
                            )}
                          </td>
                          <td className="py-2.5 px-3 font-sans text-slate-600">{log.intent}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Admin Approvals */}
        {superAdminTab === "approvals" && (
          <div className="bg-white border border-slate-200/80 rounded-2xl p-6 shadow-xs flex flex-col gap-4">
            <div>
              <h3 className="font-heading text-sm font-bold text-slate-900">
                Admin Registration Access Requests
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Review and approve user requests to register as User Admins.
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-400 font-semibold text-[11px]">
                    <th className="py-3 px-3">Applicant Name</th>
                    <th className="py-3 px-3">Email Address</th>
                    <th className="py-3 px-3">Request Reason</th>
                    <th className="py-3 px-3">Date Submitted</th>
                    <th className="py-3 px-3">Status</th>
                    <th className="py-3 px-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {pendingRequests.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-slate-400 text-xs">
                        No admin registration requests submitted yet.
                      </td>
                    </tr>
                  ) : (
                    pendingRequests.map((req) => {
                      const isPending = req.status === "PENDING";
                      const isApproved = req.status === "APPROVED";
                      const isLoading = approvalLoadingId === req.id;

                      return (
                        <tr key={req.id} className="hover:bg-slate-50/70">
                          <td className="py-3 px-3 font-bold text-slate-900">{req.full_name}</td>
                          <td className="py-3 px-3 text-indigo-600 font-medium">{req.email}</td>
                          <td className="py-3 px-3 max-w-[200px] truncate text-slate-600" title={req.request_note}>
                            {req.request_note || "No note"}
                          </td>
                          <td className="py-3 px-3 text-slate-500">{req.created_at}</td>
                          <td className="py-3 px-3">
                            <span
                              className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                isPending
                                  ? "bg-amber-50 text-amber-700 border border-amber-200"
                                  : isApproved
                                  ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                  : "bg-rose-50 text-rose-700 border border-rose-200"
                              }`}
                            >
                              {req.status}
                            </span>
                          </td>
                          <td className="py-3 px-3 text-right">
                            {isPending ? (
                              <div className="flex items-center justify-end gap-2">
                                <button
                                  type="button"
                                  onClick={() => handleApproveOrReject(req.id, "APPROVE")}
                                  disabled={isLoading}
                                  className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 transition-all disabled:opacity-50"
                                >
                                  {isLoading ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
                                  Approve
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleApproveOrReject(req.id, "REJECT")}
                                  disabled={isLoading}
                                  className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold text-rose-600 bg-rose-50 border border-rose-200 hover:bg-rose-100 transition-all disabled:opacity-50"
                                >
                                  Reject
                                </button>
                              </div>
                            ) : (
                              <span className="text-[11px] text-slate-400">
                                {isApproved ? `Approved by ${req.approved_by || "System"}` : "Rejected"}
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ─────────────────────────────────────────────────────────────
  // RENDER: USER ADMIN AUDIT DASHBOARD
  // ─────────────────────────────────────────────────────────────
  const filteredAudits = userAudits.filter((a) => {
    const q = auditSearch.toLowerCase().trim();
    if (!q) return true;
    return (
      (a.query_asked || "").toLowerCase().includes(q) ||
      (a.responding_file_name || "").toLowerCase().includes(q)
    );
  });

  return (
    <div className="max-w-[1440px] mx-auto px-6 py-6 flex flex-col gap-6 animate-fade-in">
      {/* Header Banner */}
      <div className="bg-white border border-slate-200/80 rounded-2xl p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-md shadow-blue-500/20 flex-shrink-0">
            <FileText size={22} className="stroke-[2.2]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-heading text-base font-bold text-slate-900">
                User Admin Query Activity & Analysis Audit
              </h1>
              <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 border border-blue-200">
                USER ADMIN
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Logged in as: <strong>{adminProfile.email}</strong> ({adminProfile.full_name}) — Approved by Lead Admin
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => loadUserAudits()}
            disabled={isLoadingAudits}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-slate-700 bg-slate-50 border border-slate-200 hover:bg-slate-100 transition-all"
          >
            <RefreshCw size={12} className={isLoadingAudits ? "animate-spin text-blue-600" : ""} />
            Refresh Audits
          </button>
          <button
            onClick={handleLogout}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-rose-600 bg-rose-50 border border-rose-200 hover:bg-rose-100 transition-all"
          >
            <LogOut size={12} />
            Sign Out
          </button>
        </div>
      </div>

      {/* Scope Explanation Card */}
      <div className="p-4 rounded-2xl bg-blue-50/70 border border-blue-200/80 text-xs text-blue-900 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <ShieldCheck size={20} className="text-blue-600 flex-shrink-0" />
          <span>
            <strong>Isolated User Audit View:</strong> This portal displays the questions asked, files analyzed, files referenced, and the responding file name for your account. You cannot view technical metrics or other users' confidential documents.
          </span>
        </div>
        <div className="relative flex-shrink-0">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search queries or files..."
            value={auditSearch}
            onChange={(e) => setAuditSearch(e.target.value)}
            className="w-56 bg-white border border-slate-200 rounded-xl pl-8 pr-3 py-1.5 text-xs text-slate-800 placeholder-slate-400 outline-none focus:border-blue-500"
          />
        </div>
      </div>

      {/* Audits Table: Query Asked, Files Referenced, Files Analyzed, Responding File Name */}
      <div className="bg-white border border-slate-200/80 rounded-2xl p-5 shadow-xs flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h3 className="font-heading text-sm font-bold text-slate-900">
            Document Query Audit Records ({filteredAudits.length})
          </h3>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-200 text-slate-400 font-semibold text-[11px]">
                <th className="py-3 px-3">Timestamp</th>
                <th className="py-3 px-3 w-[28%]">Query Asked</th>
                <th className="py-3 px-3">Responding File Name</th>
                <th className="py-3 px-3">Files Referenced</th>
                <th className="py-3 px-3">Files Analyzed</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {filteredAudits.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-10 text-center text-slate-400 text-xs">
                    {auditSearch
                      ? `No audit records match "${auditSearch}".`
                      : "No query activity recorded for your account yet. Submit questions in the User Portal to populate this audit log."}
                  </td>
                </tr>
              ) : (
                filteredAudits.map((a) => (
                  <tr key={a.id} className="hover:bg-slate-50/70 align-top">
                    <td className="py-3 px-3 text-slate-500 font-mono text-[11px] whitespace-nowrap">
                      {a.timestamp}
                    </td>

                    {/* Query Asked */}
                    <td className="py-3 px-3">
                      <p className="font-semibold text-slate-900">{a.query_asked}</p>
                      {a.answer_snippet && (
                        <p className="text-[11px] text-slate-500 mt-1 line-clamp-2">
                          {a.answer_snippet}
                        </p>
                      )}
                    </td>

                    {/* Responding File Name */}
                    <td className="py-3 px-3">
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
                        <FileText size={12} className="text-emerald-600" />
                        {a.responding_file_name}
                      </span>
                    </td>

                    {/* Files Referenced */}
                    <td className="py-3 px-3">
                      <div className="flex flex-wrap gap-1">
                        {a.files_referenced && a.files_referenced.length > 0 ? (
                          a.files_referenced.map((f, i) => (
                            <span
                              key={i}
                              className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-blue-50 text-blue-700 border border-blue-200/70"
                            >
                              {f}
                            </span>
                          ))
                        ) : (
                          <span className="text-slate-400 text-[11px]">None cited</span>
                        )}
                      </div>
                    </td>

                    {/* Files Analyzed */}
                    <td className="py-3 px-3">
                      <div className="flex flex-wrap gap-1">
                        {a.files_analyzed && a.files_analyzed.length > 0 ? (
                          a.files_analyzed.map((f, i) => (
                            <span
                              key={i}
                              className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-100 text-slate-600 border border-slate-200/70"
                            >
                              {f}
                            </span>
                          ))
                        ) : (
                          <span className="text-slate-400 text-[11px]">Auto-discovered</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
