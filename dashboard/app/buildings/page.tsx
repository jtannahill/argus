'use client';

import { Suspense, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { getBuilding } from '@/lib/api';

type Tab = 'story' | 'owner' | 'value' | 'violations' | 'permits';

interface BuildingData {
  bbl: string;
  address: string;
  borough: string;
  yearBuilt?: number;
  numFloors?: number;
  unitsTotal?: number;
  landUse?: string;
  isLandmark?: boolean;
  scanCount?: number;
  story?: {
    headline: string;
    body: string;
    generatedAt: string;
  };
  owner?: {
    name: string;
    mailingAddress?: string;
    ownerType?: string;
    portfolioSize?: number;
  };
  value?: {
    assessedValue?: number;
    marketValue?: number;
    taxClass?: string;
    lastSalePrice?: number;
    lastSaleDate?: string;
  };
  violations?: {
    violationId: string;
    issueDate: string;
    description: string;
    status: string;
    device?: string;
  }[];
  permits?: {
    permitNum: string;
    issueDate: string;
    type: string;
    description: string;
    status: string;
  }[];
}

const TABS: { id: Tab; label: string }[] = [
  { id: 'story', label: 'Story' },
  { id: 'owner', label: 'Owner' },
  { id: 'value', label: 'Value' },
  { id: 'violations', label: 'Violations' },
  { id: 'permits', label: 'Permits' },
];

function fmt(val: number | undefined, prefix = '') {
  if (val == null) return '—';
  return `${prefix}${val.toLocaleString()}`;
}

function BuildingDetailContent() {
  const searchParams = useSearchParams();
  const bbl = searchParams.get('bbl') || '';
  const [data, setData] = useState<BuildingData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [tab, setTab] = useState<Tab>('story');

  useEffect(() => {
    if (!bbl) return;
    setLoading(true);
    setError('');
    getBuilding(bbl)
      .then(setData)
      .catch(() => setError('Failed to load building data.'))
      .finally(() => setLoading(false));
  }, [bbl]);

  if (!bbl) {
    return (
      <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center">
        <p className="text-gray-400">No building specified. Provide a <code className="text-green-400">bbl</code> query parameter.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center">
        <div className="text-gray-400 animate-pulse">Loading building data…</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center">
        <p className="text-red-400">{error || 'No data found.'}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <div className="border-b border-gray-800 px-6 py-4 flex items-start justify-between">
        <div>
          <Link href="/" className="text-green-400 text-sm hover:text-green-300 mb-2 inline-block">
            &larr; Map
          </Link>
          <h1 className="text-2xl font-semibold">{data.address}</h1>
          <div className="flex items-center gap-3 mt-1 text-sm text-gray-400">
            <span>{data.borough}</span>
            <span>BBL {data.bbl}</span>
            {data.yearBuilt && <span>Built {data.yearBuilt}</span>}
            {data.numFloors && <span>{data.numFloors} floors</span>}
            {data.unitsTotal && <span>{data.unitsTotal} units</span>}
            {data.scanCount != null && (
              <span className="text-green-400">{data.scanCount} scans</span>
            )}
            {data.isLandmark && (
              <span className="px-2 py-0.5 rounded-full bg-yellow-900/50 border border-yellow-500 text-yellow-300 text-xs">
                Landmark
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-800 px-6 flex gap-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              tab === t.id
                ? 'border-green-500 text-green-400'
                : 'border-transparent text-gray-400 hover:text-gray-200'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="p-6 max-w-4xl">
        {tab === 'story' && (
          <div>
            {data.story ? (
              <>
                <h2 className="text-xl font-semibold mb-3">{data.story.headline}</h2>
                <p className="text-gray-300 leading-relaxed whitespace-pre-wrap">{data.story.body}</p>
                <p className="text-gray-500 text-xs mt-4">
                  Generated {new Date(data.story.generatedAt).toLocaleString()}
                </p>
              </>
            ) : (
              <p className="text-gray-500">No story generated yet.</p>
            )}
          </div>
        )}

        {tab === 'owner' && (
          <div className="bg-gray-800 rounded-lg p-5 max-w-sm">
            <h2 className="text-gray-400 text-sm mb-3 uppercase tracking-wider">Ownership</h2>
            {data.owner ? (
              <dl className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <dt className="text-gray-400">Name</dt>
                  <dd className="text-white">{data.owner.name || '—'}</dd>
                </div>
                {data.owner.ownerType && (
                  <div className="flex justify-between">
                    <dt className="text-gray-400">Type</dt>
                    <dd className="text-white capitalize">{data.owner.ownerType}</dd>
                  </div>
                )}
                {data.owner.mailingAddress && (
                  <div className="flex justify-between">
                    <dt className="text-gray-400">Mailing</dt>
                    <dd className="text-white text-right max-w-[60%]">{data.owner.mailingAddress}</dd>
                  </div>
                )}
                {data.owner.portfolioSize != null && (
                  <div className="flex justify-between">
                    <dt className="text-gray-400">Portfolio</dt>
                    <dd className="text-white">{data.owner.portfolioSize} properties</dd>
                  </div>
                )}
              </dl>
            ) : (
              <p className="text-gray-500 text-sm">No ownership data available.</p>
            )}
          </div>
        )}

        {tab === 'value' && (
          <div className="bg-gray-800 rounded-lg p-5 max-w-sm">
            <h2 className="text-gray-400 text-sm mb-3 uppercase tracking-wider">Assessed Value</h2>
            {data.value ? (
              <dl className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <dt className="text-gray-400">Tax Class</dt>
                  <dd className="text-white">{data.value.taxClass || '—'}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-400">Assessed Value</dt>
                  <dd className="text-white">{fmt(data.value.assessedValue, '$')}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-400">Market Value</dt>
                  <dd className="text-white">{fmt(data.value.marketValue, '$')}</dd>
                </div>
                {data.value.lastSalePrice && (
                  <div className="flex justify-between">
                    <dt className="text-gray-400">Last Sale</dt>
                    <dd className="text-white">{fmt(data.value.lastSalePrice, '$')}</dd>
                  </div>
                )}
                {data.value.lastSaleDate && (
                  <div className="flex justify-between">
                    <dt className="text-gray-400">Sale Date</dt>
                    <dd className="text-white">{data.value.lastSaleDate}</dd>
                  </div>
                )}
              </dl>
            ) : (
              <p className="text-gray-500 text-sm">No valuation data available.</p>
            )}
          </div>
        )}

        {tab === 'violations' && (
          <div>
            {data.violations && data.violations.length > 0 ? (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-400 border-b border-gray-700 text-left">
                    <th className="py-2 pr-4">ID</th>
                    <th className="py-2 pr-4">Date</th>
                    <th className="py-2 pr-4">Description</th>
                    <th className="py-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.violations.map((v) => (
                    <tr key={v.violationId} className="border-b border-gray-800">
                      <td className="py-2 pr-4 font-mono text-xs text-gray-400">{v.violationId}</td>
                      <td className="py-2 pr-4 text-gray-300 whitespace-nowrap">{v.issueDate}</td>
                      <td className="py-2 pr-4 text-gray-200">{v.description}</td>
                      <td className="py-2">
                        <span
                          className={`px-2 py-0.5 rounded text-xs ${
                            v.status === 'OPEN'
                              ? 'bg-red-900/50 text-red-300'
                              : 'bg-gray-700 text-gray-400'
                          }`}
                        >
                          {v.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="text-gray-500">No violations on record.</p>
            )}
          </div>
        )}

        {tab === 'permits' && (
          <div>
            {data.permits && data.permits.length > 0 ? (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-400 border-b border-gray-700 text-left">
                    <th className="py-2 pr-4">Permit #</th>
                    <th className="py-2 pr-4">Date</th>
                    <th className="py-2 pr-4">Type</th>
                    <th className="py-2 pr-4">Description</th>
                    <th className="py-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.permits.map((p) => (
                    <tr key={p.permitNum} className="border-b border-gray-800">
                      <td className="py-2 pr-4 font-mono text-xs text-gray-400">{p.permitNum}</td>
                      <td className="py-2 pr-4 text-gray-300 whitespace-nowrap">{p.issueDate}</td>
                      <td className="py-2 pr-4 text-gray-300">{p.type}</td>
                      <td className="py-2 pr-4 text-gray-200">{p.description}</td>
                      <td className="py-2">
                        <span className="px-2 py-0.5 rounded text-xs bg-gray-700 text-gray-400">
                          {p.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="text-gray-500">No permits on record.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function BuildingDetailPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center">
          <div className="text-gray-400 animate-pulse">Loading…</div>
        </div>
      }
    >
      <BuildingDetailContent />
    </Suspense>
  );
}
