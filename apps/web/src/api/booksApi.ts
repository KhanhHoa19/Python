import { apiDelete, apiGet, apiPatch, apiPost, apiPut, apiUpload, Params } from './client.ts';
import { Book, BookSentence, BookUploadResponse, Category, Chapter, ShelfCounts } from '../types/book.ts';

/** What the shelf list can be narrowed by (all filters combine; the backend does the searching). */
export interface ShelfQuery {
  q?: string;
  category?: string | null;
  source?: string;
  status?: string | null;
  sort?: string;
}

function shelfParams(query: ShelfQuery): Params {
  return { q: query.q?.trim() || undefined, category: query.category, source: query.source, status: query.status, sort: query.sort };
}

/** The signed-in user's shelf: own books plus public books they added, with their progress. */
export async function listBooks(query: ShelfQuery = {}, limit = 500): Promise<Book[]> {
  return apiGet<Book[]>('/books', { ...shelfParams(query), limit });
}

export async function fetchShelfCounts(query: ShelfQuery = {}): Promise<ShelfCounts> {
  return apiGet<ShelfCounts>('/books/counts', { ...shelfParams(query), status: undefined, sort: undefined });
}

/** The public catalogue (Khám phá). */
export async function exploreBooks(query: { q?: string; category?: string | null; sort?: string } = {}): Promise<Book[]> {
  return apiGet<Book[]>('/books/explore', { q: query.q?.trim() || undefined, category: query.category, sort: query.sort });
}

export async function fetchCategories(): Promise<Category[]> {
  return apiGet<Category[]>('/categories');
}

export async function addToShelf(bookId: number): Promise<void> {
  await apiPost(`/books/${bookId}/shelf`);
}

export async function removeFromShelf(bookId: number): Promise<void> {
  await apiDelete(`/books/${bookId}/shelf`);
}

export async function setFavorite(bookId: number, isFavorite: boolean): Promise<void> {
  await apiPut(`/books/${bookId}/favorite`, { is_favorite: isFavorite });
}

/** "Đánh dấu đã nghe xong" (completed) or "Nghe lại từ đầu" (unread: back to the first sentence). */
export async function setReadStatus(bookId: number, status: 'completed' | 'unread'): Promise<void> {
  await apiPut(`/books/${bookId}/status`, { status });
}

/** Only the fields that are present change; `category_id: null` clears the category. */
export async function updateBook(bookId: number, changes: { title?: string; author?: string; category_id?: number | null }): Promise<Book> {
  return apiPatch<Book>(`/books/${bookId}`, changes);
}

export async function renameBook(bookId: number, title: string): Promise<Book> {
  return updateBook(bookId, { title });
}

export async function replaceCover(bookId: number, file: File): Promise<Book> {
  const formData = new FormData();
  formData.append('file', file);
  return apiUpload<Book>(`/books/${bookId}/cover`, formData, 'PUT');
}

export async function deleteBook(bookId: number): Promise<void> {
  await apiDelete(`/books/${bookId}`);
}

export interface UploadOptions {
  title?: string;
  author?: string;
  categoryId?: number | null;
  cover?: File | null;
  /** Administrators only: a system book everyone can find in "Khám phá". */
  isPublic?: boolean;
}

export async function uploadBookFile(file: File, options: UploadOptions = {}): Promise<BookUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  if (options.title) formData.append('title', options.title);
  if (options.author) formData.append('author', options.author);
  if (options.categoryId != null) formData.append('category_id', String(options.categoryId));
  if (options.cover) formData.append('cover', options.cover);
  if (options.isPublic) formData.append('is_public', 'true');
  return apiUpload<BookUploadResponse>('/books/ingest', formData);
}

export async function fetchBookSentences(bookId: number): Promise<BookSentence[]> {
  const data = await apiGet<{ sentences: BookSentence[] }>(`/books/${bookId}/sentences`);
  return data.sentences;
}

export async function fetchBookChapters(bookId: number): Promise<Chapter[]> {
  const data = await apiGet<{ chapters: Chapter[] }>(`/books/${bookId}/chapters`);
  return data.chapters;
}
