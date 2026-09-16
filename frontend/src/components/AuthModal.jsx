import React, { useState } from "react";
import { useAuth } from "../context/AuthContext";

export default function AuthModal() {
  const {
    isAuthModalOpen,
    closeAuthModal,
    login,
    register,
    verifyAndLogin,
    resendVerification,
  } = useAuth();

  const [activeTab, setActiveTab] = useState("login"); // 'login' | 'register' | 'verify'

  // Form states
  const [loginIdentifier, setLoginIdentifier] = useState("");
  const [loginPassword, setLoginPassword] = useState("");

  const [regUsername, setRegUsername] = useState("");
  const [regEmail, setRegEmail] = useState("");
  const [regFullName, setRegFullName] = useState("");
  const [regPassword, setRegPassword] = useState("");

  // Verification state
  const [pendingEmail, setPendingEmail] = useState("");
  const [otpCode, setOtpCode] = useState("");

  const [error, setError] = useState("");
  const [infoMsg, setInfoMsg] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (!isAuthModalOpen) return null;

  const handleLogin = async (e) => {
    e.preventDefault();
    setError("");
    setInfoMsg("");

    if (!loginIdentifier.trim() || !loginPassword) {
      setError("Please enter your username/email and password.");
      return;
    }
    try {
      setSubmitting(true);
      await login(loginIdentifier.trim(), loginPassword);
      setLoginIdentifier("");
      setLoginPassword("");
    } catch (err) {
      if (err.needsVerification && err.email) {
        setPendingEmail(err.email);
        setActiveTab("verify");
        setInfoMsg(`Your email (${err.email}) is not verified. Enter the 6-digit OTP code sent to your email.`);
      } else {
        setError(err.message || "Failed to log in");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setError("");
    setInfoMsg("");

    if (!regFullName.trim() || regFullName.trim().length < 2) {
      setError("Full Name is compulsory (minimum 2 characters).");
      return;
    }

    if (!regUsername.trim()) {
      setError("Username is required.");
      return;
    }

    if (!regEmail.trim()) {
      setError("Email address is required.");
      return;
    }

    if (!regPassword || regPassword.length < 6) {
      setError("Password must be at least 6 characters long.");
      return;
    }

    try {
      setSubmitting(true);
      const res = await register({
        username: regUsername.trim(),
        email: regEmail.trim(),
        password: regPassword,
        full_name: regFullName.trim(),
      });

      setPendingEmail(res.email || regEmail.trim());
      setActiveTab("verify");
      setInfoMsg(`Account created! A 6-digit verification code has been sent to ${res.email || regEmail.trim()}.`);

      setRegUsername("");
      setRegEmail("");
      setRegFullName("");
      setRegPassword("");
    } catch (err) {
      setError(err.message || "Failed to create account");
    } finally {
      setSubmitting(false);
    }
  };

  const handleVerifyOtp = async (e) => {
    e.preventDefault();
    setError("");
    setInfoMsg("");

    if (!otpCode.trim() || otpCode.trim().length !== 6) {
      setError("Please enter a valid 6-digit verification OTP.");
      return;
    }

    try {
      setSubmitting(true);
      await verifyAndLogin(pendingEmail, otpCode.trim());
      setOtpCode("");
      setPendingEmail("");
    } catch (err) {
      setError(err.message || "Invalid or expired verification code.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleResendOtp = async () => {
    setError("");
    setInfoMsg("");
    try {
      await resendVerification(pendingEmail);
      setInfoMsg(`A new 6-digit verification code has been sent to ${pendingEmail}.`);
    } catch (err) {
      setError(err.message || "Failed to resend verification code.");
    }
  };

  return (
    <div className="auth-modal-overlay" onClick={closeAuthModal}>
      <div
        className="auth-modal-card"
        onClick={(e) => e.stopPropagation()}
      >
        <button className="auth-modal-close" onClick={closeAuthModal}>
          ✕
        </button>

        <div className="auth-header">
          <div className="auth-logo">⚡</div>
          <h2>IRIUM Account</h2>
          <p>
            {activeTab === "verify"
              ? "Email Verification Required"
              : "Sign in to access AI financial intelligence & research tools"}
          </p>
        </div>

        {activeTab !== "verify" && (
          <div className="auth-tabs">
            <button
              className={`auth-tab ${activeTab === "login" ? "active" : ""}`}
              onClick={() => {
                setActiveTab("login");
                setError("");
                setInfoMsg("");
              }}
            >
              Sign In
            </button>
            <button
              className={`auth-tab ${activeTab === "register" ? "active" : ""}`}
              onClick={() => {
                setActiveTab("register");
                setError("");
                setInfoMsg("");
              }}
            >
              Create Account
            </button>
          </div>
        )}

        {infoMsg && <div className="auth-info-msg">{infoMsg}</div>}
        {error && <div className="auth-error">{error}</div>}

        {activeTab === "login" && (
          <form className="auth-form" onSubmit={handleLogin}>
            <div className="form-group">
              <label>Username or Email *</label>
              <input
                type="text"
                placeholder="alex@irium.io or alex99"
                value={loginIdentifier}
                onChange={(e) => setLoginIdentifier(e.target.value)}
                autoFocus
              />
            </div>

            <div className="form-group">
              <label>Password *</label>
              <input
                type="password"
                placeholder="••••••••"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
              />
            </div>

            <button
              type="submit"
              className="auth-submit-btn"
              disabled={submitting}
            >
              {submitting ? "Authenticating..." : "Sign In ➔"}
            </button>
          </form>
        )}

        {activeTab === "register" && (
          <form className="auth-form" onSubmit={handleRegister}>
            <div className="form-group">
              <label>Full Name * (Compulsory)</label>
              <input
                type="text"
                placeholder="Alex Morgan"
                value={regFullName}
                onChange={(e) => setRegFullName(e.target.value)}
                autoFocus
              />
            </div>

            <div className="form-group">
              <label>Username *</label>
              <input
                type="text"
                placeholder="alex_researcher"
                value={regUsername}
                onChange={(e) => setRegUsername(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label>Email Address *</label>
              <input
                type="email"
                placeholder="alex@irium.io"
                value={regEmail}
                onChange={(e) => setRegEmail(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label>Password *</label>
              <input
                type="password"
                placeholder="Minimum 6 characters"
                value={regPassword}
                onChange={(e) => setRegPassword(e.target.value)}
              />
            </div>

            <button
              type="submit"
              className="auth-submit-btn"
              disabled={submitting}
            >
              {submitting ? "Creating Account..." : "Create Account ➔"}
            </button>
          </form>
        )}

        {activeTab === "verify" && (
          <form className="auth-form" onSubmit={handleVerifyOtp}>
            <div className="form-group">
              <label>6-Digit Verification Code *</label>
              <input
                type="text"
                maxLength={6}
                placeholder="123456"
                value={otpCode}
                onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ""))}
                style={{
                  textAlign: "center",
                  fontSize: "20px",
                  letterSpacing: "6px",
                  fontWeight: "bold",
                }}
                autoFocus
              />
            </div>

            <button
              type="submit"
              className="auth-submit-btn"
              disabled={submitting || otpCode.length !== 6}
            >
              {submitting ? "Verifying..." : "Verify & Sign In ➔"}
            </button>

            <div style={{ display: "flex", justifyContent: "space-between", marginTop: "12px" }}>
              <button
                type="button"
                className="resend-code-btn"
                onClick={handleResendOtp}
              >
                Resend 6-digit Code
              </button>

              <button
                type="button"
                className="resend-code-btn"
                onClick={() => {
                  setActiveTab("login");
                  setError("");
                  setInfoMsg("");
                }}
              >
                Back to Sign In
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
