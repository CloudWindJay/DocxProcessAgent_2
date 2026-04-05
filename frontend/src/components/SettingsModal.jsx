import { useEffect, useState } from 'react';
import { getLLMSettings, updateLLMSettings } from '../api/client';

const PROVIDER_OPTIONS = [
  { value: 'qwen', label: 'Qwen' },
  { value: 'chatgpt', label: 'ChatGPT' },
  { value: 'gemini', label: 'Gemini' },
];

export default function SettingsModal({ open, onClose }) {
  const [provider, setProvider] = useState('qwen');
  const [useEnvKey, setUseEnvKey] = useState(true);
  const [apiKey, setApiKey] = useState('');
  const [hasStoredKey, setHasStoredKey] = useState(false);
  const [maskedStoredKey, setMaskedStoredKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;

    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError('');
      try {
        const res = await getLLMSettings();
        if (cancelled) return;
        setProvider(res.data.provider || 'qwen');
        setUseEnvKey(Boolean(res.data.use_env_key));
        setHasStoredKey(Boolean(res.data.has_custom_api_key));
        setMaskedStoredKey(res.data.masked_custom_api_key || '');
        setApiKey('');
      } catch (err) {
        if (!cancelled) {
          setError(err.response?.data?.detail || 'Failed to load LLM settings.');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, [open]);

  if (!open) return null;

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');

    try {
      const payload = {
        provider,
        use_env_key: useEnvKey,
      };

      if (!useEnvKey && apiKey.trim()) {
        payload.api_key = apiKey.trim();
      }

      const res = await updateLLMSettings(payload);
      setHasStoredKey(Boolean(res.data.has_custom_api_key));
      setMaskedStoredKey(res.data.masked_custom_api_key || '');
      setApiKey('');
      onClose?.();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save LLM settings.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="settings-modal-overlay" onClick={onClose}>
      <div className="settings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="settings-modal-header">
          <div>
            <h3>LLM Settings</h3>
            <p>Choose which provider this user uses for chat and document tasks.</p>
          </div>
          <button
            type="button"
            className="settings-close"
            onClick={onClose}
            id="btn-settings-close"
          >
            ×
          </button>
        </div>

        {loading ? (
          <div className="settings-loading">Loading settings...</div>
        ) : (
          <form className="settings-form" onSubmit={handleSave}>
            {error && <div className="settings-error">{error}</div>}

            <label className="settings-label" htmlFor="select-provider">
              Provider
            </label>
            <select
              id="select-provider"
              className="settings-select"
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
            >
              {PROVIDER_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>

            <label className="settings-checkbox">
              <input
                type="checkbox"
                checked={useEnvKey}
                onChange={(e) => setUseEnvKey(e.target.checked)}
              />
              <span>Use backend environment key</span>
            </label>

            <div className="settings-help">
              Environment mode uses backend environment configuration. It defaults to
              provider-specific variables when present and falls back to `LLM_API_KEY`.
            </div>

            {!useEnvKey && (
              <>
                <label className="settings-label" htmlFor="input-api-key">
                  Custom API Key
                </label>
                <input
                  id="input-api-key"
                  className="settings-input"
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={hasStoredKey ? 'Leave blank to keep current key' : 'Paste your API key'}
                />
                {hasStoredKey && (
                  <div className="settings-help">
                    Current stored key: <code>{maskedStoredKey}</code>
                  </div>
                )}
              </>
            )}

            <div className="settings-actions">
              <button
                type="button"
                className="btn-settings-secondary"
                onClick={onClose}
                id="btn-settings-cancel"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="btn-settings-primary"
                disabled={saving}
                id="btn-settings-save"
              >
                {saving ? 'Saving...' : 'Save Settings'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
