import { useEffect, useRef, useState } from 'react';
import { geocodeAddress } from '../api/routeApi';
import { useI18n } from '../i18n';
import type { GeocodeResult, LatLng } from '../types';

interface Props {
  placeholder?: string;
  onSelect: (pos: LatLng, label: string) => void;
}

export default function AddressSearch({ placeholder, onSelect }: Props) {
  const { t } = useI18n();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<GeocodeResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [open, setOpen] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, []);

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setResults([]);
      setSearching(false);
      setErr(null);
      return;
    }
    const ctrl = new AbortController();
    const timer = window.setTimeout(async () => {
      setSearching(true);
      setErr(null);
      try {
        const items = await geocodeAddress(trimmed, ctrl.signal);
        if (!ctrl.signal.aborted) {
          setResults(items);
          setOpen(true);
        }
      } catch (e) {
        if (!ctrl.signal.aborted) {
          setErr(e instanceof Error ? e.message : 'Lỗi tìm địa chỉ');
          setResults([]);
        }
      } finally {
        if (!ctrl.signal.aborted) setSearching(false);
      }
    }, 350);
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [query]);

  return (
    <div className="addr-search" ref={boxRef}>
      <div className="addr-input-wrap">
        <input
          type="search"
          className="addr-input"
          placeholder={placeholder ?? t('searchPlaceholder')}
          value={query}
          onFocus={() => {
            if (results.length > 0) setOpen(true);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Escape') setOpen(false);
          }}
          onChange={(e) => setQuery(e.target.value)}
        />
        {searching && <span className="addr-spinner" aria-label={t('searchingAddr')}>⏳</span>}
      </div>
      {open && (results.length > 0 || err || (query.trim().length >= 2 && !searching)) && (
        <ul className="addr-results" role="listbox">
          {err && <li className="addr-empty">{err}</li>}
          {!err && results.length === 0 && <li className="addr-empty">{t('noAddrResults')}</li>}
          {results.map((item, idx) => (
            <li key={`${item.latitude}-${item.longitude}-${idx}`}>
              <button
                type="button"
                className="addr-option"
                onClick={() => {
                  onSelect({ lat: item.latitude, lng: item.longitude }, item.label);
                  setQuery(item.label);
                  setOpen(false);
                }}
              >
                <strong>{item.label}</strong>
                <span>{item.latitude.toFixed(5)}, {item.longitude.toFixed(5)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
