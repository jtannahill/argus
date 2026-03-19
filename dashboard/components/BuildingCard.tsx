import Link from 'next/link';

interface Props {
  bbl: string;
  address: string;
  yearBuilt?: number;
  storyHeadline?: string;
  scanCount?: number;
  isLandmark?: boolean;
}

export default function BuildingCard({
  bbl,
  address,
  yearBuilt,
  storyHeadline,
  scanCount,
  isLandmark,
}: Props) {
  return (
    <Link
      href={`/buildings?bbl=${bbl}`}
      className="block bg-gray-800 hover:bg-gray-700 border border-gray-700 hover:border-gray-500 rounded-lg p-4 transition-colors"
    >
      <div className="flex items-start justify-between gap-2 mb-1">
        <h3 className="text-white font-medium text-sm leading-snug">{address}</h3>
        {isLandmark && (
          <span className="shrink-0 px-1.5 py-0.5 rounded-full bg-yellow-900/50 border border-yellow-500 text-yellow-300 text-xs">
            Landmark
          </span>
        )}
      </div>

      <div className="flex items-center gap-3 text-xs text-gray-400 mb-2">
        {yearBuilt && <span>Built {yearBuilt}</span>}
        {scanCount != null && (
          <span className="text-green-400">{scanCount} scan{scanCount !== 1 ? 's' : ''}</span>
        )}
      </div>

      {storyHeadline && (
        <p className="text-gray-300 text-xs line-clamp-2 leading-relaxed">{storyHeadline}</p>
      )}
    </Link>
  );
}
