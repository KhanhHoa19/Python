import { apiDelete, apiGet, apiGetBlob, apiPatch, apiPost } from './client.ts';
import { Note, NoteCreatePayload } from '../types/note.ts';

export async function listNotes(bookId?: number): Promise<Note[]> {
  return apiGet<Note[]>('/notes', { book_id: bookId });
}

export async function createNote(payload: NoteCreatePayload): Promise<Note> {
  return apiPost<Note>('/notes', payload);
}

export async function updateNote(noteId: number, noteText: string): Promise<Note> {
  return apiPatch<Note>(`/notes/${noteId}`, { note_text: noteText });
}

export async function deleteNote(noteId: number): Promise<void> {
  await apiDelete(`/notes/${noteId}`);
}

export async function fetchNoteAudio(noteId: number): Promise<Blob> {
  return apiGetBlob(`/notes/${noteId}/audio`);
}
