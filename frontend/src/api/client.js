/**
 * API client — wraps all backend calls with JWT auth.
 */
import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 (expired/invalid token) globally
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.reload();
    }
    return Promise.reject(err);
  }
);

// ── Auth ──
export const register = (username, password) =>
  api.post('/auth/register', { username, password });

export const login = (username, password) =>
  api.post('/auth/login', { username, password });

// ── Files ──
export const listFiles = () => api.get('/files');

export const deleteFile = (fileId) => api.delete(`/files/${fileId}`);

export const downloadFile = async (fileId) => {
  const res = await api.get(`/files/${fileId}/download`, {
    responseType: 'arraybuffer',
  });
  return res.data;
};

export const uploadFile = (file) => {
  const form = new FormData();
  form.append('file', file);
  return api.post('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

// ── Agent Chat ──
export const sendMessage = (fileId, message) =>
  api.post('/agent/chat', { file_id: fileId, message });

export default api;
