const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

async function fetchApi(path: string, options?: RequestInit) {
  const token = localStorage.getItem('argus_token') || '';
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...options?.headers,
    },
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export const api = {
  getPlate: (plate: string) => fetchApi(`/plates/${plate}`),
  getSightings: (plate: string, limit = 25, nextToken?: string) =>
    fetchApi(`/plates/${plate}/sightings?limit=${limit}${nextToken ? `&nextToken=${nextToken}` : ''}`),
  search: (q: string) => fetchApi(`/search?q=${q}`),
  getAlerts: (limit = 50) => fetchApi(`/alerts?limit=${limit}`),
  getGeofences: () => fetchApi('/geofences'),
  createGeofence: (data: { label: string; polygon: number[][]; alertFor: string }) =>
    fetchApi('/geofences', { method: 'POST', body: JSON.stringify(data) }),
  deleteGeofence: (id: string) => fetchApi(`/geofences/${id}`, { method: 'DELETE' }),
};
