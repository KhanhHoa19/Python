import { useCallback, useEffect, useState } from 'react';
import { fetchMe } from '../api/authApi.ts';
import { onUnauthorized, setAuthToken } from '../api/client.ts';
import { clearSession, loadSession, saveSession } from '../lib/session.ts';
import { StoredSession, TokenResponse } from '../types/auth.ts';

function initialSession(): StoredSession | null {
  const saved = loadSession();
  setAuthToken(saved?.token ?? null); // before the first request of the page
  return saved;
}

/** Who is signed in. The token lives in localStorage; an expired or revoked one sends the user back to the form. */
export function useAuth() {
  const [session, setSession] = useState<StoredSession | null>(initialSession);
  const [notice, setNotice] = useState<string | null>(null);

  const signOut = useCallback((message: string | null = null) => {
    setAuthToken(null);
    clearSession();
    setSession(null);
    setNotice(message);
  }, []);

  const signIn = useCallback((response: TokenResponse) => {
    const next: StoredSession = { token: response.access_token, user: response.user };
    setAuthToken(next.token);
    saveSession(next);
    setSession(next);
    setNotice(null);
  }, []);

  useEffect(() => {
    onUnauthorized(() => signOut('Phiên đăng nhập đã hết hạn. Hãy đăng nhập lại.'));
    return () => onUnauthorized(null);
  }, [signOut]);

  // A saved session may belong to an account that no longer exists (or a token signed with an old secret).
  const savedToken = session?.token;
  useEffect(() => {
    if (!savedToken) return;
    fetchMe()
      .then((user) => setSession((current) => (current && current.token === savedToken ? { ...current, user } : current)))
      .catch(() => undefined); // 401 is handled by onUnauthorized; a network error keeps the session
  }, [savedToken]);

  return { session, notice, signIn, signOut };
}
