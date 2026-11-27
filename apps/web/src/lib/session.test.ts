import { describe, expect, it } from 'vitest';
import { avatarLetter, checkCredentials, clearSession, loadSession, saveSession, StorageLike } from './session.ts';
import { StoredSession } from '../types/auth.ts';

function fakeStorage(initial: Record<string, string> = {}): StorageLike & { data: Record<string, string> } {
  const data = { ...initial };
  return {
    data,
    getItem: (k) => (k in data ? data[k] : null),
    setItem: (k, v) => void (data[k] = v),
    removeItem: (k) => void delete data[k],
  };
}
const session: StoredSession = { token: 'abc.def.ghi', user: { id: 3, username: 'lan', full_name: 'Lan Nguyễn', role: 'user' } };

describe('session storage', () => {
  it('saves, loads and clears a session', () => {
    const storage = fakeStorage();
    expect(loadSession(storage)).toBeNull();
    saveSession(session, storage);
    expect(loadSession(storage)).toEqual(session);
    clearSession(storage);
    expect(loadSession(storage)).toBeNull();
  });
  it('ignores damaged or incomplete data', () => {
    for (const raw of ['not json', '{}', '{"token":"","user":{}}', JSON.stringify({ token: 't', user: { id: 1, username: 'x', role: 'root' } })]) {
      expect(loadSession(fakeStorage({ 'audiobook:session': raw }))).toBeNull();
    }
  });
  it('does not fail when storage is unavailable or throws', () => {
    expect(loadSession(null)).toBeNull();
    const broken: StorageLike = { getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); }, removeItem: () => { throw new Error('blocked'); } };
    expect(loadSession(broken)).toBeNull();
    expect(() => saveSession(session, broken)).not.toThrow();
    expect(() => clearSession(broken)).not.toThrow();
  });
});

describe('avatar letter', () => {
  it('uses the display name, then the username, keeping Vietnamese letters', () => {
    expect(avatarLetter({ full_name: 'đức anh', username: 'x' })).toBe('Đ');
    expect(avatarLetter({ full_name: '', username: 'minh' })).toBe('M');
    expect(avatarLetter({ full_name: '  ', username: '' })).toBe('?');
  });
});

describe('credential checks', () => {
  const ok = { username: 'lan.nguyen', password: 'correct horse', confirm: 'correct horse' };
  it('login only needs both fields', () => {
    expect(checkCredentials('login', { username: ' a ', password: 'x', confirm: '' })).toBeNull();
    expect(checkCredentials('login', { username: '', password: 'x', confirm: '' })).not.toBeNull();
    expect(checkCredentials('login', { username: 'a', password: '', confirm: '' })).not.toBeNull();
  });
  it('registration follows the backend rules', () => {
    expect(checkCredentials('register', ok)).toBeNull();
    expect(checkCredentials('register', { ...ok, username: 'ab' })).toMatch(/3–32/);
    expect(checkCredentials('register', { ...ok, username: 'có dấu' })).toMatch(/3–32/);
    expect(checkCredentials('register', { ...ok, password: 'short', confirm: 'short' })).toMatch(/8 ký tự/);
    expect(checkCredentials('register', { ...ok, confirm: 'different pass' })).toMatch(/không khớp/);
  });
});
