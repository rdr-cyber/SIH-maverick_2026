/**
 * Authentication API client.
 * Handles login, logout, and current user retrieval.
 */
const API_BASE = '/api/v1';

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  username: string;
  role: string;
  full_name: string;
}

export interface UserInfo {
  username: string;
  role: string;
  full_name: string;
  email: string;
  is_active: boolean;
}

const TOKEN_KEY = 'trilok_trace_token';
const USER_KEY = 'trilok_trace_user';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

/**
 * Session is no longer valid — token expired, revoked, or the backend
 * restarted with a fresh JWT secret.  Clear credentials and reload so the
 * router renders Sign In.  Guarded so concurrent 401s trigger one reload.
 */
let sessionExpiredHandled = false;
export function sessionExpired(): void {
  if (sessionExpiredHandled) return;
  sessionExpiredHandled = true;
  try {
    sessionStorage.setItem('trilok_session_expired', '1');
  } catch {
    /* storage unavailable — banner is best-effort */
  }
  removeToken();
  window.location.assign("/");
}

/** True once per expiry: the login page consumes and clears this flag. */
export function consumeSessionExpiredFlag(): boolean {
  try {
    if (sessionStorage.getItem('trilok_session_expired') === '1') {
      sessionStorage.removeItem('trilok_session_expired');
      return true;
    }
  } catch {
    /* ignore */
  }
  return false;
}

// ---- refresh-token storage -------------------------------------------------
const REFRESH_KEY = 'trilok_trace_refresh';

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function setRefreshToken(token: string): void {
  localStorage.setItem(REFRESH_KEY, token);
}

/**
 * Exchange the refresh token for a fresh JWT pair (rotation endpoint).
 * Returns true when a fresh pair was stored.
 *
 * Deduplicated: the backend ROTATES refresh tokens (each is single-use), so
 * two concurrent 401s must share ONE refresh call — a second parallel call
 * would replay the just-revoked token and log the user out mid-recovery.
 */
let refreshInFlight: Promise<boolean> | null = null;

export async function refreshSession(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) return false;
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: getRefreshToken() }),
        });
        if (!res.ok) {
          // Refresh rejected (revoked/expired/rotated) — session truly dead.
          sessionExpired();
          return false;
        }
        const data: { access_token: string; refresh_token: string } = await res.json();
        setToken(data.access_token);
        setRefreshToken(data.refresh_token);
        return true;
      } catch {
        // Network error — not an expiry; let the caller surface the original error.
        return false;
      } finally {
        // Release the slot once every concurrent awaiter has been handed the
        // same result, so a genuine later expiry can refresh again.
        setTimeout(() => {
          refreshInFlight = null;
        }, 0);
      }
    })();
  }
  return refreshInFlight;
}

export function getStoredUser(): UserInfo | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function setStoredUser(user: UserInfo): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Authenticated fetch shared by all API clients.
 * On a 401 it silently rotates the JWT pair via /auth/refresh and retries the
 * original request once; if the refresh itself fails the caller receives the
 * 401 response and decides how to surface it (sessionExpired()).
 */
export async function authFetch(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  const doFetch = () =>
    fetch(url, {
      ...init,
      headers: { "Content-Type": "application/json", ...authHeaders(), ...init?.headers },
    });
  let res = await doFetch();
  if (res.status === 401 && (await refreshSession())) {
    res = await doFetch();
  }
  return res;
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    if (res.status === 429) {
      throw new Error('Too many attempts — wait a minute and try again');
    }
    const body = await res.json().catch(() => ({}));
    const detail = body?.detail ?? body?.error?.message;
    throw new Error(detail || 'Login failed');
  }
  const data: LoginResponse = await res.json();
  setToken(data.access_token);
  setRefreshToken(data.refresh_token);
  setStoredUser({
    username: data.username,
    role: data.role,
    full_name: data.full_name,
    email: '',
    is_active: true,
  });
  return data;
}

export async function logout(): Promise<void> {
  const token = getToken();
  const refresh = getRefreshToken();
  if (token) {
    try {
      await fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(refresh ? { refresh_token: refresh } : {}),
      });
    } catch {
      // ignore errors on logout
    }
  }
  removeToken();
}

export async function fetchMe(): Promise<UserInfo> {
  const res = await authFetch('/auth/me');
  if (res.status === 401) {
    removeToken();
    throw new Error('Session expired');
  }
  if (!res.ok) throw new Error('Failed to fetch user info');
  return res.json();
}
