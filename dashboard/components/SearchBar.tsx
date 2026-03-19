'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';

export default function SearchBar() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<{ plate: string; lastSeen: string }[]>([]);
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    if (query.length < 2) { setResults([]); return; }
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      const data = await api.search(query);
      setResults(data.results || []);
      setOpen(true);
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [query]);

  return (
    <div className="absolute top-4 left-4 z-20 w-72">
      <input
        type="text"
        placeholder="Search plates..."
        value={query}
        onChange={(e) => setQuery(e.target.value.toUpperCase())}
        onFocus={() => results.length > 0 && setOpen(true)}
        className="w-full bg-gray-800 text-white px-4 py-2 rounded-lg border border-gray-600 focus:border-blue-500 focus:outline-none text-sm font-mono"
      />
      {open && results.length > 0 && (
        <div className="mt-1 bg-gray-800 border border-gray-600 rounded-lg max-h-64 overflow-y-auto">
          {results.map((r) => (
            <button
              key={r.plate}
              onClick={() => { setOpen(false); router.push(`/plates?plate=${r.plate}`); }}
              className="w-full text-left px-4 py-2 hover:bg-gray-700 text-sm"
            >
              <span className="text-white font-mono">{r.plate}</span>
              <span className="text-gray-400 ml-2 text-xs">
                {new Date(r.lastSeen).toLocaleDateString()}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
