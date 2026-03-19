import ArgusMap from '@/components/map/ArgusMap';
import SearchBar from '@/components/SearchBar';
import AlertsPanel from '@/components/AlertsPanel';

export default function Home() {
  return (
    <main className="h-screen w-screen bg-gray-900">
      <SearchBar />
      <AlertsPanel />
      <ArgusMap />
    </main>
  );
}
