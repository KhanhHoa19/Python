export interface NetworkCheck {
  name: string;
  ok: boolean;
  detail: string;
}

export interface NetworkHealth {
  provider: string;
  host: string | null;
  skipped: boolean;
  checks: NetworkCheck[];
}

export interface VerifyResult {
  provider: string;
  ok: boolean;
  error: string | null;
}
