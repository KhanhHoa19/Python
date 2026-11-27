import { apiDelete, apiGet, apiPatch, apiUpload } from './client.ts';
import { AmbientTrack } from '../types/ambient.ts';

/** The background sounds every signed-in user may choose from. */
export const listAmbient = () => apiGet<AmbientTrack[]>('/ambient');

// Administrators manage the library (Quản Trị › Âm thanh nền).
export function addAmbient(name: string, file: File): Promise<AmbientTrack> {
  const data = new FormData();
  data.append('name', name);
  data.append('file', file);
  return apiUpload<AmbientTrack>('/admin/ambient', data);
}
export const renameAmbient = (id: number, name: string) => apiPatch<AmbientTrack>(`/admin/ambient/${id}`, { name });
export const deleteAmbient = (id: number) => apiDelete(`/admin/ambient/${id}`);
