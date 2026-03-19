'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import mapboxgl from 'mapbox-gl';
import TimelineScrubber from './TimelineScrubber';
import { api } from '@/lib/api';

interface Props {
  map: mapboxgl.Map;
}

interface Sighting {
  timestamp: string;
  latitude: number;
  longitude: number;
  plate: string;
  confidence: number;
}

export default function PlotMode({ map }: Props) {
  const [plate, setPlate] = useState('');
  const [dateRange, setDateRange] = useState({ start: '', end: '' });
  const [sightings, setSightings] = useState<Sighting[]>([]);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const markersRef = useRef<mapboxgl.Marker[]>([]);
  const animRef = useRef<number>(undefined);

  const loadSightings = async () => {
    if (!plate) return;
    const data = await api.getSightings(plate, 1000);
    const sorted = data.sightings.sort(
      (a: Sighting, b: Sighting) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );
    setSightings(sorted);
    if (sorted.length > 0) {
      setCurrentTime(new Date(sorted[0].timestamp));
    }
  };

  // Animate playback
  useEffect(() => {
    if (!isPlaying || sightings.length === 0) return;

    const endTime = new Date(sightings[sightings.length - 1].timestamp);
    const intervalMs = 50;
    const stepMs = speed * 60000; // 1 minute per tick * speed

    animRef.current = window.setInterval(() => {
      setCurrentTime((prev) => {
        const next = new Date(prev.getTime() + stepMs);
        if (next >= endTime) {
          setIsPlaying(false);
          return endTime;
        }
        return next;
      });
    }, intervalMs);

    return () => clearInterval(animRef.current);
  }, [isPlaying, speed, sightings]);

  // Update visible markers based on currentTime
  useEffect(() => {
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    const visible = sightings.filter((s) => new Date(s.timestamp) <= currentTime);

    // Draw path line
    if (visible.length >= 2) {
      const coords = visible.map((s) => [s.longitude, s.latitude]);
      const source = map.getSource('plot-path') as mapboxgl.GeoJSONSource;
      const geojson: GeoJSON.Feature = {
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: coords },
        properties: {},
      };
      if (source) {
        source.setData(geojson);
      } else {
        map.addSource('plot-path', { type: 'geojson', data: geojson });
        map.addLayer({
          id: 'plot-path-line',
          type: 'line',
          source: 'plot-path',
          paint: { 'line-color': '#3b82f6', 'line-width': 3 },
        });
      }
    }

    // Add markers for visible sightings
    visible.forEach((s) => {
      const marker = new mapboxgl.Marker({ color: '#3b82f6', scale: 0.6 })
        .setLngLat([s.longitude, s.latitude])
        .addTo(map);
      markersRef.current.push(marker);
    });
  }, [currentTime, sightings, map]);

  const startTime = sightings.length > 0 ? new Date(sightings[0].timestamp) : new Date();
  const endTime = sightings.length > 0 ? new Date(sightings[sightings.length - 1].timestamp) : new Date();

  return (
    <>
      <div className="absolute top-16 left-4 z-10 bg-gray-800/90 p-4 rounded-lg">
        <input
          type="text"
          placeholder="Plate number..."
          value={plate}
          onChange={(e) => setPlate(e.target.value.toUpperCase())}
          className="bg-gray-700 text-white px-3 py-2 rounded w-48 text-sm"
        />
        <button
          onClick={loadSightings}
          className="ml-2 px-4 py-2 bg-blue-600 text-white rounded text-sm"
        >
          Load
        </button>
      </div>
      {sightings.length > 0 && (
        <TimelineScrubber
          startTime={startTime}
          endTime={endTime}
          currentTime={currentTime}
          onTimeChange={setCurrentTime}
          isPlaying={isPlaying}
          onPlayPause={() => setIsPlaying(!isPlaying)}
          speed={speed}
          onSpeedChange={setSpeed}
        />
      )}
    </>
  );
}
