import { apiGet, apiPost } from './client.ts';
import { AuthUser, DemoAccount, TokenResponse } from '../types/auth.ts';

export async function login(username: string, password: string): Promise<TokenResponse> {
  return apiPost<TokenResponse>('/auth/login', { username, password });
}

export async function register(username: string, password: string, fullName: string): Promise<TokenResponse> {
  return apiPost<TokenResponse>('/auth/register', { username, password, full_name: fullName });
}

export async function fetchMe(): Promise<AuthUser> {
  return apiGet<AuthUser>('/auth/me');
}

/** Empty unless the backend runs with DEV_QUICK_LOGIN=true. A failure just means "no quick-login boxes". */
export async function fetchDemoAccounts(): Promise<DemoAccount[]> {
  return apiGet<DemoAccount[]>('/auth/demo-accounts').catch(() => []);
}
