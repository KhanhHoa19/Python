export type Role = 'admin' | 'user';

export interface AuthUser {
  id: number;
  username: string;
  full_name: string;
  role: Role;
}

/** POST /api/auth/login and /register. */
export interface TokenResponse {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
  user: AuthUser;
}

/** One of the ready-made accounts of development mode (GET /api/auth/demo-accounts). */
export interface DemoAccount {
  username: string;
  password: string;
  full_name: string;
  role: Role;
}

export interface StoredSession {
  token: string;
  user: AuthUser;
}
