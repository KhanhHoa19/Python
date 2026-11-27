import React from 'react';
import { Check, Globe, Lock, Play, Star } from 'lucide-react';
import { listSystemVoices, setDefaultVoice, setVoicePublic } from '../../api/adminApi.ts';
import { fetchVoicePreview } from '../../api/voicesApi.ts';
import { useApp } from '../../context/AppContext.tsx';
import { useAsyncData } from '../../hooks/useAsyncData.ts';
import { useBlobAudio } from '../../hooks/useBlobAudio.ts';
import { Voice } from '../../types/voice.ts';
import { EmptyState, ErrorState, LoadingState } from '../common/StateViews.tsx';

/** Quản trị › Giọng hệ thống: share your cloned voices with everyone and choose the voice new readers start with. */
export const SystemVoicesPanel: React.FC<{ active: boolean }> = ({ active }) => {
  const { toast, showError, refreshVoices } = useApp();
  const data = useAsyncData(listSystemVoices, [], active);
  const { playBlob } = useBlobAudio();

  const run = async (action: () => Promise<unknown>, done: string) => {
    try {
      await action();
      toast(done);
      data.reload();
      await refreshVoices();
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Không thực hiện được.');
    }
  };

  const preview = async (voice: Voice) => {
    try {
      await playBlob(await fetchVoicePreview(voice.voice_id));
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Không nghe thử được.');
    }
  };

  if (!data.data && !data.error) return <LoadingState />; // also before the first request starts (the screen is hidden until opened)
  if (data.error) return <ErrorState message={data.error} onRetry={data.reload} />;
  const voices = data.data?.voices ?? [];
  const defaultId = data.data?.default_voice ?? '';
  if (voices.length === 0) return <EmptyState title="Chưa có giọng nào để chia sẻ." hint="Tạo một giọng ở Kho Giọng Đọc, rồi quay lại đây để công khai." />;

  return (
    <>
      <p className="muted">Giọng công khai ai cũng nghe và dùng được. Giọng mặc định hệ thống áp dụng cho người chưa tự chọn giọng. Giọng riêng của người khác không hiện ở đây.</p>
      <ul className="studio-list">
        {voices.map((voice) => (
          <li key={voice.voice_id} className="studio-row">
            <div className="studio-info">
              <span className="studio-name">{voice.display_name}</span>
              <span className="chip-row">
                {voice.is_public ? <span className="chip static selected"><Globe size={12} /> Công khai</span> : <span className="chip static"><Lock size={12} /> Riêng tư</span>}
                {voice.voice_id === defaultId && <span className="chip static selected"><Check size={12} /> Mặc định hệ thống</span>}
              </span>
            </div>
            <span className="row-actions">
              <button className="btn-secondary small" onClick={() => preview(voice)}><Play size={14} /> Nghe thử</button>
              {voice.is_public ? (
                <>
                  <button className="btn-secondary small" disabled={voice.voice_id === defaultId} onClick={() => run(() => setDefaultVoice(voice.voice_id), `Đã đặt "${voice.display_name}" làm giọng mặc định hệ thống`)}><Star size={14} /> Đặt mặc định</button>
                  <button className="btn-secondary small" disabled={voice.voice_id === defaultId} title={voice.voice_id === defaultId ? 'Đang là giọng mặc định hệ thống' : undefined} onClick={() => run(() => setVoicePublic(voice.voice_id, false), `Đã gỡ "${voice.display_name}"`)}>Gỡ công khai</button>
                </>
              ) : (
                <button className="btn-primary small" disabled={!voice.is_mine} onClick={() => run(() => setVoicePublic(voice.voice_id, true), `Đã công khai "${voice.display_name}"`)}>Công khai</button>
              )}
            </span>
          </li>
        ))}
      </ul>
    </>
  );
};
