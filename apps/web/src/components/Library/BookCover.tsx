import React, { useState } from 'react';
import { coverHue, coverInitials } from '../../lib/cover.ts';

interface BookCoverProps {
  title: string;
  /** The cover image; without one (or if it fails to load) a coloured tile with the initials is shown. */
  url?: string | null;
}

export const BookCover: React.FC<BookCoverProps> = ({ title, url }) => {
  const [failed, setFailed] = useState(false);
  if (url && !failed) {
    return (
      <div className="book-cover has-image">
        <img src={url} alt="" loading="lazy" onError={() => setFailed(true)} />
      </div>
    );
  }
  return (
    <div className="book-cover" style={{ '--cover-hue': coverHue(title) } as React.CSSProperties} aria-hidden="true">
      <span className="book-cover-initials">{coverInitials(title)}</span>
    </div>
  );
};
