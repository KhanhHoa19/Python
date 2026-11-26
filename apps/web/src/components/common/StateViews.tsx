import React from 'react';

export const LoadingState: React.FC<{ text?: string }> = ({ text = 'Đang tải…' }) => (
  <div className="loading-state" role="status">
    <div className="spinner" />
    <p>{text}</p>
  </div>
);

export const EmptyState: React.FC<{ title: string; hint?: string; children?: React.ReactNode }> = ({ title, hint, children }) => (
  <div className="empty-state">
    <h3>{title}</h3>
    {hint && <p>{hint}</p>}
    {children}
  </div>
);

export const ErrorState: React.FC<{ message: string; onRetry?: () => void }> = ({ message, onRetry }) => (
  <div className="error-state" role="alert">
    <p>{message}</p>
    {onRetry && <button className="btn-secondary" onClick={onRetry}>Thử lại</button>}
  </div>
);
