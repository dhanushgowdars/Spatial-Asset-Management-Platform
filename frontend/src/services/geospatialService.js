/** The Aereo assessment API is proxied by Vite in development and same-origin in production. */
const ROOT = '/api/files/';
const MAX_BYTES = 10 * 1024 * 1024;

async function unwrap(response) {
  if (response.ok) return response.json();
  let detail;
  try {
    const body = await response.json();
    detail = body.detail;
  } catch { /* response may be plain text */ }
  if (Array.isArray(detail)) detail = detail.map(x => x.msg || String(x)).join('; ');
  throw new Error(typeof detail === 'string' ? detail : `Request failed (HTTP ${response.status})`);
}

export async function uploadDataset(file, signal) {
  if (!file) throw new Error('Select a .kml or zipped Shapefile first.');
  if (!/\.(kml|zip)$/i.test(file.name)) throw new Error('Only KML and ZIP Shapefile uploads are supported.');
  if (file.size === 0 || file.size > MAX_BYTES) throw new Error('File must be nonempty and no larger than 10 MiB.');
  const form = new FormData();
  form.append('file', file);
  const response = await fetch(ROOT, { method: 'POST', body: form, signal });
  return unwrap(response);
}

export async function getDataset(id, signal) {
  const response = await fetch(`${ROOT}${encodeURIComponent(id)}/`, { signal });
  return unwrap(response);
}

export async function getMeasurements(id, signal) {
  const response = await fetch(`${ROOT}${encodeURIComponent(id)}/measurements/`, { signal });
  return unwrap(response);
}

export async function getGeoJSON(id, signal) {
  const response = await fetch(`${ROOT}${encodeURIComponent(id)}/geojson/`, { signal });
  return unwrap(response);
}

export async function getDatasetBundle(id, signal) {
  const [metadata, measurements, geojson] = await Promise.all([
    getDataset(id, signal), getMeasurements(id, signal), getGeoJSON(id, signal),
  ]);
  return { metadata, measurements, geojson };
}

export const EXAMPLE_DATASETS = [
  { id: 'mixed', name: 'KML · Mixed geometries', file: 'mixed.kml', path: '/samples/mixed.kml', description: 'Point, route and parcel in one upload' },
  { id: 'plot', name: 'Shapefile · 100m square', file: 'plot-utm43n.zip', path: '/samples/plot-utm43n.zip', description: 'Reference polygon in projected coordinates' },
];

export async function sampleAsFile(sample, signal) {
  const response = await fetch(sample.path, { signal });
  if (!response.ok) throw new Error('Could not load sample dataset.');
  const blob = await response.blob();
  return new File([blob], sample.file, { type: sample.file.endsWith('.zip') ? 'application/zip' : 'application/vnd.google-earth.kml+xml' });
}

export function downloadCSV(fileName, measurements) {
  const fields = ['index', 'id', 'geometry_type', 'status', 'measurement_type', 'measurement_value', 'unit', 'source_crs', 'measurement_crs', 'error'];
  const csvEscape = (value) => `"${String(value ?? '').replaceAll('"', '""')}"`;
  const rows = (measurements?.measurements || []).map(item => [
    item.index, item.id, item.geometry_type, item.status, item.measurement?.type,
    item.measurement?.value, item.measurement?.unit, item.crs, item.measurement_crs, item.error,
  ].map(csvEscape).join(','));
  const csv = [fields.join(','), ...rows].join('\r\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${fileName.replace(/\.[^.]+$/, '').replace(/[^\w-]+/g, '-')}-measurements.csv`;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
