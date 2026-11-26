import { apiGet, apiPost, fileUrl } from './client.ts';
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

export function exportFileUrl(jobId: string): string {
  return fileUrl(`/exports/${jobId}/file`);
}
