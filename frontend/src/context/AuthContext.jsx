import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { authApi, chatApi, getAuthToken, setAuthToken } from "../api/client";

const AuthContext = createContext(null);

const getStorageKey = (targetUser) => {
  if (targetUser && targetUser.id) {
    return `irium_chats_user_${targetUser.id}`;
  }
  return "irium_chats_guest";
};

const loadStoredSessions = (targetUser) => {
  try {
    const key = getStorageKey(targetUser);
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    console.warn("Failed to parse local chat sessions:", e);
    return [];
  }
};

const saveStoredSessions = (targetUser, sessions) => {
  try {
    const key = getStorageKey(targetUser);
    localStorage.setItem(key, JSON.stringify(sessions));
  } catch (e) {
    console.warn("Failed to persist local chat sessions:", e);
  }
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setTokenState] = useState(getAuthToken());
  const [loading, setLoading] = useState(true);
  
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);

  // Chat sessions state
  const [chatSessions, setChatSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);

  const loadSessionsForUser = useCallback(async (targetUser) => {
    // 1. Immediately load cached sessions from localStorage for instant display
    const cached = loadStoredSessions(targetUser);
    if (cached && cached.length > 0) {
      setChatSessions(cached);
    } else {
      setChatSessions([]);
    }

    // 2. If authenticated, fetch and synchronize from backend
    if (targetUser && getAuthToken()) {
      try {
        const summaries = await chatApi.getSessions();
        if (summaries && summaries.length > 0) {
          const cachedMap = new Map((cached || []).map((s) => [s.id, s]));
          
          const fullSessions = await Promise.all(
            summaries.map(async (sum) => {
              const localMatch = cachedMap.get(sum.id);
              if (localMatch && localMatch.messages && localMatch.messages.length >= (sum.message_count || 0)) {
                return { ...sum, messages: localMatch.messages };
              }
              try {
                const full = await chatApi.getSession(sum.id);
                return full;
              } catch (err) {
                return localMatch || { ...sum, messages: [] };
              }
            })
          );

          setChatSessions(fullSessions);
          saveStoredSessions(targetUser, fullSessions);
          return fullSessions;
        } else if (cached && cached.length > 0) {
          // If backend had no sessions but local storage has them, sync to backend
          for (const s of cached) {
            try {
              await chatApi.saveSession(s);
            } catch (err) {
              // ignore
            }
          }
        }
      } catch (err) {
        console.warn("Failed to sync chat sessions with server:", err);
      }
    }
    return cached;
  }, []);

  const saveOrUpdateSession = useCallback(async (sessionData) => {
    const nowStr = new Date().toISOString();
    let updatedList = [];

    setChatSessions((prev) => {
      const idx = prev.findIndex((s) => s.id === sessionData.id);
      if (idx >= 0) {
        updatedList = [...prev];
        updatedList[idx] = {
          ...updatedList[idx],
          ...sessionData,
          updated_at: nowStr,
        };
        // Move active session to top
        const [moved] = updatedList.splice(idx, 1);
        updatedList.unshift(moved);
      } else {
        const newSession = {
          id: sessionData.id || `session_${Date.now()}`,
          title: sessionData.title || "New Chat",
          created_at: sessionData.created_at || nowStr,
          updated_at: nowStr,
          messages: sessionData.messages || [],
        };
        updatedList = [newSession, ...prev];
      }

      saveStoredSessions(user, updatedList);
      return updatedList;
    });

    // If authenticated, sync with backend
    if (user && getAuthToken()) {
      try {
        await chatApi.saveSession(sessionData);
      } catch (err) {
        console.warn("Failed to save session to backend:", err);
      }
    }
  }, [user]);

  const refreshUser = async () => {
    try {
      const userData = await authApi.getMe();
      setUser(userData);
      return userData;
    } catch (err) {
      console.warn("Failed to refresh user profile:", err);
    }
  };

  useEffect(() => {
    async function loadUser() {
      const storedToken = getAuthToken();
      if (!storedToken) {
        loadSessionsForUser(null);
        setLoading(false);
        return;
      }
      try {
        const userData = await authApi.getMe();
        setUser(userData);
        await loadSessionsForUser(userData);
      } catch (err) {
        console.warn("Session expired or invalid token:", err.message);
        setAuthToken(null);
        setTokenState(null);
        setUser(null);
        loadSessionsForUser(null);
      } finally {
        setLoading(false);
      }
    }
    loadUser();
  }, [loadSessionsForUser]);

  const login = async (username_or_email, password) => {
    try {
      const response = await authApi.login({ username_or_email, password });
      setAuthToken(response.access_token);
      setTokenState(response.access_token);
      setUser(response.user);
      setIsAuthModalOpen(false);
      
      // Load user's saved chat history
      await loadSessionsForUser(response.user);
      return response.user;
    } catch (err) {
      if (err.message && err.message.includes("EMAIL_NOT_VERIFIED:")) {
        const unverifiedEmail = err.message.split("EMAIL_NOT_VERIFIED:")[1];
        const errorObj = new Error("Your email address is not verified yet. Please enter your 6-digit verification OTP.");
        errorObj.needsVerification = true;
        errorObj.email = unverifiedEmail;
        throw errorObj;
      }
      throw err;
    }
  };

  const register = async ({ username, email, password, full_name }) => {
    const response = await authApi.register({ username, email, password, full_name });
    return response;
  };

  const verifyAndLogin = async (email, code) => {
    const response = await authApi.verifyAndLogin({ email, code });
    setAuthToken(response.access_token);
    setTokenState(response.access_token);
    setUser(response.user);
    setIsAuthModalOpen(false);

    // Load user's saved chat history
    await loadSessionsForUser(response.user);
    return response.user;
  };

  const resendVerification = async (email) => {
    return await authApi.resendVerification(email || user?.email);
  };

  const logout = () => {
    // IMPORTANT: Do NOT delete user's saved chat history in localStorage or backend!
    // Simply clear current session token and user state
    setAuthToken(null);
    setTokenState(null);
    setUser(null);
    setIsProfileModalOpen(false);
    setActiveSessionId(null);
    
    // Switch to guest sessions without touching the logged-out user's persistent history
    const guestSessions = loadStoredSessions(null);
    setChatSessions(guestSessions);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        login,
        register,
        verifyAndLogin,
        logout,
        resendVerification,
        refreshUser,
        isAuthenticated: !!user,
        
        isAuthModalOpen,
        openAuthModal: () => setIsAuthModalOpen(true),
        closeAuthModal: () => setIsAuthModalOpen(false),
        
        isProfileModalOpen,
        openProfileModal: () => setIsProfileModalOpen(true),
        closeProfileModal: () => setIsProfileModalOpen(false),

        chatSessions,
        setChatSessions,
        activeSessionId,
        setActiveSessionId,
        saveOrUpdateSession,
        loadSessionsForUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

