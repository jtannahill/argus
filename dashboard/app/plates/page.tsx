'use client';

import { Suspense, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { api } from '@/lib/api';
import DiplomaticBadge from '@/components/DiplomaticBadge';

interface PlateData {
  plate: string;
  enrichment: {
    registration?: string;
    classifierMake?: string;
    classifierModel?: string;
    classifierYear?: string;
    classifierColor?: string;
    mismatch?: boolean;
    mismatchDetails?: string;
    diplomatic?: {
      isDiplomatic: boolean;
      issuingCountry: string;
      plateType: string;
      mission?: { country: string; missionType: string; city: string };
    };
  };
  recentSightings: {
    timestamp: string;
    latitude: number;
    longitude: number;
    confidence: number;
    mode: string;
  }[];
}

function PlateDetailContent() {
  const searchParams = useSearchParams();
  const plate = searchParams.get('plate') || '';
  const [data, setData] = useState<PlateData | null>(null);

  useEffect(() => {
    if (plate) api.getPlate(plate).then(setData);
  }, [plate]);

  if (!plate) return <div className="p-8 text-white">No plate specified</div>;
  if (!data) return <div className="p-8 text-white">Loading...</div>;

  const reg = data.enrichment.registration ? JSON.parse(data.enrichment.registration) : {};

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <Link href="/" className="text-blue-400 text-sm mb-4 inline-block">&larr; Back to map</Link>

      <h1 className="text-3xl font-mono font-bold mb-4">{data.plate}</h1>

      {data.enrichment.diplomatic?.isDiplomatic && (
        <div className="mb-6">
          <DiplomaticBadge diplomatic={data.enrichment.diplomatic} />
        </div>
      )}

      {data.enrichment.mismatch && (
        <div className="bg-red-900/50 border border-red-500 rounded-lg p-4 mb-6">
          <span className="text-red-400 font-bold">CLONE SUSPICION</span>
          <p className="text-sm mt-1">{data.enrichment.mismatchDetails}</p>
        </div>
      )}

      <div className="grid grid-cols-2 gap-6 mb-8">
        <div className="bg-gray-800 rounded-lg p-4">
          <h2 className="text-gray-400 text-sm mb-3">Registration</h2>
          {['make', 'model', 'year', 'color', 'state', 'owner'].map((field) => (
            <div key={field} className="flex justify-between py-1 text-sm">
              <span className="text-gray-400 capitalize">{field}</span>
              <span>{reg[field] || '—'}</span>
            </div>
          ))}
        </div>
        <div className="bg-gray-800 rounded-lg p-4">
          <h2 className="text-gray-400 text-sm mb-3">Classifier</h2>
          {['Make', 'Model', 'Year', 'Color'].map((f) => (
            <div key={f} className="flex justify-between py-1 text-sm">
              <span className="text-gray-400">{f}</span>
              <span>{String(data.enrichment[`classifier${f}` as keyof typeof data.enrichment] || '—')}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Sighting History</h2>
        <Link href={`/?plot=${data.plate}`} className="text-blue-400 text-sm">Plot on map &rarr;</Link>
      </div>

      <table className="w-full text-sm">
        <thead>
          <tr className="text-gray-400 border-b border-gray-700">
            <th className="text-left py-2">Time</th>
            <th className="text-left py-2">Location</th>
            <th className="text-left py-2">Confidence</th>
            <th className="text-left py-2">Mode</th>
          </tr>
        </thead>
        <tbody>
          {data.recentSightings.map((s, i) => (
            <tr key={i} className="border-b border-gray-800">
              <td className="py-2">{new Date(s.timestamp).toLocaleString()}</td>
              <td className="py-2 font-mono text-xs">{s.latitude.toFixed(4)}, {s.longitude.toFixed(4)}</td>
              <td className="py-2">{(s.confidence * 100).toFixed(0)}%</td>
              <td className="py-2 capitalize">{s.mode}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function PlateDetailPage() {
  return (
    <Suspense fallback={<div className="p-8 text-white">Loading...</div>}>
      <PlateDetailContent />
    </Suspense>
  );
}
