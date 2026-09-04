/* SourceMedia — the deepest level of the audit drill-down (design.md §4.5/§7.2):
   when a transaction carries source_media_id, fetch GET /api/media/{id} and show
   the ORIGINAL artifact — inline <audio controls preload="none"> for voice notes,
   a 96px thumbnail that opens a simple lightbox for receipt photos.

   Graceful states, no console noise:
   - mock mode / no media id → "not available in demo data" note (mock ids can
     never resolve, so we don't even try — zero failed requests)
   - live 404/410/network error → "original not available" note (the media row is
     kept server-side forever per schema.md §2, but demo seeds may lack blobs)
   Blob is object-URL'd and revoked on unmount; nothing is uploaded, only read. */

import { useEffect, useState } from 'react';
import type { SourceType } from '../types/schema';
import { api, mediaUrl } from '../api/client';
import { IconPhoto, IconVoice } from './icons';

type MediaState =
  | { kind: 'skip' }
  | { kind: 'loading' }
  | { kind: 'unavailable' }
  | { kind: 'audio'; url: string }
  | { kind: 'image'; url: string };

export interface SourceMediaProps {
  mediaId: string | null;
  sourceType: SourceType;
}

export function SourceMedia({ mediaId, sourceType }: SourceMediaProps) {
  const [state, setState] = useState<MediaState>(() =>
    mediaId && !api.mock ? { kind: 'loading' } : { kind: 'skip' },
  );
  const [lightboxOpen, setLightboxOpen] = useState(false);

  useEffect(() => {
    if (!mediaId || api.mock) return; // stays 'skip' — demo data, no fetch
    let alive = true;
    let objectUrl: string | null = null;
    (async () => {
      try {
        const res = await fetch(mediaUrl(mediaId));
        if (!res.ok) {
          if (alive) setState({ kind: 'unavailable' });
          return;
        }
        const blob = await res.blob();
        if (!alive) return;
        objectUrl = URL.createObjectURL(blob);
        const isImage = sourceType === 'photo' || blob.type.startsWith('image/');
        setState(isImage ? { kind: 'image', url: objectUrl } : { kind: 'audio', url: objectUrl });
      } catch {
        if (alive) setState({ kind: 'unavailable' });
      }
    })();
    return () => {
      alive = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [mediaId, sourceType]);

  if (state.kind === 'skip') {
    return (
      <Note>Original media not available in demo data</Note>
    );
  }

  if (state.kind === 'loading') {
    return (
      <Note>Fetching the original…</Note>
    );
  }

  if (state.kind === 'unavailable') {
    return (
      <Note>Original not available on the server right now</Note>
    );
  }

  if (state.kind === 'audio') {
    return (
      <div className="flex flex-col gap-1">
        <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ink-green">
          <IconVoice className="h-4 w-4" />
          Original voice note
        </p>
        {/* eslint-disable-next-line jsx-a11y/media-has-caption -- raw WhatsApp note, no captions exist */}
        <audio controls preload="none" src={state.url} className="w-full" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1">
      <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ink-green">
        <IconPhoto className="h-4 w-4" />
        Original receipt photo
      </p>
      <button
        type="button"
        onClick={() => setLightboxOpen(true)}
        className="w-fit overflow-hidden rounded-chip border-[3px] border-ink-line shadow-hard-sm transition-shadow duration-200 ease-out hover:shadow-hard-md focus-visible:shadow-hard-md motion-reduce:transition-none"
        aria-label="Show the original receipt photo larger"
      >
        <img
          src={state.url}
          alt="Receipt photo thumbnail"
          width={96}
          height={96}
          className="block h-24 w-24 object-cover"
        />
      </button>
      {lightboxOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink-line/80 p-6"
          role="dialog"
          aria-modal="true"
          aria-label="Receipt photo — press Escape to close"
          onClick={() => setLightboxOpen(false)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') setLightboxOpen(false);
          }}
        >
          <img
            src={state.url}
            alt="Original receipt photo, full size"
            className="max-h-[85vh] max-w-full rounded-chip border-[3px] border-paper"
          />
        </div>
      )}
    </div>
  );
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-chip border-2 border-dashed border-ink-line bizro-tint-neutral px-3 py-2 text-xs text-ink-line opacity-80">
      {children}
    </p>
  );
}
