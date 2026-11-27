import { apiDelete, apiGet, apiGetBlob, apiPatch, apiPost } from './client.ts';
import { EmotionTag, Note, NoteCreatePayload } from '../types/note.ts';

export async function listNotes(filters: { bookId?: number | null; emotionTag?: EmotionTag | null } = {}): Promise<Note[]> {
  return apiGet<Note[]>('/notes', { book_id: filters.bookId, emotion_tag: filters.emotionTag });
}

/** Saving the same passage twice returns the quote that already exists. */
export async function createNote(payload: NoteCreatePayload): Promise<Note> {
  return apiPost<Note>('/notes', payload);
}

/** Only the fields present change; `emotion_tag: null` removes the tag. */
export async function updateNote(noteId: number, changes: { note_text?: string; emotion_tag?: EmotionTag | null }): Promise<Note> {
  return apiPatch<Note>(`/notes/${noteId}`, changes);
}

export async function deleteNote(noteId: number): Promise<void> {
  await apiDelete(`/notes/${noteId}`);
}

export async function fetchNoteAudio(noteId: number): Promise<Blob> {
  return apiGetBlob(`/notes/${noteId}/audio`);
}
