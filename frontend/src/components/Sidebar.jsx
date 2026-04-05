import { useState, useRef } from 'react';
import { uploadFile } from '../api/client';

/**
 * Sidebar — file management panel with upload, file list, and user info.
 */
export default function Sidebar({
  files,
  activeFileId,
  onSelectFile,
  onFilesChange,
  user,
  onLogout,
  onUploadStart,
  onUploadComplete,
  onDeleteFile,
  onOpenSettings,
}) {
  const [collapsed, setCollapsed] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    onUploadStart?.(file.name);

    try {
      const res = await uploadFile(file);
      onUploadComplete?.(res.data);
      onFilesChange?.(); // Refresh file list
    } catch (err) {
      console.error('Upload failed:', err);
      onUploadComplete?.(null, err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const formatDate = (dateStr) => {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
      {/* Header */}
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="logo-icon">📄</div>
          <span>DocxAgent</span>
        </div>
        <button
          className="btn-collapse"
          onClick={() => setCollapsed(!collapsed)}
          title={collapsed ? 'Expand' : 'Collapse'}
          id="btn-sidebar-toggle"
        >
          {collapsed ? '▶' : '◀'}
        </button>
      </div>

      {/* Upload Button */}
      <div className="sidebar-upload">
        <button
          className="btn-upload"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          id="btn-sidebar-upload"
        >
          {uploading ? '⏳' : '＋'}
          <span className="upload-text">
            {uploading ? 'Uploading...' : 'Upload Document'}
          </span>
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".docx"
          className="hidden-input"
          onChange={handleUpload}
          id="input-file-upload"
        />
      </div>

      {/* File List */}
      <div className="sidebar-section-title">Documents</div>
      <div className="file-list">
        {files.length === 0 && (
          <div style={{ padding: '16px', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.8rem' }}>
            No documents yet.<br />Upload a .docx to begin.
          </div>
        )}
        {files.map((file) => (
          <div
            key={file.id}
            className={`file-item ${file.id === activeFileId ? 'active' : ''}`}
            onClick={() => onSelectFile(file.id)}
            title={file.filename}
            id={`file-item-${file.id}`}
          >
            <div className="file-icon">📋</div>
            <div className="file-info">
              <div className="file-name">{file.filename}</div>
              <div className="file-date">{formatDate(file.uploaded_at)}</div>
            </div>
            <button
              className="btn-delete-file"
              onClick={(e) => {
                e.stopPropagation();
                if (window.confirm(`Delete "${file.filename}"? This cannot be undone.`)) {
                  onDeleteFile?.(file.id);
                }
              }}
              title="Delete Document"
              id={`btn-delete-${file.id}`}
            >
              🗑️
            </button>
          </div>
        ))}
      </div>

      {/* User Footer */}
      <div className="sidebar-footer">
        <div className="user-avatar">
          {user?.username?.[0]?.toUpperCase() || 'U'}
        </div>
        <div className="user-info">
          <span>{user?.username}</span>
        </div>
        <button
          className="btn-settings"
          onClick={onOpenSettings}
          title="LLM Settings"
          id="btn-open-settings"
        >
          ⚙
        </button>
        <button
          className="btn-logout"
          onClick={onLogout}
          title="Sign Out"
          id="btn-logout"
        >
          ⏻
        </button>
      </div>
    </aside>
  );
}
