import React, { useState } from 'react';
import { AmbientPanel } from '../components/Admin/AmbientPanel.tsx';
import { CategoriesPanel } from '../components/Admin/CategoriesPanel.tsx';
import { SystemBooksPanel } from '../components/Admin/SystemBooksPanel.tsx';
import { SystemVoicesPanel } from '../components/Admin/SystemVoicesPanel.tsx';
import { UsersPanel } from '../components/Admin/UsersPanel.tsx';
import { PageHeader } from '../components/common/PageHeader.tsx';

const SECTIONS = [
  { id: 'books', label: 'Sách hệ thống' },
  { id: 'categories', label: 'Thể loại' },
  { id: 'voices', label: 'Giọng hệ thống' },
  { id: 'ambient', label: 'Âm thanh nền' },
  { id: 'users', label: 'Người dùng' },
] as const;
type SectionId = (typeof SECTIONS)[number]['id'];

/** S11 – Quản trị (admin only): system books, categories, system voices and the account list. */
export const AdminPage: React.FC<{ active: boolean }> = ({ active }) => {
  const [section, setSection] = useState<SectionId>('books');
  return (
    <div className="admin-page">
      <PageHeader title="Quản Trị" subtitle="Quản lý nội dung dùng chung cho mọi người." />
      <div className="segmented" role="tablist" aria-label="Mục quản trị">
        {SECTIONS.map((s) => (
          <button key={s.id} role="tab" aria-selected={section === s.id} className={section === s.id ? 'active' : ''} onClick={() => setSection(s.id)}>{s.label}</button>
        ))}
      </div>
      <div className="admin-body">
        {section === 'books' && <SystemBooksPanel active={active} />}
        {section === 'categories' && <CategoriesPanel active={active} />}
        {section === 'voices' && <SystemVoicesPanel active={active} />}
        {section === 'ambient' && <AmbientPanel active={active} />}
        {section === 'users' && <UsersPanel active={active} />}
      </div>
    </div>
  );
};
