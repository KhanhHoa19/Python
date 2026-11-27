import { AdminBook } from '../types/admin.ts';

/** Icons a category may use (the sidebar knows how to draw each of them). */
export const CATEGORY_ICONS = [
  { value: 'book-open', label: 'Sách mở' },
  { value: 'sprout', label: 'Mầm cây' },
  { value: 'cpu', label: 'Công nghệ' },
  { value: 'trending-up', label: 'Biểu đồ' },
  { value: 'feather', label: 'Lông vũ' },
  { value: 'layers', label: 'Lớp' },
  { value: 'search', label: 'Kính lúp' },
  { value: 'flask-conical', label: 'Khoa học' },
  { value: 'landmark', label: 'Di tích' },
  { value: 'brain', label: 'Bộ não' },
  { value: 'lightbulb', label: 'Bóng đèn' },
  { value: 'heart', label: 'Trái tim' },
  { value: 'ghost', label: 'Bóng ma' },
  { value: 'compass', label: 'La bàn' },
  { value: 'baby', label: 'Trẻ em' },
] as const;

export const HEX_COLOR = /^#[0-9a-fA-F]{6}$/;

/** Public books first, then the admin's private ones that could still be published; each group by title. */
export function sortSystemBooks(books: AdminBook[]): AdminBook[] {
  return [...books].sort((a, b) => Number(b.is_public) - Number(a.is_public) || a.title.localeCompare(b.title, 'vi'));
}

/** Why a category form cannot be saved yet (null = fine). */
export function categoryProblem(name: string, color: string): string | null {
  if (!name.trim()) return 'Hãy nhập tên thể loại.';
  if (!HEX_COLOR.test(color)) return 'Màu phải có dạng #a1b2c3.';
  return null;
}

/** "1,9 MB" / "320 KB" for a file size. */
export function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1).replace('.', ',')} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}
