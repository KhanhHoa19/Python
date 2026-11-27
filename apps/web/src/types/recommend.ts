import { Book, Category } from './book.ts';

export interface RecommendedBook extends Book {
  /** Why it was suggested ("Bạn hay nghe Trinh thám"), ready to show. */
  reasons: string[];
  /** At this reader's own listening speed. */
  estimated_minutes: number;
}

export interface Mood {
  id: string;
  label: string;
  categories: string[];
}

export interface TopCategory {
  slug: string;
  name: string;
  weight: number;
}

export interface Recommendations {
  items: RecommendedBook[];
  moods: Mood[];
  /** Slugs of the topic tags the reader chose. */
  favorite_categories: string[];
  /** Has answered (or skipped) the first-time question. */
  onboarded: boolean;
  has_history: boolean;
  top_categories: TopCategory[];
}

export type { Category };
