/**
 * Authentication API client.
 * Handles login, logout, and current user retrieval.
 */
const API_BASE = '/api/v1';

export interface LoginResponse {
  access_token: string;
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

const TOKEN_KEY = 'mavericks_token';
const USER_KEY = 'mavericks_user';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
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

export async function login(username: string, password: string): Promise<LoginResponse> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || 'Login failed');
  }
  const data: LoginResponse = await res.json();
  setToken(data.access_token);
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
  if (token) {
    try {
      await fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch {
      // ignore errors on logout
    }
  }
  removeToken();
}

export async function fetchMe(): Promise<UserInfo> {
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: authHeaders(),
  });
  if (res.status === 401) {
    removeToken();
    throw new Error('Session expired');
  }
  if (!res.ok) throw new Error('Failed to fetch user info');
  return res.json();
}
