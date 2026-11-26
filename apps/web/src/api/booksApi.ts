import { apiDelete, apiGet, apiUpload } from './client.ts';
import { Book, BookSentence, BookUploadResponse } from '../types/book.ts';

export async function listBooks(limit = 500, offset = 0): Promise<Book[]> {
  return apiGet<Book[]>('/books', { limit, offset });
}

export async function deleteBook(bookId: number): Promise<void> {
  await apiDelete(`/books/${bookId}`);
}

export async function uploadBookFile(file: File, title?: string, author?: string): Promise<BookUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  if (title) formData.append('title', title);
  if (author) formData.append('author', author);
  return apiUpload<BookUploadResponse>('/books/ingest', formData);
}

export async function fetchBookSentences(bookId: number): Promise<BookSentence[]> {
  const data = await apiGet<{ sentences: BookSentence[] }>(`/books/${bookId}/sentences`);
  return data.sentences;
}
