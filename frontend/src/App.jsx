import { useState, useEffect, useCallback } from 'react';
import './App.css';
import LoginPage from './components/LoginPage';
import Sidebar from './components/Sidebar';
import DocPreview from './components/DocPreview';
import AgentChat from './components/AgentChat';
import { listFiles, deleteFile } from './api/client';

/**
 * App — root component handling auth state and the 3-panel layout.
 */
export default function App() {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('user');
    return saved ? JSON.parse(saved) : null;
  });

  const [files, setFiles] = useState([]);
  const [activeFileId, setActiveFileId] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  // Fetch files when user is authenticated
  const fetchFiles = useCallback(async () => {
    if (!user) return;
    try {
      const res = await listFiles();
      setFiles(res.data);
    } catch (err) {
      console.error('Failed to fetch files:', err);
    }
  }, [user]);

  useEffect(() => {
    fetchFiles();
  }, [fetchFiles]);

  // ── Auth handlers ──
  const handleAuth = (userData) => {
    setUser(userData);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setUser(null);
    setFiles([]);
    setActiveFileId(null);
  };

  // ── File handlers ──
  const handleSelectFile = (fileId) => {
    setActiveFileId(fileId);
    setRefreshKey((k) => k + 1);
  };

  const handleFileUpdated = () => {
    // Increment refresh key to trigger DocPreview re-render
    setRefreshKey((k) => k + 1);
  };

  const handleUploadComplete = (data, error) => {
    if (data && !error) {
      // Auto-select the newly uploaded file
      fetchFiles().then(() => {
        setActiveFileId(data.file_id);
        setRefreshKey((k) => k + 1);
      });
    }
  };

  const handleDeleteFile = async (fileId) => {
    try {
      await deleteFile(fileId);
      // If the deleted file was active, clear it
      if (activeFileId === fileId) {
        setActiveFileId(null);
      }
      fetchFiles(); // Refresh list
    } catch (err) {
      console.error('Delete failed:', err);
      alert('Delete failed. Please try again.');
    }
  };

  // Get active file name
  const activeFile = files.find((f) => f.id === activeFileId);
  const activeFileName = activeFile?.filename || '';

  // ── Not authenticated ──
  if (!user) {
    return <LoginPage onAuth={handleAuth} />;
  }

  // ── Main Layout ──
  return (
    <div className="app-layout">
      <Sidebar
        files={files}
        activeFileId={activeFileId}
        onSelectFile={handleSelectFile}
        onFilesChange={fetchFiles}
        user={user}
        onLogout={handleLogout}
        onUploadStart={() => {}}
        onUploadComplete={handleUploadComplete}
        onDeleteFile={handleDeleteFile}
      />

      <DocPreview
        activeFileId={activeFileId}
        activeFileName={activeFileName}
        refreshKey={refreshKey}
      />

      <AgentChat
        activeFileId={activeFileId}
        activeFileName={activeFileName}
        onFileUpdated={handleFileUpdated}
        onUploadStart={() => {}}
        onUploadComplete={handleUploadComplete}
        onFilesChange={fetchFiles}
      />
    </div>
  );
}
