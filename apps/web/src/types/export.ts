export interface ExportRequest {
  from_index: number;
  dialogue_voice?: string | null;
  to_index?: number | null;
  voice?: string | null;
  speed?: number;
  format?: 'wav' | 'mp3' | null;
}

export interface ExportEstimate {
  sentences: number;
  words: number;
  estimated_minutes: number;
  chars_to_synthesize: number;
  chars_cached: number;
  daily_limit: number;
  chars_used_today: number;
}

export interface ExportJob {
  job_id: string;
  status: 'running' | 'done' | 'failed' | 'cancelled';
  done: number;
  total: number;
  file_name: string | null;
  error: string | null;
}
