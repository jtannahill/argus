'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';

interface Alert {
  alertId: string;
  timestamp: string;
  type: string;
  plate: string;
  message: string;
  geofenceId?: string;
}

const ALERT_COLORS: Record<string, string> = {
  clone_suspicion: 'border-red-500 bg-red-900/30',
  circling: 'border-orange-500 bg-orange-900/30',
  repeat_visit: 'border-yellow-500 bg-yellow-900/30',
  diplomatic_sighting: 'border-purple-500 bg-purple-900/30',
};

export default function AlertsPanel() {
  const [open, setOpen] = useState(false);
  const [alerts, setAlerts] = useState<Alert[]>([]);

  useEffect(() => {
    api.getAlerts().then((data) => setAlerts(data.alerts || []));
  }, []);

  return (
    <>
      <button
        onClick={() => setOpen(!open)}
        className="absolute top-4 right-4 z-20 px-3 py-2 bg-gray-800 text-white rounded-lg text-sm border border-gray-600"
      >
        Alerts {alerts.length > 0 && <span className="ml-1 bg-red-600 text-xs px-1.5 py-0.5 rounded-full">{alerts.length}</span>}
      </button>

      {open && (
        <div className="absolute top-14 right-4 z-20 w-96 max-h-[80vh] overflow-y-auto bg-gray-800 border border-gray-600 rounded-lg">
          <div className="p-3 border-b border-gray-700 font-semibold text-white text-sm">Alerts</div>
          {alerts.length === 0 && <div className="p-4 text-gray-400 text-sm">No alerts</div>}
          {alerts.map((a) => (
            <Link
              key={a.alertId}
              href={`/plates/${a.plate}`}
              className={`block p-3 border-l-4 m-2 rounded text-sm ${ALERT_COLORS[a.type] || 'border-gray-500'}`}
            >
              <div className="flex justify-between">
                <span className="text-white font-mono">{a.plate}</span>
                <span className="text-gray-400 text-xs">{new Date(a.timestamp).toLocaleString()}</span>
              </div>
              <p className="text-gray-300 text-xs mt-1">{a.message}</p>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
