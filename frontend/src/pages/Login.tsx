/**
 * Login page for MAVERICKS PROJECT.
 * Authenticates users and redirects to Dashboard on success.
 */
import { useState, type FormEvent } from 'react';
import { login, type LoginResponse } from '../api/auth';

interface Props {
  onLogin: (user: LoginResponse) => void;
}

export default function Login({ onLogin }: Props) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const result = await login(username, password);
      onLogin(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-base flex items-center justify-center">
      <div className="w-full max-w-sm">
        {/* Brand */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-10 h-10 rounded border border-line bg-panel mb-4">
            <svg className="h-5 w-5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <h1 className="text-lg font-bold tracking-wide text-slate-200">
            MAVERICKS PROJECT
          </h1>
          <p className="text-xs text-slate-600 mt-1">Investigative Intelligence Platform</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="mp-panel p-6">
          {error && (
            <div className="mb-4 p-2.5 rounded bg-danger/10 border border-danger/20 text-danger text-xs">
              {error}
            </div>
          )}

          <div className="space-y-3">
            <div>
              <label className="block text-2xs font-medium text-slate-500 mb-1 uppercase tracking-wider">Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="mp-input"
                placeholder="Enter username"
                autoFocus
                required
              />
            </div>
            <div>
              <label className="block text-2xs font-medium text-slate-500 mb-1 uppercase tracking-wider">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mp-input"
                placeholder="Enter password"
                required
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="mt-5 w-full py-2 rounded bg-accent hover:bg-accentLight disabled:opacity-50 text-white text-xs font-medium transition-colors"
          >
            {loading ? 'Authenticating...' : 'Sign In'}
          </button>

          {/* Demo credentials */}
          <div className="mt-4 p-3 rounded bg-panel2 border border-line">
            <p className="text-2xs text-slate-600 mb-2 uppercase tracking-wider">Demo credentials</p>
            <div className="space-y-1 text-2xs font-mono text-slate-500">
              <div><span className="text-accent">admin</span> / admin123 <span className="text-slate-600">(Admin)</span></div>
              <div><span className="text-accent">jmartinez</span> / analyst123 <span className="text-slate-600">(Sr. Analyst)</span></div>
              <div><span className="text-accent">akim</span> / analyst123 <span className="text-slate-600">(Analyst)</span></div>
            </div>
          </div>
        </form>

        <p className="text-center text-2xs text-slate-700 mt-3">
          Synthetic data only · All intelligence is fabricated for demonstration
        </p>
      </div>
    </div>
  );
}
