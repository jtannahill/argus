const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

async function fetchApi(path: string, options?: RequestInit) {
  const token = typeof window !== 'undefined' ? localStorage.getItem('argus_token') || '' : '';
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

export async function getBuilding(bbl: string) {
  return fetchApi(`/buildings/${bbl}`);
}

export async function getRecentScans(limit = 50) {
  return fetchApi(`/scans/recent?limit=${limit}`);
}

export async function getTrending(date?: string) {
  const qs = date ? `?date=${encodeURIComponent(date)}` : '';
  return fetchApi(`/buildings/trending${qs}`);
}

export async function searchBuildings(lat: number, lon: number, radius = 100) {
  return fetchApi(`/buildings/search?lat=${lat}&lon=${lon}&radius=${radius}`);
}
