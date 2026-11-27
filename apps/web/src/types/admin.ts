import { Category } from './book.ts';
import { Voice } from './voice.ts';

export interface AdminBook {
  id: number;
  title: string;
  author: string;
  total_chapters: number;
  is_public: boolean;
  /** Uploaded by the signed-in admin: only those can be published. */
  is_mine: boolean;
  category: Category | null;
  cover_url: string | null;
  /** How many readers keep the book on their shelf. */
  shelf_count: number;
}

export interface AdminCategory extends Category {
  book_count: number;
}

export interface CategoryInput {
  name: string;
  icon: string;
  color: string;
}

export interface AdminVoices {
  voices: Voice[];
  default_voice: string;
}

export interface AdminUser {
  id: number;
  username: string;
  full_name: string;
  role: 'admin' | 'user';
  created_at: string | null;
  book_count: number;
  voice_count: number;
}
