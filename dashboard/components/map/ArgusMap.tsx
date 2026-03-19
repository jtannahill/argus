'use client';

import { useRef, useEffect, useState, useCallback } from 'react';
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';
import { createWebSocket } from '@/lib/websocket';

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
  const [mode, setMode] = useState<MapMode>('live');
  const [sightings, setSightings] = useState<Sighting[]>([]);

  useEffect(() => {
    if (!mapContainer.current) return;

    map.current = new mapboxgl.Map({
      container: mapContainer.current,
      style: 'mapbox://styles/mapbox/dark-v11',
      center: [-80.1918, 25.7617], // Miami default
      zoom: 12,
    });

    return () => { map.current?.remove(); };
  }, []);

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
    const color = hasAlerts ? '#ef4444' : '#22c55e'; // red if alert, green if new

    new mapboxgl.Marker({ color })
      .setLngLat([sighting.longitude, sighting.latitude])
      .setPopup(
        new mapboxgl.Popup().setHTML(`
          <strong>${sighting.plate}</strong><br/>
          ${new Date(sighting.timestamp).toLocaleString()}<br/>
          Confidence: ${(sighting.confidence * 100).toFixed(0)}%
        `)
      )
      .addTo(map.current);
  }, []);

  return (
    <div className="relative w-full h-full">
      <div className="absolute top-4 right-4 z-10 flex gap-2">
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
      <div ref={mapContainer} className="w-full h-full" />
    </div>
  );
}
