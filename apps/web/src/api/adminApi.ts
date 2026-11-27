import { apiDelete, apiGet, apiPost, apiPut } from './client.ts';
import { AdminBook, AdminCategory, AdminUser, AdminVoices, CategoryInput } from '../types/admin.ts';
import { Voice } from '../types/voice.ts';

export const listSystemBooks = () => apiGet<AdminBook[]>('/admin/books');
export const setBookPublic = (bookId: number, isPublic: boolean) => apiPut<AdminBook>(`/admin/books/${bookId}/public`, { is_public: isPublic });

export const listAdminCategories = () => apiGet<AdminCategory[]>('/admin/categories');
export const createCategory = (input: CategoryInput) => apiPost<AdminCategory>('/admin/categories', input);
export const updateCategory = (id: number, input: CategoryInput) => apiPut<AdminCategory>(`/admin/categories/${id}`, input);
export const deleteCategory = (id: number) => apiDelete(`/admin/categories/${id}`);

export const listSystemVoices = () => apiGet<AdminVoices>('/admin/voices');
export const setVoicePublic = (voiceId: string, isPublic: boolean) => apiPut<Voice>(`/admin/voices/${encodeURIComponent(voiceId)}/public`, { is_public: isPublic });
export const setDefaultVoice = (voiceId: string) => apiPut<AdminVoices>('/admin/default-voice', { voice_id: voiceId });

export const listUsers = () => apiGet<AdminUser[]>('/admin/users');
