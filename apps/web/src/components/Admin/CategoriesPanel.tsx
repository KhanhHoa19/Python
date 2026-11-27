import React, { useState } from 'react';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import { createCategory, deleteCategory, listAdminCategories, updateCategory } from '../../api/adminApi.ts';
import { fetchCategories } from '../../api/booksApi.ts';
import { useApp } from '../../context/AppContext.tsx';
import { useAsyncData } from '../../hooks/useAsyncData.ts';
import { CATEGORY_ICONS, categoryProblem } from '../../lib/admin.ts';
import { AdminCategory } from '../../types/admin.ts';
import { ConfirmDialog } from '../common/ConfirmDialog.tsx';
import { Modal } from '../common/Modal.tsx';
import { ErrorState, LoadingState } from '../common/StateViews.tsx';

/** Quản trị › Thể loại: add, rename, recolour and delete the categories shown in the sidebar. */
export const CategoriesPanel: React.FC<{ active: boolean }> = ({ active }) => {
  const { toast, showError, refreshCategories } = useApp();
  const categories = useAsyncData(listAdminCategories, [], active);
  const [editing, setEditing] = useState<AdminCategory | 'new' | null>(null);
  const [toDelete, setToDelete] = useState<AdminCategory | null>(null);

  const changed = async () => {
    categories.reload();
    refreshCategories(await fetchCategories());
  };

  const remove = async () => {
    if (!toDelete) return;
    try {
      await deleteCategory(toDelete.id);
      toast(`Đã xóa thể loại "${toDelete.name}"`);
      await changed();
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Không xóa được thể loại.');
    }
    setToDelete(null);
  };

  if (!categories.data && !categories.error) return <LoadingState />; // also before the first request starts (the screen is hidden until opened)
  if (categories.error) return <ErrorState message={categories.error} onRetry={categories.reload} />;

  return (
    <>
      <div className="panel-bar">
        <p className="muted">Thể loại hiện ở thanh bên của mọi người. Xóa một thể loại không xóa sách trong đó.</p>
        <button className="btn-primary" onClick={() => setEditing('new')}><Plus size={16} /> Thêm thể loại</button>
      </div>
      <ul className="studio-list">
        {(categories.data ?? []).map((c) => (
          <li key={c.id} className="studio-row">
            <span className="color-dot" style={{ background: c.color }} aria-hidden="true" />
            <div className="studio-info">
              <span className="studio-name">{c.name}</span>
              <span className="muted">{c.book_count} sách · {c.slug}</span>
            </div>
            <span className="row-actions">
              <button className="btn-ghost small" aria-label={`Sửa thể loại ${c.name}`} onClick={() => setEditing(c)}><Pencil size={14} /></button>
              <button className="btn-danger small" aria-label={`Xóa thể loại ${c.name}`} disabled={c.slug === 'khac'} title={c.slug === 'khac' ? 'Thể loại mặc định, không xóa được' : undefined} onClick={() => setToDelete(c)}><Trash2 size={14} /></button>
            </span>
          </li>
        ))}
      </ul>
      {editing && (
        <CategoryDialog
          category={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={async () => { setEditing(null); await changed(); }}
        />
      )}
      {toDelete && (
        <ConfirmDialog
          title="Xóa thể loại"
          message={`Xóa thể loại "${toDelete.name}"? ${toDelete.book_count} sách trong đó sẽ trở thành chưa phân loại.`}
          confirmLabel="Xóa"
          danger
          onConfirm={remove}
          onCancel={() => setToDelete(null)}
        />
      )}
    </>
  );
};

const CategoryDialog: React.FC<{ category: AdminCategory | null; onClose: () => void; onSaved: () => void }> = ({ category, onClose, onSaved }) => {
  const [name, setName] = useState(category?.name ?? '');
  const [icon, setIcon] = useState(category?.icon ?? 'book-open');
  const [color, setColor] = useState(category?.color ?? '#8a6d3b');
  const [error, setError] = useState<string | null>(null);
  const problem = categoryProblem(name, color);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (problem) return setError(problem);
    try {
      const input = { name: name.trim(), icon, color };
      if (category) await updateCategory(category.id, input);
      else await createCategory(input);
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không lưu được thể loại.');
    }
  };

  return (
    <Modal title={category ? 'Sửa thể loại' : 'Thêm thể loại'} onClose={onClose} width={460}>
      <form className="modal-form" onSubmit={submit}>
        <div className="form-group">
          <label htmlFor="cat-name">Tên thể loại</label>
          <input id="cat-name" value={name} maxLength={80} onChange={(e) => setName(e.target.value)} autoFocus />
        </div>
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="cat-icon">Biểu tượng</label>
            <select id="cat-icon" value={icon} onChange={(e) => setIcon(e.target.value)}>
              {CATEGORY_ICONS.map((i) => <option key={i.value} value={i.value}>{i.label}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="cat-color">Màu (#rrggbb)</label>
            <input id="cat-color" value={color} maxLength={7} onChange={(e) => setColor(e.target.value)} />
          </div>
        </div>
        {error && <p className="status-text error" role="alert">{error}</p>}
        <div className="modal-actions">
          <button type="button" className="btn-secondary" onClick={onClose}>Hủy</button>
          <button type="submit" className="btn-primary" disabled={!!problem}>Lưu</button>
        </div>
      </form>
    </Modal>
  );
};
