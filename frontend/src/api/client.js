import axios from 'axios';

const API_BASE_URL = 'http://127.0.0.1:8000/api';

export const getAuthToken = () => {
  return localStorage.getItem('irium_auth_token') || null;
};

export const setAuthToken = (token) => {
  if (token) {
    localStorage.setItem('irium_auth_token', token);
  } else {
    localStorage.removeItem('irium_auth_token');
  }
};

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  const token = getAuthToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const message =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      'An error occurred';
    return Promise.reject(new Error(message));
  }
);

export const authApi = {
  async register({ username, email, password, full_name }) {
    const response = await apiClient.post('/auth/register', {
      username,
      email,
      password,
      full_name,
    });
    return response.data;
  },

  async login({ username_or_email, password }) {
    const response = await apiClient.post('/auth/login', {
      username_or_email,
      password,
    });
    return response.data;
  },

  async verifyAndLogin({ email, code }) {
    const response = await apiClient.post('/auth/verify-and-login', {
      email,
      code,
    });
    return response.data;
  },

  async resendVerification(email) {
    const response = await apiClient.post(
      `/auth/resend-verification?email=${encodeURIComponent(email)}`
    );
    return response.data;
  },

  async getMe() {
    const response = await apiClient.get('/auth/me');
    return response.data;
  },

  async sendChatQuery(queryText, sessionId = null, attachments = null) {
    const payload = {
      query: queryText || "",
      session_id: sessionId,
    };
    if (attachments && attachments.length > 0) {
      payload.attachments = attachments.map((a) => ({
        name: a.name,
        type: a.type,
        data: a.data,
        size: a.size || 0,
      }));
    }
    const response = await apiClient.post('/chat/query', payload);
    return response.data;
  },
};


export const chatApi = {
  async getSessions() {
    const response = await apiClient.get('/chat/sessions');
    return response.data;
  },

  async getSession(sessionId) {
    const response = await apiClient.get(`/chat/sessions/${sessionId}`);
    return response.data;
  },

  async saveSession(sessionData) {
    const response = await apiClient.post('/chat/sessions', sessionData);
    return response.data;
  },

  async sendQuery(queryText, sessionId = null) {
    return authApi.sendChatQuery(queryText, sessionId);
  },
};


export const documentApi = {
  async uploadDocument(files) {
    const formData = new FormData();
    files.forEach((file) => {
      formData.append('files', file);
    });

    const response = await apiClient.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  async getDocuments() {
    const response = await apiClient.get('/documents');
    return response.data.documents;
  },

  async deleteDocument(documentId) {
    const response = await apiClient.delete(`/documents/${documentId}`);
    return response.data;
  },

  async queryDocuments(queryText, documentIds = null, topK = 5) {
    const response = await apiClient.post('/documents/query', {
      query: queryText,
      document_ids: documentIds,
      top_k: topK,
    });
    return response.data;
  },
};