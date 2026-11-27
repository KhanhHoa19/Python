import React, { useState } from 'react';
import { Pencil } from 'lucide-react';
import { addToShelf } from '../api/booksApi.ts';
import { getRecommendations, savePreferences } from '../api/recommendApi.ts';
import { EmptyState, ErrorState, LoadingState } from '../components/common/StateViews.tsx';
import { PageHeader } from '../components/common/PageHeader.tsx';
import { categoryIcon } from '../components/common/CategoryChips.tsx';
import { ExploreCard } from '../components/Library/ExploreCard.tsx';
import { useApp } from '../context/AppContext.tsx';
import { LibraryData } from '../hooks/useLibrary.ts';
import { useAsyncData } from '../hooks/useAsyncData.ts';
import { DURATION_OPTIONS, describeFilters, toggleSlug } from '../lib/recommend.ts';
import { RecommendedBook } from '../types/recommend.ts';

interface RecommendPageProps {
  active: boolean;
  library: LibraryData;
}

/** S12 – Gợi Ý: books suggested for this reader, with the reasons; filter by mood and length. */
export const RecommendPage: React.FC<RecommendPageProps> = ({ active, library }) => {
  const { categories, openInReader, toast, showError } = useApp();
  const [mood, setMood] = useState<string | null>(null);
  const [durationIndex, setDurationIndex] = useState(0);
  const [editing, setEditing] = useState(false);
  const [picked, setPicked] = useState<string[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);
  const duration = DURATION_OPTIONS[durationIndex];
  const result = useAsyncData(
    () => getRecommendations({ mood, maxMinutes: duration.minutes }),
    [mood, duration.minutes, library.version],
    active,
  );
  const data = result.data;
  const showPicker = !!data && (!data.onboarded || editing);

  const openPicker = () => {
    setPicked(data?.favorite_categories ?? []);
    setEditing(true);
  };

  const save = async (skip: boolean) => {
    try {
      await savePreferences(skip ? [] : picked);
      setEditing(false);
      toast(skip ? 'Đã bỏ qua. Gợi ý sẽ dựa trên lịch sử nghe của bạn.' : 'Đã lưu thể loại yêu thích.');
      result.reload();
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Không lưu được thể loại yêu thích.');
    }
  };

  const add = async (book: RecommendedBook, listen = false) => {
    setBusyId(book.id);
    try {
      await addToShelf(book.id);
      if (listen) openInReader(book.id, book.title);
      else toast(`Đã thêm "${book.title}" vào kệ.`);
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Không thêm được vào kệ.');
    }
    setBusyId(null);
    await library.reload();
  };

  const moodLabel = data?.moods.find((m) => m.id === mood)?.label ?? null;
  const favoriteNames = (data?.favorite_categories ?? []).map((slug) => categories.find((c) => c.slug === slug)?.name ?? slug);

  return (
    <div className="recommend-page">
      <PageHeader title="Gợi ý cho bạn" subtitle="Sách hệ thống hợp với bạn hôm nay, kèm lý do vì sao." />

      {result.loading && !data && <LoadingState />}
      {result.error && <ErrorState message={result.error} onRetry={result.reload} />}

      {showPicker && (
        <section className="panel pref-panel" aria-label="Thể loại yêu thích">
          <h3>{data?.onboarded ? 'Thể loại yêu thích của bạn' : 'Bạn thích thể loại nào?'}</h3>
          <p className="muted">Chọn vài thể loại để mình gợi ý đúng gu. Bạn đổi lại bất cứ lúc nào.</p>
          <div className="chip-row" role="group" aria-label="Chọn thể loại">
            {categories.map((c) => (
              <button key={c.id} className={`chip with-icon ${picked.includes(c.slug) ? 'selected' : ''}`} aria-pressed={picked.includes(c.slug)} onClick={() => setPicked(toggleSlug(picked, c.slug))}>
                {categoryIcon(c.icon)}{c.name}
              </button>
            ))}
          </div>
          <div className="modal-actions">
            {data?.onboarded
              ? <button className="btn-secondary" onClick={() => setEditing(false)}>Hủy</button>
              : <button className="btn-secondary" onClick={() => void save(true)}>Bỏ qua</button>}
            <button className="btn-primary" onClick={() => void save(false)} disabled={picked.length === 0}>Lưu</button>
          </div>
        </section>
      )}

      {data && data.onboarded && !editing && (
        <p className="favorite-line">
          <span className="muted">Thể loại yêu thích:</span>{' '}
          {favoriteNames.length ? <strong>{favoriteNames.join(' · ')}</strong> : <span className="muted">chưa chọn (dựa vào lịch sử nghe)</span>}{' '}
          <button className="btn-ghost small" onClick={openPicker}><Pencil size={14} /> Sửa</button>
        </p>
      )}
      {data && !data.has_history && data.onboarded && <p className="status-text">Bạn chưa nghe nhiều nên gợi ý còn dựa vào thể loại đã chọn và độ phổ biến. Nghe thêm để hệ thống hiểu gu của bạn.</p>}
      {data && data.top_categories.length > 0 && <p className="status-text">Bạn hay nghe: {data.top_categories.map((t) => t.name).join(', ')}.</p>}

      {data && (
        <>
          <div className="chip-row" role="radiogroup" aria-label="Tâm trạng">
            <span className="filter-label">Tâm trạng</span>
            <button className={`chip ${mood === null ? 'selected' : ''}`} role="radio" aria-checked={mood === null} onClick={() => setMood(null)}>Tất cả</button>
            {data.moods.map((m) => (
              <button key={m.id} className={`chip ${mood === m.id ? 'selected' : ''}`} role="radio" aria-checked={mood === m.id} onClick={() => setMood(mood === m.id ? null : m.id)}>{m.label}</button>
            ))}
          </div>
          <div className="chip-row" role="radiogroup" aria-label="Thời lượng">
            <span className="filter-label">Thời lượng</span>
            {DURATION_OPTIONS.map((o, i) => (
              <button key={o.label} className={`chip ${durationIndex === i ? 'selected' : ''}`} role="radio" aria-checked={durationIndex === i} onClick={() => setDurationIndex(i)}>{o.label}</button>
            ))}
          </div>
          {describeFilters(moodLabel, duration) && <p className="muted">{describeFilters(moodLabel, duration)}</p>}

          {data.items.length === 0 ? (
            <EmptyState
              title="Chưa có sách phù hợp."
              hint={mood || duration.minutes ? 'Thử đổi tâm trạng hoặc thời lượng.' : 'Bạn đã có tất cả sách hệ thống trên kệ, hoặc quản trị viên chưa đăng thêm sách.'}
            />
          ) : (
            <div className="books-grid">
              {data.items.map((book) => (
                <ExploreCard key={book.id} book={book} busy={busyId === book.id} reasons={book.reasons} minutes={book.estimated_minutes} onAdd={() => void add(book)} onListen={() => void add(book, true)} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
};
