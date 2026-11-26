export interface AnalyticsSummary {
  total_listening_minutes: number;
  total_words_absorbed: number;
  total_sessions: number;
  avg_sentence_response_time_sec: number;
  avg_lan_ping_ms: number;
  avg_tailscale_ping_ms: number;
  recent_sessions_count: number;
}

export interface DailyStat {
  date: string;
  minutes: number;
  words: number;
  sessions: number;
}

export interface Metrics {
  total_calls: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  max_latency_ms: number;
  success_rate: number;
  words_per_minute: number;
}
