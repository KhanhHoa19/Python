import React from 'react';
import { listUsers } from '../../api/adminApi.ts';
import { useAsyncData } from '../../hooks/useAsyncData.ts';
import { ErrorState, LoadingState } from '../common/StateViews.tsx';

function day(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso.replace(' ', 'T'));
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString('vi-VN');
}

/** Quản trị › Người dùng: read-only list of accounts (never their books or notes). */
export const UsersPanel: React.FC<{ active: boolean }> = ({ active }) => {
  const users = useAsyncData(listUsers, [], active);
  if (!users.data && !users.error) return <LoadingState />; // also before the first request starts (the screen is hidden until opened)
  if (users.error) return <ErrorState message={users.error} onRetry={users.reload} />;
  return (
    <>
      <p className="muted">Chỉ xem. Quản trị viên không đọc được sách hay ghi chú riêng của người dùng.</p>
      <div className="table-wrap">
        <table className="data-table">
          <thead><tr><th>Tài khoản</th><th>Họ tên</th><th>Vai trò</th><th>Ngày tạo</th><th>Sách</th><th>Giọng</th></tr></thead>
          <tbody>
            {(users.data ?? []).map((u) => (
              <tr key={u.id}>
                <td>{u.username}</td>
                <td>{u.full_name}</td>
                <td><span className={`role-badge ${u.role}`}>{u.role === 'admin' ? 'Admin' : 'Member'}</span></td>
                <td>{day(u.created_at)}</td>
                <td>{u.book_count}</td>
                <td>{u.voice_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
};
