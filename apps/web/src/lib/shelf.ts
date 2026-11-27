import { ShelfCounts } from '../types/book.ts';

/** The tabs of "Kệ sách của tôi" (the quotes have their own screen). */
export type ShelfTab = 'reading' | 'unread' | 'completed' | 'favorite';

export const SHELF_TABS: { id: ShelfTab; label: string }[] = [
  { id: 'reading', label: 'Đang nghe dở' },
  { id: 'unread', label: 'Chưa nghe' },
  { id: 'completed', label: 'Đã hoàn thành' },
  { id: 'favorite', label: 'Yêu thích' },
];

export const SOURCE_OPTIONS = [
  { value: 'all', label: 'Tất cả' },
  { value: 'system', label: 'Sách hệ thống' },
  { value: 'mine', label: 'Sách của tôi' },
] as const;
export type SourceValue = (typeof SOURCE_OPTIONS)[number]['value'];

export const SORT_OPTIONS = [
  { value: 'recent', label: 'Đọc gần đây' },
  { value: 'title', label: 'Tên A→Z' },
  { value: 'newest', label: 'Ngày thêm' },
  { value: 'progress', label: 'Tiến độ' },
] as const;
export type SortValue = (typeof SORT_OPTIONS)[number]['value'];

/** The tab to open first: the first one that has books, else "Đang nghe dở". */
export function pickInitialTab(counts: ShelfCounts): ShelfTab {
  return SHELF_TABS.find((tab) => counts[tab.id] > 0)?.id ?? 'reading';
}

/** Label for the primary button of a book card. */
export function playLabel(status: 'unread' | 'reading' | 'completed' | undefined): string {
  if (status === 'reading') return 'Nghe tiếp';
  if (status === 'completed') return 'Nghe lại';
  return 'Bắt đầu nghe';
}
