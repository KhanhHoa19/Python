import React from 'react';
import { Baby, BookOpen, Brain, Compass, Cpu, Feather, FlaskConical, Ghost, Heart, Landmark, Layers, Lightbulb, Search, Sprout, TrendingUp } from 'lucide-react';
import { Category } from '../../types/book.ts';

/** Icon per category (names come from the backend; unknown ones fall back to a book). */
const ICONS: Record<string, React.ReactNode> = {
  'book-open': <BookOpen size={15} />,
  search: <Search size={15} />,
  'flask-conical': <FlaskConical size={15} />,
  landmark: <Landmark size={15} />,
  sprout: <Sprout size={15} />,
  brain: <Brain size={15} />,
  lightbulb: <Lightbulb size={15} />,
  cpu: <Cpu size={15} />,
  'trending-up': <TrendingUp size={15} />,
  heart: <Heart size={15} />,
  ghost: <Ghost size={15} />,
  compass: <Compass size={15} />,
  baby: <Baby size={15} />,
  feather: <Feather size={15} />,
  layers: <Layers size={15} />,
};

export const categoryIcon = (name: string): React.ReactNode => ICONS[name] ?? <BookOpen size={15} />;

interface CategoryChipsProps {
  categories: Category[];
  /** Slug of the chosen tag, or null for all. */
  selected: string | null;
  onSelect: (slug: string | null) => void;
}

/** The topic tags of the library ("Trinh thám", "Khoa học"…): click one to filter, click it again to clear. */
export const CategoryChips: React.FC<CategoryChipsProps> = ({ categories, selected, onSelect }) => {
  if (categories.length === 0) return null;
  return (
    <div className="chip-row category-chips" role="group" aria-label="Chủ đề sách">
      <button className={`chip ${selected === null ? 'selected' : ''}`} aria-pressed={selected === null} onClick={() => onSelect(null)}>Tất cả</button>
      {categories.map((c) => (
        <button key={c.id} className={`chip with-icon ${selected === c.slug ? 'selected' : ''}`} aria-pressed={selected === c.slug} onClick={() => onSelect(selected === c.slug ? null : c.slug)}>
          {categoryIcon(c.icon)}{c.name}
        </button>
      ))}
    </div>
  );
};
