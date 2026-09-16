import React from "react";
import { useAuth } from "../context/AuthContext";

export default function ProfileModal() {
  const {
    user,
    isAuthenticated,
    isProfileModalOpen,
    closeProfileModal,
    logout,
  } = useAuth();

  if (!isProfileModalOpen || !isAuthenticated || !user) return null;

  const createdDate = user.created_at
    ? new Date(user.created_at).toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
    : "Recently";

  return (
    <div className="auth-modal-overlay" onClick={closeProfileModal}>
      <div
        className="auth-modal-card profile-modal-card"
        onClick={(e) => e.stopPropagation()}
      >
        <button className="auth-modal-close" onClick={closeProfileModal}>
          ✕
        </button>

        <div className="profile-header">
          <div className="profile-large-avatar">
            {(user.full_name || user.username || "U")[0].toUpperCase()}
          </div>
          <h2>{user.full_name}</h2>
          <span className="profile-username">@{user.username}</span>
        </div>

        <div className="profile-info-grid">
          <div className="profile-info-item">
            <span className="info-label">Email Address</span>
            <span className="info-value">{user.email}</span>
          </div>

          <div className="profile-info-item">
            <span className="info-label">Member Since</span>
            <span className="info-value">{createdDate}</span>
          </div>

          <div className="profile-info-item">
            <span className="info-label">Email Verification</span>
            <span className="info-value">
              <span className="status-badge verified">Verified ✅</span>
            </span>
          </div>
        </div>

        <div className="profile-actions">
          <button
            className="profile-logout-btn"
            onClick={() => {
              logout();
              closeProfileModal();
            }}
          >
            🚪 Log Out of IRIUM
          </button>
        </div>
      </div>
    </div>
  );
}
