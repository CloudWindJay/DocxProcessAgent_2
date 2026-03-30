import { useState } from 'react';
import { register, login } from '../api/client';

/**
 * Login / Register page with toggle between modes.
 */
export default function LoginPage({ onAuth }) {
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = isRegister
        ? await register(username, password)
        : await login(username, password);

      const { access_token, user } = res.data;
      localStorage.setItem('token', access_token);
      localStorage.setItem('user', JSON.stringify(user));
      onAuth(user);
    } catch (err) {
      const msg =
        err.response?.data?.detail || 'Something went wrong. Please try again.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={handleSubmit}>
        <h1>DocxProcess Agent</h1>
        <p className="subtitle">
          {isRegister
            ? 'Create an account to get started'
            : 'Sign in to your workspace'}
        </p>

        {error && <div className="login-error">{error}</div>}

        <div className="form-group">
          <label htmlFor="username">Username</label>
          <input
            id="username"
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Enter your username"
            required
            autoFocus
          />
        </div>

        <div className="form-group">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Enter your password"
            required
            minLength={6}
          />
        </div>

        <button
          type="submit"
          className="btn-primary"
          disabled={loading || !username || !password}
          id="btn-auth-submit"
        >
          {loading ? '...' : isRegister ? 'Create Account' : 'Sign In'}
        </button>

        <div className="login-toggle">
          {isRegister ? 'Already have an account? ' : "Don't have an account? "}
          <button
            type="button"
            onClick={() => {
              setIsRegister(!isRegister);
              setError('');
            }}
            id="btn-auth-toggle"
          >
            {isRegister ? 'Sign In' : 'Register'}
          </button>
        </div>
      </form>
    </div>
  );
}
