import { apiDelete, apiGet, apiGetBlob, apiPost } from './client.ts';
import { ExportEstimate, ExportJob, ExportRequest } from '../types/export.ts';

export async function estimateExport(
  bookId: number,
  fromIndex: number,
  toIndex: number | null,
  voice: string | null,
): Promise<ExportEstimate> {
  return apiGet<ExportEstimate>(`/books/${bookId}/export/estimate`, {
    from_index: fromIndex,
    to_index: toIndex,
    voice,
  });
}

export async function startExport(bookId: number, request: ExportRequest): Promise<ExportJob> {
  return apiPost<ExportJob>(`/books/${bookId}/export`, request);
}

export async function getExportJob(jobId: string): Promise<ExportJob> {
  return apiGet<ExportJob>(`/exports/${jobId}`);
}

/** Ask the backend to stop a running export; the job then reports status "cancelled". */
export async function cancelExport(jobId: string): Promise<void> {
  await apiDelete(`/exports/${jobId}`);
}

/** The finished file. Fetched with the sign-in token (a plain link could not carry it). */
export async function downloadExport(jobId: string): Promise<Blob> {
  return apiGetBlob(`/exports/${jobId}/file`);
}
