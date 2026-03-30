import { useEffect, useRef, useState } from 'react';
import { downloadFile } from '../api/client';
import { renderAsync } from 'docx-preview';

/**
 * DocPreview — renders the .docx file using docx-preview library.
 */
export default function DocPreview({ activeFileId, activeFileName, refreshKey }) {
  const containerRef = useRef(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!activeFileId) return;

    let cancelled = false;

    const loadDoc = async () => {
      setLoading(true);
      setError('');

      try {
        const arrayBuffer = await downloadFile(activeFileId);
        if (cancelled) return;

        // Clear previous render
        if (containerRef.current) {
          containerRef.current.innerHTML = '';
        }

        await renderAsync(arrayBuffer, containerRef.current, null, {
          className: 'docx-wrapper',
          inWrapper: true,
          ignoreWidth: false,
          ignoreHeight: false,
          ignoreFonts: false,
          breakPages: true,
          ignoreLastRenderedPageBreak: true,
          experimental: false,
          trimXmlDeclaration: true,
          useBase64URL: true,
        });
      } catch (err) {
        if (!cancelled) {
          console.error('Failed to render document:', err);
          setError('Failed to load document.');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    loadDoc();
    return () => { cancelled = true; };
  }, [activeFileId, refreshKey]);

  // Empty state
  if (!activeFileId) {
    return (
      <section className="doc-preview">
        <div className="doc-preview-header">
          <h2>Document Preview</h2>
        </div>
        <div className="doc-preview-body">
          <div className="doc-empty-state">
            <div className="empty-icon">📄</div>
            <h3>No Document Selected</h3>
            <p>
              Upload a .docx file or select one from the sidebar to preview it here.
            </p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="doc-preview">
      <div className="doc-preview-header">
        <h2>{activeFileName || 'Document Preview'}</h2>
        {!loading && !error && (
          <div className="doc-preview-status">
            <span className="dot" />
            Live Preview
          </div>
        )}
      </div>
      <div className="doc-preview-body">
        {loading && (
          <div className="doc-loading">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="skeleton-line" />
            ))}
          </div>
        )}

        {error && (
          <div className="doc-empty-state">
            <div className="empty-icon">⚠️</div>
            <h3>{error}</h3>
          </div>
        )}

        <div
          ref={containerRef}
          style={{ display: loading || error ? 'none' : 'block', width: '100%' }}
        />
      </div>
    </section>
  );
}
