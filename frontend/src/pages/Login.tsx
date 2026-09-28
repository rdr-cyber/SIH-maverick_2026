/**
 * Login page for TRILOK TRACE.
 * Authenticates users and redirects to Dashboard on success.
 *
 * Atmosphere: original CSS artwork only — 3D wireframe-globe mood layer,
 * binary/hex rain, circuit traces, 3D brand mark. No bitmaps, no stock art.
 * All animation respects prefers-reduced-motion.
 */
import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { consumeSessionExpiredFlag, login, type LoginResponse } from '../api/auth';

interface Props {
  onLogin: (user: LoginResponse) => void;
}

/* ------------------------------------------------------------------ */
/* 3D wireframe globe — pure CSS-3D sphere (spinning meridians +       */
/* latitude rings), echoing the globe motif in the brand artwork.      */
/* ------------------------------------------------------------------ */
const GLOBE_MERIDIANS = Array.from({ length: 10 }, (_, i) => (i * 180) / 10);
const GLOBE_LATS = [0, 32, 58, -32, -58].map((lat) => {
  const rad = (lat * Math.PI) / 180;
  return { lat, size: 100 * Math.cos(rad), lift: Math.sin(rad) };
});

function Globe3D() {
  return (
    <div className="tt-globe" aria-hidden="true">
      <div className="tt-globe-tilt">
        <div className="tt-globe-spin">
          {GLOBE_MERIDIANS.map((deg) => (
            <span
              key={deg}
              className="tt-globe-ring tt-globe-ring--meridian"
              style={{ transform: `translate(-50%, -50%) rotateY(${deg}deg)` }}
            />
          ))}
          {GLOBE_LATS.map(({ lat, size, lift }) => (
            <span
              key={lat}
              className="tt-globe-ring tt-globe-ring--latitude"
              style={{
                width: `${size}%`,
                height: `${size}%`,
                left: '50%',
                top: `calc(50% - var(--tt-globe-size) * ${(lift / 2).toFixed(4)})`,
                transform: `translate(-50%, -50%) rotateX(${90 - lat}deg)`,
              }}
            />
          ))}
        </div>
        {/* static shading + limb so the sphere reads as a body, not just rings */}
        <span className="tt-globe-core" />
        <span className="tt-globe-limb" />
        <span className="tt-globe-node" style={{ left: '24%', top: '36%', '--delay': '0.8s' } as React.CSSProperties} />
        <span className="tt-globe-node" style={{ left: '76%', top: '64%', '--delay': '2.9s' } as React.CSSProperties} />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Circuit traces — original polyline layout with pulsing nodes.       */
/* ------------------------------------------------------------------ */
function CircuitTraces() {
  const nodes: Array<{ x: number; y: number; delay: string }> = [
    { x: 120, y: 140, delay: '0s' },
    { x: 262, y: 84, delay: '1.2s' },
    { x: 386, y: 210, delay: '2.1s' },
    { x: 540, y: 120, delay: '0.6s' },
    { x: 90, y: 420, delay: '2.8s' },
    { x: 300, y: 520, delay: '1.7s' },
    { x: 620, y: 470, delay: '3.4s' },
    { x: 700, y: 260, delay: '2.4s' },
  ];
  return (
    <svg
      className="tt-circuits"
      viewBox="0 0 800 600"
      preserveAspectRatio="xMidYMid slice"
      aria-hidden="true"
      focusable="false"
    >
      <path className="trace" d="M0 140 H120 V84 H262 V210 H386 V120 H540 V260 H700" />
      <path className="trace" d="M0 420 H90 V470 H300 V520 H620 V470 H800" />
      <path className="trace" d="M386 210 V330 H300 V520" />
      <path className="trace" d="M540 120 V40 H800" />
      <path className="trace" d="M120 140 V300 H40 V420 H90" />
      {nodes.map((n, i) => (
        <circle key={i} className="node" cx={n.x} cy={n.y} r="2.5" style={{ '--delay': n.delay } as React.CSSProperties} />
      ))}
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/* Binary / hex rain — deterministic pseudo-random columns (no Hydration
   mismatch; generated once per mount).                                */
/* ------------------------------------------------------------------ */
function DigitRain() {
  const columns = useRef<string[]>([]);
  if (columns.current.length === 0) {
    let seed = 42;
    const rnd = () => {
      seed = (seed * 1103515245 + 12345) % 2147483648;
      return seed / 2147483648;
    };
    const glyphs = '0101ABCDEF3F9<>#'.split('');
    for (let i = 0; i < 26; i++) {
      const len = 24 + Math.floor(rnd() * 22);
      let col = '';
      for (let j = 0; j < len; j++) {
        col += glyphs[Math.floor(rnd() * glyphs.length)];
        if (rnd() > 0.72) col += ' ';
      }
      columns.current.push(col);
    }
  }

  return (
    <div className="tt-rain" aria-hidden="true">
      {columns.current.map((col, i) => {
        const left = (i / 26) * 100 + (i % 3) * 0.4;
        const dur = 18 + (i % 7) * 4;
        const delay = -(i * 3.1) % 26;
        return (
          <span
            key={i}
            style={{
              position: 'absolute',
              left: `${left}%`,
              top: 0,
              '--dur': `${dur}s`,
              '--delay': `${delay}s`,
            } as React.CSSProperties}
          >
            {col}
          </span>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* 3D brand mark — preserve-3d resting tilt + pointer parallax.        */
/* ------------------------------------------------------------------ */
function Logo3D() {
  const innerRef = useRef<HTMLDivElement>(null);

  const onMove = useCallback((e: React.PointerEvent) => {
    const el = innerRef.current;
    if (!el) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const rect = el.getBoundingClientRect();
    const px = (e.clientX - rect.left) / rect.width - 0.5;
    const py = (e.clientY - rect.top) / rect.height - 0.5;
    el.style.transform = `rotateX(${(6 - py * 14).toFixed(2)}deg) rotateY(${(-9 + px * 16).toFixed(2)}deg)`;
  }, []);

  const onLeave = useCallback(() => {
    const el = innerRef.current;
    if (el) el.style.transform = 'rotateX(6deg) rotateY(-9deg)';
  }, []);

  return (
    <div className="tt-logo-3d relative" onPointerMove={onMove} onPointerLeave={onLeave}>
      <div className="tt-logo-3d-inner" ref={innerRef}>
        <img
          src="/brand/logo-mark.png"
          alt="TRILOK TRACE"
          className="w-24 h-auto mx-auto"
          draggable={false}
        />
      </div>
    </div>
  );
}

export default function Login({ onLogin }: Props) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionNotice, setSessionNotice] = useState('');

  useEffect(() => {
    if (consumeSessionExpiredFlag()) {
      setSessionNotice('Your session expired — please sign in again.');
    }
  }, []);

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
    <div className="tt-login-scene min-h-screen flex items-center justify-center">
      {/* atmosphere layers (decorative, pointer-transparent) */}
      <CircuitTraces />
      <DigitRain />
      <Globe3D />
      <span className="tt-hud tt-hud--tl">information is power</span>
      <span className="tt-hud tt-hud--br">[ trace · analyze · expose ]</span>

      {/* content */}
      <div className="relative w-full max-w-sm px-4 z-10">
        {/* Brand — 3D mark + wordmark */}
        <div className="text-center mb-8">
          <div className="mb-4 flex justify-center">
            <Logo3D />
          </div>
          <h1 className="text-lg font-bold tracking-wide text-slate-200">
            TRILOK <span className="text-accent">TRACE</span>
          </h1>
          <p className="text-xs text-slate-600 mt-1">Investigative Intelligence Platform</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="mp-panel p-6 bg-panel/90 backdrop-blur-sm">
          {sessionNotice && (
            <div className="mb-4 p-2.5 rounded bg-warn/10 border border-warn/30 text-warn text-xs">
              {sessionNotice}
              <button
                type="button"
                onClick={() => setSessionNotice('')}
                className="float-right text-warn/60 hover:text-warn"
                aria-label="Dismiss"
              >
                ×
              </button>
            </div>
          )}
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
          <div className="mt-4 p-3 rounded bg-panel2/80 border border-line">
            <p className="text-2xs text-slate-600 mb-2 uppercase tracking-wider">Demo credentials</p>
            <div className="space-y-1 text-2xs font-mono text-slate-500">
              <div><span className="text-accent">ami</span> / ami43210 <span className="text-slate-600">(Admin)</span></div>
              <div><span className="text-accent">amra</span> / amra4321 <span className="text-slate-600">(Sr. Analyst)</span></div>
              <div><span className="text-accent">tumi</span> / tumi1430 <span className="text-slate-600">(Analyst)</span></div>
            </div>
          </div>
        </form>

        <p className="text-center text-2xs text-slate-700 mt-3">
          Synthetic data only · All intelligence is fabricated for demonstration
        </p>
        <p className="text-center text-2xs text-slate-600 mt-1">
          Built by <span className="text-slate-400 font-medium">Team Mavericks</span>
        </p>
      </div>
    </div>
  );
}
