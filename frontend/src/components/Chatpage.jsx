import React, { useState, useEffect } from "react";
import Sidebar from "./Sidebar";
import ChatWindow from "./ChatWindow";
import NewsViewer from "./NewsViewer";
import DocumentAnalysis from "./DocumentAnalysis";
import { useAuth } from "../context/AuthContext";
import { authApi } from "../api/client";

const DEFAULT_WELCOME_MSG = [
  {
    sender: "bot",
    text: "Hello! I'm IRIUM — your AI Financial Research Assistant. How can I assist your financial analysis today?",
  },
];

export default function ChatPage() {
  const {
    chatSessions,
    activeSessionId,
    setActiveSessionId,
    saveOrUpdateSession,
  } = useAuth();

  const [messages, setMessages] = useState(DEFAULT_WELCOME_MSG);
  const [showNews, setShowNews] = useState(false);
  const [showDocumentAnalysis, setShowDocumentAnalysis] = useState(false);

  // Sync messages when active session changes
  useEffect(() => {
    if (!activeSessionId) {
      setMessages(DEFAULT_WELCOME_MSG);
      return;
    }

    const currentSession = chatSessions.find((s) => s.id === activeSessionId);
    if (currentSession && currentSession.messages && currentSession.messages.length > 0) {
      setMessages(currentSession.messages);
    } else {
      setMessages(DEFAULT_WELCOME_MSG);
    }
  }, [activeSessionId, chatSessions]);

  const handleSendMessage = async (queryText, attachments = []) => {
    const userMsg = {
      sender: "user",
      text: queryText || (attachments.length > 0 ? `Uploaded: ${attachments.map(a => a.name).join(", ")}` : ""),
      attachments: attachments && attachments.length > 0 ? attachments : null,
      created_at: new Date().toISOString(),
    };
    
    // Determine session ID and title
    const currentSession = chatSessions.find((s) => s.id === activeSessionId);
    const targetSessionId = activeSessionId || `session_${Date.now()}`;
    
    let shortTitle = currentSession?.title;
    if (!shortTitle || shortTitle === "New Chat") {
      if (queryText && queryText.trim()) {
        shortTitle = queryText.length > 28 ? queryText.substring(0, 28) + "..." : queryText;
      } else if (attachments && attachments.length > 0) {
        shortTitle = `📎 ${attachments[0].name.substring(0, 24)}`;
      } else {
        shortTitle = "Financial Research";
      }
    }

    if (!activeSessionId) {
      setActiveSessionId(targetSessionId);
    }

    const updatedWithUser = [...messages.filter((m) => m !== DEFAULT_WELCOME_MSG[0]), userMsg];
    setMessages(updatedWithUser);

    try {
      // Call backend chat query endpoint with query & attachments
      const response = await authApi.sendChatQuery(queryText, targetSessionId, attachments);
      const botMsg = {
        sender: "bot",
        text: response.reply,
        tier: response.tier,
        charts: response.charts || [],
        structured_data: response.structured_data || [],
        metadata: response.metadata || {},
        created_at: new Date().toISOString(),
      };

      const finalMessages = [...updatedWithUser, botMsg];
      setMessages(finalMessages);

      // Persist session messages
      await saveOrUpdateSession({
        id: targetSessionId,
        title: shortTitle,
        messages: finalMessages,
      });
    } catch (err) {
      console.warn("API Error:", err);
      let errorText;
      if (err.message === "Failed to fetch" || err.name === "TypeError") {
        errorText =
          "Unable to connect to IRIUM backend server at this moment. Please ensure the backend server is running on port 8000.";
      } else {
        errorText =
          err.message ||
          "An unexpected error occurred while processing your query. Please try again.";
      }
      const fallbackMsg = {
        sender: "bot",
        text: errorText,
        created_at: new Date().toISOString(),
      };

      const finalMessages = [...updatedWithUser, fallbackMsg];
      setMessages(finalMessages);

      // Persist fallback error session so chat context isn't lost
      await saveOrUpdateSession({
        id: targetSessionId,
        title: shortTitle,
        messages: finalMessages,
      });
    }
  };

  const handleNewChat = () => {
    setShowNews(false);
    setShowDocumentAnalysis(false);
    setActiveSessionId(null);
    setMessages([
      {
        sender: "bot",
        text: "Started new research session. Ask IRIUM any financial query or attach an image/PDF!",
      },
    ]);
  };

  const handleShowNews = () => {
    setShowNews(true);
    setShowDocumentAnalysis(false);
  };

  const handleShowDocumentAnalysis = () => {
    setShowNews(false);
    setShowDocumentAnalysis(true);
  };

  return (
    <div className="app">
      <Sidebar 
        onNewChat={handleNewChat} 
        onShowNews={handleShowNews}
        onShowDocumentAnalysis={handleShowDocumentAnalysis}
      />
      {showNews ? (
        <NewsViewer />
      ) : showDocumentAnalysis ? (
        <DocumentAnalysis />
      ) : (
        <ChatWindow
          messages={messages}
          onSendMessage={handleSendMessage}
        />
      )}
    </div>
  );
}
