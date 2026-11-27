import React from 'react';
import { BarChart2, BookOpen, Compass, Headphones, LogOut, Mic2, Monitor, Moon, Quote, Settings, ShieldCheck, Sparkles, Sun } from 'lucide-react';
import { TabId } from '../../context/AppContext.tsx';
import { ThemePreference } from '../../hooks/useTheme.ts';
import { avatarLetter } from '../../lib/session.ts';
import { AuthUser } from '../../types/auth.ts';

interface SidebarProps {
  current: TabId;
  user: AuthUser;
  onLogout: () => void;
  theme: ThemePreference;
  onSelect: (tab: TabId) => void;
  onSettings: () => void;
  onToggleTheme: () => void;
}

const TABS: { id: TabId; label: string; icon: React.ReactNode }[] = [
  { id: 'reader', label: 'Phòng Đọc', icon: <Headphones size={19} /> },
  { id: 'explore', label: 'Khám Phá', icon: <Compass size={19} /> },
  { id: 'recommend', label: 'Gợi Ý', icon: <Sparkles size={19} /> },
  { id: 'library', label: 'Kệ Sách Của Tôi', icon: <BookOpen size={19} /> },
  { id: 'quotes', label: 'Trích Dẫn Yêu Thích', icon: <Quote size={19} /> },
  { id: 'stats', label: 'Thống Kê', icon: <BarChart2 size={19} /> },
  { id: 'voices', label: 'Kho Giọng Đọc', icon: <Mic2 size={19} /> },
];

const ADMIN_TAB = { id: 'admin' as TabId, label: 'Quản Trị', icon: <ShieldCheck size={19} /> };

const THEME_LABEL: Record<ThemePreference, { text: string; short: string; icon: React.ReactNode }> = {
  system: { text: 'Giao diện: theo hệ thống', short: 'Tự động', icon: <Monitor size={19} /> },
  light: { text: 'Giao diện: sáng', short: 'Sáng', icon: <Sun size={19} /> },
  dark: { text: 'Giao diện: tối', short: 'Tối', icon: <Moon size={19} /> },
};

/** Left navigation (bottom bar on narrow screens). New screens are added to TABS. */
export const Sidebar: React.FC<SidebarProps> = ({ current, user, onLogout, theme, onSelect, onSettings, onToggleTheme }) => (
  <aside className="sidebar">
    <div className="brand">
      <span className="brand-mark" aria-hidden="true"><Headphones size={20} /></span>
      <span className="brand-name">Audiobook<span className="brand-accent"> TTS</span></span>
    </div>

    <div className="account">
      <span className="avatar" aria-hidden="true">{avatarLetter(user)}</span>
      <span className="account-text">
        <span className="account-name">{user.full_name || user.username}</span>
        <span className={`role-badge ${user.role}`}>{user.role === 'admin' ? 'Admin' : 'Member'}</span>
      </span>
    </div>

    <nav className="nav-list" aria-label="Điều hướng chính">
      {(user.role === 'admin' ? [...TABS, ADMIN_TAB] : TABS).map((tab) => (
        <button key={tab.id} className={`nav-item ${current === tab.id ? 'active' : ''}`} aria-current={current === tab.id ? 'page' : undefined} onClick={() => onSelect(tab.id)}>
          {tab.icon}
          <span>{tab.label}</span>
        </button>
      ))}
    </nav>

    <div className="nav-footer">
      <p className="nav-section">Công cụ</p>
      <button className="nav-item" onClick={onSettings}><Settings size={19} /><span>Kết nối & Cài đặt</span></button>
      <button className="nav-item" onClick={onToggleTheme} aria-label={THEME_LABEL[theme].text} title={THEME_LABEL[theme].text}>
        {THEME_LABEL[theme].icon}
        <span>{THEME_LABEL[theme].short}</span>
      </button>
      <button className="nav-item" onClick={onLogout}><LogOut size={19} /><span>Đăng xuất</span></button>
    </div>
  </aside>
);
