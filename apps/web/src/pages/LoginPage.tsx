import React, { useEffect, useState } from 'react';
import { Headphones, Loader2 } from 'lucide-react';
import { fetchDemoAccounts, login, register } from '../api/authApi.ts';
import { checkCredentials } from '../lib/session.ts';
import { avatarLetter } from '../lib/session.ts';
import { DemoAccount, TokenResponse } from '../types/auth.ts';

interface LoginPageProps {
  /** Why the user is here again ("session expired"), if they were signed out. */
  notice: string | null;
  onAuthenticated: (response: TokenResponse) => void;
}

/** S09 – Đăng nhập & Đăng ký. */
export const LoginPage: React.FC<LoginPageProps> = ({ notice, onAuthenticated }) => {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [demo, setDemo] = useState<DemoAccount[]>([]);

  useEffect(() => {
    let active = true;
    void fetchDemoAccounts().then((accounts) => active && setDemo(accounts));
    return () => {
      active = false;
    };
  }, []);

  /** Development shortcut: sign in as one of the ready-made accounts with a single click. */
  const quickLogin = async (account: DemoAccount) => {
    setBusy(true);
    setError(null);
    try {
      onAuthenticated(await login(account.username, account.password));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không đăng nhập được.');
      setBusy(false);
    }
  };

  const switchMode = (next: 'login' | 'register') => {
    setMode(next);
    setError(null);
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const problem = checkCredentials(mode, { username, password, confirm });
    if (problem) return setError(problem);
    setBusy(true);
    setError(null);
    try {
      const response = mode === 'login' ? await login(username.trim(), password) : await register(username.trim(), password, fullName.trim());
      onAuthenticated(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không đăng nhập được.');
      setBusy(false);
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="auth-title">
        <div className="brand auth-brand">
          <span className="brand-mark" aria-hidden="true"><Headphones size={20} /></span>
          <span className="brand-name">Audiobook<span className="brand-accent"> TTS</span></span>
        </div>
        <h1 id="auth-title" className="auth-title">{mode === 'login' ? 'Chào mừng trở lại' : 'Tạo tài khoản'}</h1>
        <p className="muted">{mode === 'login' ? 'Đăng nhập để nghe tiếp từ chỗ bạn dừng.' : 'Mỗi người có thư viện, tiến độ và giọng đọc riêng.'}</p>

        <div className="segmented" role="tablist" aria-label="Đăng nhập hoặc đăng ký">
          <button role="tab" aria-selected={mode === 'login'} className={mode === 'login' ? 'active' : ''} onClick={() => switchMode('login')} type="button">Đăng nhập</button>
          <button role="tab" aria-selected={mode === 'register'} className={mode === 'register' ? 'active' : ''} onClick={() => switchMode('register')} type="button">Đăng ký</button>
        </div>

        {notice && !error && <p className="status-text warn" role="status">{notice}</p>}

        <form className="modal-form" onSubmit={submit} noValidate>
          <div className="form-group">
            <label htmlFor="auth-username">Tên đăng nhập</label>
            <input id="auth-username" autoComplete="username" autoFocus value={username} onChange={(e) => setUsername(e.target.value)} />
          </div>
          {mode === 'register' && (
            <div className="form-group">
              <label htmlFor="auth-fullname">Tên hiển thị <span className="muted">(không bắt buộc)</span></label>
              <input id="auth-fullname" autoComplete="name" maxLength={100} value={fullName} onChange={(e) => setFullName(e.target.value)} />
            </div>
          )}
          <div className="form-group">
            <label htmlFor="auth-password">Mật khẩu</label>
            <input id="auth-password" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          {mode === 'register' && (
            <div className="form-group">
              <label htmlFor="auth-confirm">Nhập lại mật khẩu</label>
              <input id="auth-confirm" type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
            </div>
          )}
          {error && <p className="status-text error" role="alert">{error}</p>}
          <button className="btn-primary auth-submit" type="submit" disabled={busy}>
            {busy && <Loader2 size={16} className="spin" />} {mode === 'login' ? 'Đăng nhập' : 'Tạo tài khoản'}
          </button>
        </form>
      </section>

      {demo.length > 0 && (
        <section className="demo-accounts" aria-label="Tài khoản thử">
          <p className="demo-title">Tài khoản thử <span className="muted">· chế độ phát triển, bấm để đăng nhập</span></p>
          <div className="demo-grid">
            {demo.map((account) => (
              <button key={account.username} className="demo-card" onClick={() => void quickLogin(account)} disabled={busy}>
                <span className="avatar" aria-hidden="true">{avatarLetter(account)}</span>
                <span className="demo-text">
                  <span className="demo-name">{account.full_name}</span>
                  <span className={`role-badge ${account.role}`}>{account.role === 'admin' ? 'Admin' : 'Member'}</span>
                  <code>{account.username}</code>
                  <code>{account.password}</code>
                </span>
              </button>
            ))}
          </div>
        </section>
      )}
    </main>
  );
};
