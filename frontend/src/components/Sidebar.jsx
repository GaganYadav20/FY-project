import React from "react";
import { useAuth } from "../context/AuthContext";

export default function Sidebar({ onNewChat, onShowNews, onShowDocumentAnalysis }) {
  const {
    user,
    isAuthenticated,
    openAuthModal,
    openProfileModal,
    chatSessions,
    activeSessionId,
    setActiveSessionId,
  } = useAuth();

  return (
    <aside className="sidebar">
      <div className="logo">
        IR<span>IUM</span>
      </div>

      <button className="new-chat" onClick={onNewChat}>
        + New Chat
      </button>

      <button className="news-button" onClick={onShowNews}>
        📰 Financial News
      </button>

      <button className="document-analysis-button" onClick={onShowDocumentAnalysis}>
        📄 Document Analysis
      </button>

      <div className="history">
        <div className="history-title">Recent Chats</div>
        {chatSessions.length === 0 ? (
          <div className="no-history-hint">
            No recent chats yet. Start asking queries below!
          </div>
        ) : (
          chatSessions.map((session) => (
            <div
              className={`history-item ${
                session.id === activeSessionId ? "active" : ""
              }`}
              key={session.id}
              onClick={() => setActiveSessionId(session.id)}
            >
              💬 {session.title}
            </div>
          ))
        )}
      </div>

      <div className="sidebar-footer">
        {isAuthenticated ? (
          <div
            className="user-profile-badge clickable"
            onClick={openProfileModal}
            title="Click to view Profile & Logout"
          >
            <div className="user-avatar">
              {(user.full_name || user.username || "U")[0].toUpperCase()}
            </div>
            <div className="user-details">
              <span className="user-name">{user.full_name}</span>
              <span className="user-email">{user.email}</span>
            </div>
            <span className="profile-arrow-hint">👤</span>
          </div>
        ) : (
          <button className="login-btn" onClick={openAuthModal}>
            🔑 Sign In / Register
          </button>
        )}
      </div>
    </aside>
  );
}
