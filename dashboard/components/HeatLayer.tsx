'use client';

import { useEffect } from 'react';
import mapboxgl from 'mapbox-gl';

interface Props {
  map: mapboxgl.Map;
  sourceId: string;
}

export default function HeatLayer({ map, sourceId }: Props) {
  useEffect(() => {
    const LAYER_ID = 'building-heat';

    function addLayer() {
      if (map.getLayer(LAYER_ID)) return;

      map.addLayer({
        id: LAYER_ID,
        type: 'heatmap',
        source: sourceId,
        maxzoom: 17,
        paint: {
          // Weight by scan count; cap at 10 for colour saturation
          'heatmap-weight': [
            'interpolate',
            ['linear'],
            ['get', 'scanCount'],
            0, 0,
            10, 1,
          ],
          // Intensity scales with zoom level
          'heatmap-intensity': [
            'interpolate',
            ['linear'],
            ['zoom'],
            0, 1,
            17, 3,
          ],
          // Gradient: transparent → green → yellow → red
          'heatmap-color': [
            'interpolate',
            ['linear'],
            ['heatmap-density'],
            0,   'rgba(0,0,0,0)',
            0.2, '#22c55e',
            0.5, '#eab308',
            0.8, '#f97316',
            1,   '#ef4444',
          ],
          // Radius grows with zoom
          'heatmap-radius': [
            'interpolate',
            ['linear'],
            ['zoom'],
            0, 4,
            10, 20,
            17, 40,
          ],
          // Fade out heatmap as zoom increases (circle layer takes over)
          'heatmap-opacity': [
            'interpolate',
            ['linear'],
            ['zoom'],
            14, 1,
            17, 0,
          ],
        },
      });
    }

    if (map.isStyleLoaded()) {
      addLayer();
    } else {
      map.once('load', addLayer);
    }

    return () => {
      if (map.getLayer(LAYER_ID)) map.removeLayer(LAYER_ID);
    };
  }, [map, sourceId]);

  return null;
}
