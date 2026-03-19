'use client';

import { useRef, useEffect, useState, useCallback } from 'react';
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';
import { createWebSocket } from '@/lib/websocket';
import { api } from '@/lib/api';
import PlotMode from './PlotMode';

mapboxgl.accessToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN || '';

interface Sighting {
  plate: string;
  latitude: number;
  longitude: number;
  timestamp: string;
  confidence: number;
  alerts?: { type: string }[];
}

type MapMode = 'live' | 'plot';

export default function ArgusMap() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<mapboxgl.Map | null>(null);
  const markersRef = useRef<mapboxgl.Marker[]>([]);
  const [mode, setMode] = useState<MapMode>('live');
  const [sightings, setSightings] = useState<Sighting[]>([]);
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    if (!mapContainer.current) return;

    map.current = new mapboxgl.Map({
      container: mapContainer.current,
      style: 'mapbox://styles/mapbox/dark-v11',
      center: [-73.9857, 40.7484],
      zoom: 13,
    });

    map.current.on('load', () => setMapReady(true));

    return () => { map.current?.remove(); };
  }, []);

  // Load recent sightings on mount
  useEffect(() => {
    if (!mapReady) return;

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';
    fetch(`${apiUrl}/recent?limit=200`)
      .then(res => res.json())
      .then((data) => {
        const results = data.sightings || [];
        const loaded: Sighting[] = [];
        results.forEach((r: any) => {
          if (r.latitude && r.longitude) {
            const s: Sighting = {
              plate: r.plate,
              latitude: r.latitude,
              longitude: r.longitude,
              timestamp: r.timestamp || '',
              confidence: r.confidence || 0,
            };
            addPin(s);
            loaded.push(s);
          }
        });
        setSightings(loaded);

        // Fit map to show all pins
        if (loaded.length > 0 && map.current) {
          const bounds = new mapboxgl.LngLatBounds();
          loaded.forEach(s => bounds.extend([s.longitude, s.latitude]));
          if (!bounds.isEmpty()) {
            map.current.fitBounds(bounds, { padding: 50, maxZoom: 15 });
          }
        }
      })
      .catch(() => {});
  }, [mapReady]);

  // WebSocket for live mode
  useEffect(() => {
    if (mode !== 'live') return;

    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || '';
    if (!wsUrl) return;

    const ws = createWebSocket(wsUrl, (data: Sighting) => {
      setSightings((prev) => [data, ...prev].slice(0, 500));
      addPin(data);
    });

    return () => ws.close();
  }, [mode]);

  const addPin = useCallback((sighting: Sighting) => {
    if (!map.current) return;

    const hasAlerts = sighting.alerts && sighting.alerts.length > 0;
    const color = hasAlerts ? '#ef4444' : '#22c55e';

    const marker = new mapboxgl.Marker({ color })
      .setLngLat([sighting.longitude, sighting.latitude])
      .setPopup(
        new mapboxgl.Popup({ className: 'argus-popup' }).setHTML(`
          <div style="background:#1f2937;color:#f9fafb;padding:8px 12px;border-radius:8px;font-family:monospace;">
            <div style="font-size:16px;font-weight:bold;color:#22c55e;">${sighting.plate}</div>
            <div style="font-size:11px;color:#9ca3af;margin-top:4px;">${new Date(sighting.timestamp).toLocaleString()}</div>
            <div style="font-size:11px;color:#9ca3af;">Confidence: ${(sighting.confidence * 100).toFixed(0)}%</div>
          </div>
        `)
      )
      .addTo(map.current);
    markersRef.current.push(marker);
  }, []);

  return (
    <div className="relative w-full h-full">
      <div className="absolute top-4 right-32 z-10 flex gap-2">
        <button
          onClick={() => setMode('live')}
          className={`px-4 py-2 rounded text-sm font-medium ${mode === 'live' ? 'bg-green-600 text-white' : 'bg-gray-700 text-gray-300'}`}
        >
          Live
        </button>
        <button
          onClick={() => setMode('plot')}
          className={`px-4 py-2 rounded text-sm font-medium ${mode === 'plot' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'}`}
        >
          Plot
        </button>
      </div>
      <div className="absolute bottom-4 left-4 z-10 bg-gray-800/80 px-3 py-1 rounded text-xs text-gray-300">
        {sightings.length} sightings
      </div>
      {mode === 'plot' && map.current && <PlotMode map={map.current} />}
      <div ref={mapContainer} className="w-full h-full" />
    </div>
  );
}
