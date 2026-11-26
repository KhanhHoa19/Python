import React from 'react';
import { BarChart2, BookOpen, Headphones, Settings } from 'lucide-react';
import { TabId } from '../../context/AppContext.tsx';

interface NavbarProps {
  current: TabId;
  onSelect: (tab: TabId) => void;
  onSettings: () => void;
}

const TABS: { id: TabId; label: string; icon: React.ReactNode }[] = [
  { id: 'reader', label: 'Phòng Đọc', icon: <Headphones size={18} /> },
  { id: 'library', label: 'Thư Viện & Ghi Chú', icon: <BookOpen size={18} /> },
  { id: 'stats', label: 'Thống Kê', icon: <BarChart2 size={18} /> },
];

export const Navbar: React.FC<NavbarProps> = ({ current, onSelect, onSettings }) => (
  <header className="navbar">
    <div className="navbar-container">
      <div className="navbar-brand">
        <Headphones className="brand-icon" size={24} aria-hidden="true" />
        <span className="brand-name">Audiobook TTS</span>
      </div>
      <nav className="navbar-links" aria-label="Điều hướng chính">
        {TABS.map((tab) => (
          <button key={tab.id} className={`nav-btn ${current === tab.id ? 'active' : ''}`} aria-current={current === tab.id ? 'page' : undefined} onClick={() => onSelect(tab.id)}>
            {tab.icon}
            <span>{tab.label}</span>
          </button>
        ))}
      </nav>
      <button className="nav-btn icon-only" onClick={onSettings} aria-label="Kết nối & Cài đặt" title="Kết nối & Cài đặt">
        <Settings size={18} />
      </button>
    </div>
  </header>
);
