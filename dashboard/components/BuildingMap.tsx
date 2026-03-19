'use client';

import { useRef, useEffect, useState, useCallback } from 'react';
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';
import { getRecentScans } from '@/lib/api';
import HeatLayer from './HeatLayer';

mapboxgl.accessToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN || '';

interface Scan {
  bbl: string;
  address: string;
  latitude: number;
  longitude: number;
  scanCount: number;
  storyHeadline?: string;
  isLandmark?: boolean;
}

const SOURCE_ID = 'building-scans';

export default function BuildingMap() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<mapboxgl.Map | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [scanCount, setScanCount] = useState(0);

  // Initialise map
  useEffect(() => {
    if (!mapContainer.current) return;

    map.current = new mapboxgl.Map({
      container: mapContainer.current,
      style: 'mapbox://styles/mapbox/dark-v11',
      center: [-74.006, 40.7128], // Manhattan
      zoom: 13,
    });

    map.current.addControl(new mapboxgl.NavigationControl(), 'top-right');

    map.current.on('load', () => setMapReady(true));

    return () => {
      map.current?.remove();
    };
  }, []);

  // Load recent scans and build GeoJSON source
  const loadScans = useCallback(async () => {
    if (!map.current || !mapReady) return;

    let scans: Scan[] = [];
    try {
      const data = await getRecentScans(200);
      scans = (data.scans || data.items || []).filter(
        (s: Scan) => s.latitude != null && s.longitude != null
      );
    } catch {
      // API not yet wired; render empty map
    }

    setScanCount(scans.length);

    const geojson: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: scans.map((s) => ({
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: [s.longitude, s.latitude],
        },
        properties: {
          bbl: s.bbl,
          address: s.address,
          scanCount: s.scanCount ?? 1,
          storyHeadline: s.storyHeadline || '',
          isLandmark: s.isLandmark ? 1 : 0,
        },
      })),
    };

    const existing = map.current.getSource(SOURCE_ID) as mapboxgl.GeoJSONSource | undefined;
    if (existing) {
      existing.setData(geojson);
    } else {
      map.current.addSource(SOURCE_ID, { type: 'geojson', data: geojson });

      // Circle layer (visible at high zoom after heatmap fades)
      map.current.addLayer({
        id: 'building-circles',
        type: 'circle',
        source: SOURCE_ID,
        minzoom: 14,
        paint: {
          'circle-radius': [
            'interpolate',
            ['linear'],
            ['get', 'scanCount'],
            1, 5,
            10, 12,
          ],
          'circle-color': [
            'interpolate',
            ['linear'],
            ['get', 'scanCount'],
            1, '#22c55e',
            5, '#eab308',
            10, '#ef4444',
          ],
          'circle-opacity': 0.85,
          'circle-stroke-width': 1,
          'circle-stroke-color': '#1f2937',
        },
      });
    }

    // Popup on click
    map.current.on('click', 'building-circles', (e) => {
      const feat = e.features?.[0];
      if (!feat || !map.current) return;

      const { bbl, address, storyHeadline } = feat.properties as {
        bbl: string;
        address: string;
        storyHeadline: string;
      };
      const coords = (feat.geometry as GeoJSON.Point).coordinates as [number, number];

      new mapboxgl.Popup({ className: 'argus-popup', maxWidth: '280px' })
        .setLngLat(coords)
        .setHTML(
          `<div style="background:#1f2937;color:#f9fafb;padding:10px 14px;border-radius:8px;font-family:system-ui,sans-serif;">
            <div style="font-size:13px;font-weight:600;color:#f9fafb;margin-bottom:4px;">${address}</div>
            ${storyHeadline ? `<div style="font-size:11px;color:#9ca3af;margin-bottom:8px;line-height:1.4;">${storyHeadline}</div>` : ''}
            <a href="/buildings?bbl=${bbl}" style="font-size:11px;color:#22c55e;">View full report &rarr;</a>
          </div>`
        )
        .addTo(map.current);
    });

    map.current.on('mouseenter', 'building-circles', () => {
      if (map.current) map.current.getCanvas().style.cursor = 'pointer';
    });
    map.current.on('mouseleave', 'building-circles', () => {
      if (map.current) map.current.getCanvas().style.cursor = '';
    });
  }, [mapReady]);

  useEffect(() => {
    loadScans();
  }, [loadScans]);

  return (
    <div className="relative w-full h-full">
      {/* Header bar */}
      <div className="absolute top-4 left-4 z-10 flex items-center gap-3">
        <div className="bg-gray-900/90 backdrop-blur px-4 py-2 rounded-lg border border-gray-700">
          <span className="text-green-400 font-semibold text-sm">Argus</span>
          <span className="text-gray-400 text-sm ml-2">Building Intelligence</span>
        </div>
      </div>

      {/* Scan count badge */}
      <div className="absolute bottom-8 left-4 z-10 bg-gray-800/80 backdrop-blur px-3 py-1 rounded text-xs text-gray-300">
        {scanCount} buildings scanned
      </div>

      {/* Legend */}
      <div className="absolute bottom-8 right-4 z-10 bg-gray-800/80 backdrop-blur px-3 py-2 rounded text-xs">
        <div className="text-gray-400 mb-1 font-medium">Scan density</div>
        <div className="flex items-center gap-2">
          <div className="w-20 h-2 rounded" style={{ background: 'linear-gradient(to right, #22c55e, #eab308, #ef4444)' }} />
          <div className="flex justify-between w-20 text-gray-400">
            <span>low</span>
            <span>high</span>
          </div>
        </div>
      </div>

      {/* Map container */}
      <div ref={mapContainer} className="w-full h-full" />

      {/* Heat layer rendered after map is ready */}
      {mapReady && map.current && (
        <HeatLayer map={map.current} sourceId={SOURCE_ID} />
      )}
    </div>
  );
}
