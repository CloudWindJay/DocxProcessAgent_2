import { useEffect, useRef, useState } from 'react';
import {
  createConversation,
  getConversationMessages,
  listConversations,
  sendConversationMessage,
  uploadFile,
} from '../api/client';
import ChatMessageContent from './ChatMessageContent';

export default function ConversationChat({
  activeFileId,
  activeFileName,
  onFileUpdated,
  onUploadStart,
  onUploadComplete,
  onFilesChange,
}) {
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 120) + 'px';
    }
  }, [input]);

  useEffect(() => {
    if (!activeFileId) {
      setConversations([]);
      setActiveConversationId(null);
      setMessages([]);
      return;
    }

    let cancelled = false;

    const loadConversations = async () => {
      setLoadingHistory(true);
      try {
        const res = await listConversations(activeFileId);
        if (cancelled) return;

        const nextConversations = res.data;
        setConversations(nextConversations);

        if (nextConversations.length > 0) {
          await loadMessages(nextConversations[0].id, cancelled);
        } else {
          setActiveConversationId(null);
          setMessages([]);
        }
      } catch (err) {
        if (!cancelled) {
          console.error('Failed to load conversations:', err);
          setConversations([]);
          setActiveConversationId(null);
          setMessages([]);
        }
      } finally {
        if (!cancelled) {
          setLoadingHistory(false);
        }
      }
    };

    loadConversations();
    return () => {
      cancelled = true;
    };
  }, [activeFileId]);

  const addMessage = (message) => {
    setMessages((prev) => [...prev, message]);
  };

  const loadMessages = async (conversationId, cancelled = false) => {
    const res = await getConversationMessages(conversationId);
    if (cancelled) return;

    setActiveConversationId(conversationId);
    setMessages(
      res.data.messages.map((message) => ({
        id: message.id,
        role: message.role,
        content: message.content,
      }))
    );
  };

  const handleNewConversation = async () => {
    if (!activeFileId) return;

    try {
      const res = await createConversation(activeFileId);
      const nextConversation = res.data;
      setConversations((prev) => [nextConversation, ...prev]);
      setActiveConversationId(nextConversation.id);
      setMessages([]);
    } catch (err) {
      console.error('Failed to create conversation:', err);
      alert(err.response?.data?.detail || 'Failed to create a new chat.');
    }
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || !activeFileId || sending) return;

    setInput('');
    let conversationId = activeConversationId;

    if (!conversationId) {
      try {
        const createRes = await createConversation(activeFileId);
        const nextConversation = createRes.data;
        setConversations((prev) => [nextConversation, ...prev]);
        setActiveConversationId(nextConversation.id);
        conversationId = nextConversation.id;
      } catch (err) {
        addMessage({
          role: 'error',
          content: err.response?.data?.detail || 'Failed to create a conversation.',
          id: Date.now() + Math.random(),
        });
        return;
      }
    }

    addMessage({ role: 'user', content: text, id: Date.now() + Math.random() });
    setSending(true);

    try {
      const res = await sendConversationMessage(conversationId, text);
      const {
        conversation,
        assistant_message: assistantMessage,
        file_updated: fileUpdated,
      } = res.data;

      setConversations((prev) => {
        const rest = prev.filter((item) => item.id !== conversation.id);
        return [conversation, ...rest];
      });
      addMessage({
        role: 'assistant',
        content: assistantMessage.content,
        id: assistantMessage.id,
      });

      if (fileUpdated) {
        addMessage({
          role: 'system',
          content: 'Document has been updated. Preview refreshed.',
          id: Date.now() + Math.random(),
        });
        onFileUpdated?.();
      }
    } catch (err) {
      const errMsg =
        err.response?.data?.detail || 'Failed to get a response. Please try again.';
      addMessage({ role: 'error', content: errMsg, id: Date.now() + Math.random() });
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

    addMessage({
      role: 'system',
      content: `Uploading and analyzing ${file.name}...`,
      id: Date.now() + Math.random(),
    });
    onUploadStart?.(file.name);

    try {
      const res = await uploadFile(file);
      addMessage({
        role: 'system',
        content: `${file.name} uploaded and indexed successfully.`,
        id: Date.now() + Math.random(),
      });
      onUploadComplete?.(res.data);
      onFilesChange?.();
    } catch (err) {
      const errMsg = err.response?.data?.detail || 'Upload failed.';
      addMessage({
        role: 'error',
        content: errMsg,
        id: Date.now() + Math.random(),
      });
      onUploadComplete?.(null, errMsg);
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  if (!activeFileId) {
    return (
      <aside className="chat-panel">
        <div className="chat-header">
          <span className="ai-dot" />
          <h2>AI Assistant</h2>
        </div>
        <div className="chat-conversation-toolbar">
          <div className="conversation-context">Select a file to load its chats</div>
        </div>
        <div className="chat-empty">
          <div className="ai-icon">AI</div>
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
              +
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
      <div className="chat-header">
        <span className="ai-dot" />
        <h2>AI Assistant</h2>
      </div>

      <div className="chat-conversation-toolbar">
        <div className="conversation-context">
          {activeFileName ? `Chats for ${activeFileName}` : 'File chat'}
        </div>
        <button className="btn-conversation-new" onClick={handleNewConversation}>
          New Chat
        </button>
      </div>

      <div className="conversation-list">
        {conversations.map((conversation) => (
          <button
            key={conversation.id}
            className={`conversation-chip ${
              conversation.id === activeConversationId ? 'active' : ''
            }`}
            onClick={() => loadMessages(conversation.id)}
          >
            <span className="conversation-chip-title">{conversation.title}</span>
          </button>
        ))}
      </div>

      <div className="chat-messages">
        {loadingHistory && (
          <div className="chat-empty">
            <div className="ai-icon">...</div>
            <h3>Loading chat history</h3>
          </div>
        )}

        {!loadingHistory && messages.length === 0 && (
          <div className="chat-empty">
            <div className="ai-icon">AI</div>
            <h3>{activeConversationId ? `Chat about ${activeFileName}` : 'Start a new chat'}</h3>
            <p>
              {activeConversationId
                ? 'Ask me to edit, summarize, shorten, or rewrite any part of the document.'
                : 'Create a new chat or send a message to begin a file-scoped conversation.'}
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={`chat-message ${msg.role}`}>
            <ChatMessageContent content={msg.content} />
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

      <div className="chat-input-area">
        <div className="chat-input-wrapper">
          <button
            className="btn-attach"
            onClick={() => fileInputRef.current?.click()}
            title="Upload a new document"
            id="btn-chat-attach"
          >
            +
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
            {'->'}
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
