import React from 'react';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  children?: React.ReactNode;
}

/** Title block at the top of every screen; `children` are the screen's main actions. */
export const PageHeader: React.FC<PageHeaderProps> = ({ title, subtitle, children }) => (
  <header className="page-header">
    <div>
      <h1 className="page-title">{title}</h1>
      {subtitle && <p className="page-subtitle">{subtitle}</p>}
    </div>
    {children && <div className="page-actions">{children}</div>}
  </header>
);
