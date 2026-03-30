import { useState, useRef, useEffect } from 'react';
import { sendMessage, uploadFile } from '../api/client';

/**
 * AgentChat — AI chat panel with message history, file upload via "+", and typing indicator.
 */
export default function AgentChat({
  activeFileId,
  activeFileName,
  onFileUpdated,
  onUploadStart,
  onUploadComplete,
  onFilesChange,
}) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 120) + 'px';
    }
  }, [input]);

  const addMessage = (role, content) => {
    setMessages((prev) => [...prev, { role, content, id: Date.now() + Math.random() }]);
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || !activeFileId || sending) return;

    setInput('');
    addMessage('user', text);
    setSending(true);

    try {
      const res = await sendMessage(activeFileId, text);
      addMessage('assistant', res.data.reply);

      if (res.data.file_updated) {
        addMessage('system', '✅ Document has been updated. Preview refreshed.');
        onFileUpdated?.();
      }
    } catch (err) {
      const errMsg =
        err.response?.data?.detail || 'Failed to get a response. Please try again.';
      addMessage('error', errMsg);
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    addMessage('system', `📤 Uploading and analyzing ${file.name}...`);
    onUploadStart?.(file.name);

    try {
      const res = await uploadFile(file);
      addMessage('system', `✅ ${file.name} uploaded and indexed successfully.`);
      onUploadComplete?.(res.data);
      onFilesChange?.();
    } catch (err) {
      const errMsg = err.response?.data?.detail || 'Upload failed.';
      addMessage('error', `❌ ${errMsg}`);
      onUploadComplete?.(null, errMsg);
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // No file selected state
  if (!activeFileId) {
    return (
      <aside className="chat-panel">
        <div className="chat-header">
          <span className="ai-dot" />
          <h2>AI Assistant</h2>
        </div>
        <div className="chat-empty">
          <div className="ai-icon">🤖</div>
          <h3>Ready to Help</h3>
          <p>
            Select a document from the sidebar or upload a new one to start
            editing with AI.
          </p>
        </div>
        <div className="chat-input-area">
          <div className="chat-input-wrapper">
            <button
              className="btn-attach"
              onClick={() => fileInputRef.current?.click()}
              title="Upload a document"
              id="btn-chat-attach-empty"
            >
              ＋
            </button>
            <textarea
              placeholder="Select a document first..."
              disabled
              rows={1}
            />
            <input
              ref={fileInputRef}
              type="file"
              accept=".docx"
              className="hidden-input"
              onChange={handleFileUpload}
              id="input-chat-file-empty"
            />
          </div>
        </div>
      </aside>
    );
  }

  return (
    <aside className="chat-panel">
      {/* Header */}
      <div className="chat-header">
        <span className="ai-dot" />
        <h2>AI Assistant</h2>
      </div>

      {/* Messages */}
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <div className="ai-icon">🤖</div>
            <h3>Chat about {activeFileName}</h3>
            <p>
              Ask me to edit, summarize, shorten, or rewrite any part of the
              document. Try: "Change the title to Q3 Report"
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={`chat-message ${msg.role}`}>
            {msg.content}
          </div>
        ))}

        {sending && (
          <div className="typing-indicator">
            <span />
            <span />
            <span />
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="chat-input-area">
        <div className="chat-input-wrapper">
          <button
            className="btn-attach"
            onClick={() => fileInputRef.current?.click()}
            title="Upload a new document"
            id="btn-chat-attach"
          >
            ＋
          </button>
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`Ask about ${activeFileName || 'your document'}...`}
            rows={1}
            disabled={sending}
            id="input-chat-message"
          />
          <button
            className="btn-send"
            onClick={handleSend}
            disabled={!input.trim() || sending}
            title="Send message"
            id="btn-chat-send"
          >
            ➤
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".docx"
            className="hidden-input"
            onChange={handleFileUpload}
            id="input-chat-file"
          />
        </div>
      </div>
    </aside>
  );
}
