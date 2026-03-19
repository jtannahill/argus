'use client';

interface DiplomaticInfo {
  isDiplomatic: boolean;
  issuingCountry: string;
  plateType: string;
  mission?: {
    country: string;
    missionType: string;
    city: string;
  };
}

interface Props {
  diplomatic: DiplomaticInfo;
}

const COUNTRY_FLAGS: Record<string, string> = {
  'United Kingdom': '🇬🇧', 'France': '🇫🇷', 'Germany': '🇩🇪', 'Italy': '🇮🇹',
  'Japan': '🇯🇵', 'Canada': '🇨🇦', 'Brazil': '🇧🇷', 'Mexico': '🇲🇽',
  'Colombia': '🇨🇴', 'Argentina': '🇦🇷', 'Spain': '🇪🇸', 'Israel': '🇮🇱',
  'China': '🇨🇳', 'India': '🇮🇳', 'Russia': '🇷🇺', 'South Korea': '🇰🇷',
  'Australia': '🇦🇺', 'Switzerland': '🇨🇭', 'Netherlands': '🇳🇱', 'Sweden': '🇸🇪',
};

const ISSUING_LABELS: Record<string, string> = {
  US: 'US State Dept',
  CA: 'Canadian',
  MX: 'Mexican',
};

export default function DiplomaticBadge({ diplomatic }: Props) {
  if (!diplomatic?.isDiplomatic) return null;

  const country = diplomatic.mission?.country;
  const flag = country ? COUNTRY_FLAGS[country] || '🏛️' : '🏛️';
  const label = country
    ? `${country} ${diplomatic.plateType}`
    : `${ISSUING_LABELS[diplomatic.issuingCountry] || diplomatic.issuingCountry} Diplomatic`;

  return (
    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-purple-900/50 border border-purple-500 text-purple-200 text-sm font-medium">
      <span>{flag}</span>
      <span className="capitalize">{label}</span>
    </span>
  );
}
