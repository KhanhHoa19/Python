export interface AmbientTrack {
  id: number;
  name: string;
  /** Relative URL of the audio file, readable without a token. */
  url: string;
  size_bytes: number;
}
