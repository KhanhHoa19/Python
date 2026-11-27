import { AuthUser, StoredSession } from '../types/auth.ts';

const KEY = 'audiobook:session';

/** The part of `Storage` we use (lets tests pass a fake; browsers can also refuse storage altogether). */
export type StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

function defaultStorage(): StorageLike | null {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null;
  } catch {
    return null; // storage blocked (private mode, site data disabled)
  }
}

function isUser(value: unknown): value is AuthUser {
  const user = value as Partial<AuthUser> | null;
  return !!user && typeof user.id === 'number' && typeof user.username === 'string' && (user.role === 'admin' || user.role === 'user');
}

/** The saved sign-in, or null if there is none or it is damaged. */
export function loadSession(storage: StorageLike | null = defaultStorage()): StoredSession | null {
  try {
    const raw = storage?.getItem(KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as Partial<StoredSession>;
    return typeof data.token === 'string' && data.token && isUser(data.user) ? { token: data.token, user: data.user } : null;
  } catch {
    return null;
  }
}

export function saveSession(session: StoredSession, storage: StorageLike | null = defaultStorage()): void {
  try {
    storage?.setItem(KEY, JSON.stringify(session));
  } catch {
    /* the sign-in then only lasts until the page is closed */
  }
}

export function clearSession(storage: StorageLike | null = defaultStorage()): void {
  try {
    storage?.removeItem(KEY);
  } catch {
    /* nothing to clear */
  }
}

/** First letter of the display name (or username), for the avatar circle. */
export function avatarLetter(user: Pick<AuthUser, 'full_name' | 'username'>): string {
  const source = (user.full_name || user.username).trim();
  return (source.match(/[\p{L}\p{N}]/u)?.[0] ?? '?').toUpperCase();
}

/** Client-side checks that mirror the backend rules; the backend still has the final say. */
export function checkCredentials(
  mode: 'login' | 'register',
  fields: { username: string; password: string; confirm: string },
): string | null {
  const username = fields.username.trim();
  if (!username) return 'Nhập tên đăng nhập.';
  if (!fields.password) return 'Nhập mật khẩu.';
  if (mode === 'login') return null;
  if (!/^[A-Za-z0-9_.-]{3,32}$/.test(username)) return 'Tên đăng nhập dài 3–32 ký tự, chỉ gồm chữ cái không dấu, số, dấu chấm, gạch dưới hoặc gạch ngang.';
  if (fields.password.length < 8) return 'Mật khẩu cần ít nhất 8 ký tự.';
  if (fields.password !== fields.confirm) return 'Mật khẩu nhập lại không khớp.';
  return null;
}
