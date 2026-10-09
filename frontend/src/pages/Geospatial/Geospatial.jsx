import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { GeoJSON, MapContainer, TileLayer, ZoomControl, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {
  EXAMPLE_DATASETS, downloadCSV, getDatasetBundle, sampleAsFile, uploadDataset,
} from '../../services/geospatialService';
import './Geospatial.css';

const RECENT_KEY = 'aereo:geospatial:recent:v1';
const EMPTY = [];
const palette = { polygon: '#078f79', line: '#e1a13b', point: '#235ba4', unsupported: '#8995a5' };

const icons = {
  layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/></>,
  upload: <><path d="M12 16V3m0 0L7 8m5-5 5 5"/><path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/></>,
  file: <><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Z"/><path d="M13 2v7h7M8 13h8M8 17h6"/></>,
  check: <path d="m4 12 5 5L20 6"/>,
  alert: <><path d="M10 4 2 19a2 2 0 0 0 2 3h16a2 2 0 0 0 2-3L14 4a2 2 0 0 0-4 0Z"/><path d="M12 9v5m0 4h.01"/></>,
  map: <><path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3V6Z"/><path d="M9 3v15m6-12v15"/></>,
  area: <><path d="m4 6 7-3 9 5v10l-9 3-7-5Z"/><path d="m11 3 1 9 8 6"/></>,
  route: <><circle cx="6" cy="18" r="2"/><circle cx="18" cy="6" r="2"/><path d="M8 18h5a5 5 0 0 0 0-10h-2a5 5 0 0 1-5-5"/></>,
  pin: <><path d="M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/></>,
  ruler: <><path d="m22 7-7-7L1 14l7 7Z"/><path d="m7 8 3 3m1-7 3 3m1-7 3 3"/></>,
  crosshair: <><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="2"/><path d="M12 1v3m0 16v3M1 12h3m16 0h3"/></>,
  download: <><path d="M12 3v13m-5-5 5 5 5-5"/><path d="M4 18v3h16v-3"/></>,
  arrow: <><path d="M5 12h14m-6-6 6 6-6 6"/></>,
  external: <><path d="M14 4h6v6M20 4l-9 9"/><path d="M20 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h5"/></>,
  close: <path d="M5 5l14 14M19 5 5 19"/>,
  history: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5m4-1v6l4 2"/></>,
};

function Icon({ name, size = 20, className = '' }) {
  return <svg className={className} aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{icons[name] || icons.layers}</svg>;
}

function kindOf(type = '') {
  const label = type.toLowerCase();
  if (label.includes('polygon')) return 'polygon';
  if (label.includes('line')) return 'line';
  if (label.includes('point')) return 'point';
  return 'unsupported';
}

function formatMeasure(measurement, compact = false) {
  if (!measurement) return 'Not measured';
  const { value, unit } = measurement;
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'Unavailable';
  const format = n => n.toLocaleString('en-IN', { maximumFractionDigits: 3 });
  if (compact && unit === 'm2' && value >= 1000000) return `${format(value / 1000000)} km²`;
  if (compact && unit === 'm' && value >= 1000) return `${format(value / 1000)} km`;
  return `${format(value)} ${unit === 'm2' ? 'm²' : unit}`;
}

function featureName(item) {
  return String(item?.properties?.name || item?.properties?.Name || `Feature ${item?.index ?? item?.id ?? ''}`);
}

function Status({ status }) {
  const label = status === 'NOT_APPLICABLE' ? 'No measurement required' : status === 'FAILED' ? 'Needs attention' : status === 'MEASURED' ? 'Measured' : status || 'Unknown';
  return <span className={`gi-status gi-status-${String(status || '').toLowerCase()}`}>{label}</span>;
}

function Stat({ title, value, note, icon, variation }) {
  return <div className={`gi-stat ${variation ? `gi-stat-${variation}` : ''}`}><span className="gi-stat-icon"><Icon name={icon} size={21}/></span><div className="gi-stat-copy"><span className="gi-stat-label">{title}</span><strong className="gi-stat-value">{value}</strong><span className="gi-stat-note">{note}</span></div></div>;
}

function MapController({ features, selectedFeature, fitToken, selectionToken }) {
  const map = useMap();
  useEffect(() => {
    if (!features?.length) return;
    try {
      const bounds = L.geoJSON({ type: 'FeatureCollection', features }).getBounds();
      if (bounds.isValid()) map.fitBounds(bounds.pad(0.18), { padding: [36, 36], maxZoom: 17, animate: false });
    } catch { /* Unmappable features stay visible in the results table */ }
  }, [map, features, fitToken]);
  useEffect(() => {
    if (!selectedFeature?.geometry) return;
    try {
      const bounds = L.geoJSON(selectedFeature).getBounds();
      if (bounds.isValid()) map.fitBounds(bounds.pad(0.65), { maxZoom: 20, animate: true });
    } catch { /* Show details even when geometry cannot be mapped */ }
  }, [map, selectedFeature, selectionToken]);
  return null;
}

function GeometryMap({ geojson, datasetId, selectedId, setSelectedId, selectionToken }) {
  const [baseStyle, setBaseStyle] = useState('streets');
  const [fitToken, setFitToken] = useState(0);
  const features = useMemo(() => (geojson?.features || EMPTY).filter(item => item?.geometry && ['Point','MultiPoint','LineString','MultiLineString','Polygon','MultiPolygon'].includes(item.geometry.type)), [geojson]);
  const mapData = useMemo(() => ({ type: 'FeatureCollection', features }), [features]);
  const selectedFeature = features.find(item => String(item.id) === String(selectedId));
  const onStyle = useCallback(feature => {
    const selected = String(feature?.id) === String(selectedId);
    const type = kindOf(feature?.geometry?.type);
    return { color: palette[type], weight: selected ? 5 : 3.5, fillColor: palette[type], fillOpacity: selected ? 0.4 : 0.23, opacity: 1 };
  }, [selectedId]);
  const pointToLayer = useCallback((feature, latlng) => L.circleMarker(latlng, {
    radius: String(feature?.id) === String(selectedId) ? 11 : 8,
    color: '#ffffff', weight: 2.5, fillColor: palette.point, fillOpacity: 1,
  }), [selectedId]);
  return <div className="gi-map-wrap">
    <div className="gi-map-toolbar"><button className="gi-map-action" type="button" onClick={() => { setSelectedId(null); setFitToken(n => n + 1); }} disabled={!features.length}><Icon name="crosshair" size={17}/> Fit all features</button><div className="gi-map-style" role="group" aria-label="Map appearance"><button type="button" aria-pressed={baseStyle === 'geometry'} className={baseStyle === 'geometry' ? 'active' : ''} onClick={() => setBaseStyle('geometry')}>Geometry only</button><button type="button" aria-pressed={baseStyle === 'streets'} className={baseStyle === 'streets' ? 'active' : ''} onClick={() => setBaseStyle('streets')}>Streets</button></div></div>
    <div className={`gi-map-canvas ${baseStyle === 'geometry' ? 'is-geometry' : ''}`}>
      <MapContainer center={[20, 78]} zoom={4} maxZoom={21} zoomControl={false} scrollWheelZoom={true} className="gi-map">
        {baseStyle === 'streets' && <TileLayer key="streets" maxNativeZoom={19} maxZoom={21} attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/>}
        {!!features.length && <GeoJSON key={`${datasetId}:${selectedId ?? 'all'}`} data={mapData} style={onStyle} pointToLayer={pointToLayer} onEachFeature={(feature, layer) => { layer.on('click', () => setSelectedId(String(feature.id))); layer.bindTooltip(String(featureName(feature)).slice(0, 90), { sticky: true, opacity: 0.95 }); }}/>}
        <MapController features={features} selectedFeature={selectedFeature} fitToken={fitToken} selectionToken={selectionToken}/>
        <ZoomControl position="bottomright"/>
      </MapContainer>
      {!features.length && <div className="gi-map-no-data"><Icon name="map" size={30}/><strong>No map geometry available</strong><p>{geojson ? 'The file has no features with safely mappable coordinates.' : 'Upload a dataset to display its features.'}</p></div>}
      <div className="gi-map-legend"><span><i className="gi-legend-dot polygon"/>Polygon</span><span><i className="gi-legend-dot line"/>Line</span><span><i className="gi-legend-dot point"/>Point</span></div>
    </div>
    <div className="gi-map-caption">Geometry display: WGS84 (EPSG:4326) <span>{baseStyle === 'streets' ? 'Basemap © OpenStreetMap contributors' : 'Geometry-only view · no map key required'}</span></div>
  </div>;
}

function FeaturePanel({ item, featureCount }) {
  if (!item) return <div className="gi-detail"><div className="gi-eyebrow-mini">SELECTED FEATURE</div><div className="gi-detail-empty"><span><Icon name="crosshair" size={25}/></span><strong>Select a feature to inspect</strong><p>Choose a row from the measurement records or click a geometry on the map. Each measurement is linked to its source CRS and projected calculation.</p><small>{featureCount} features available for inspection</small></div></div>;
  const props = Object.entries(item.properties || {}).filter(([key]) => !key.startsWith('_')).slice(0, 16);
  return <div className="gi-detail"><div className="gi-eyebrow-mini">SELECTED FEATURE</div><h3>{featureName(item)}</h3><div className="gi-detail-measure">{formatMeasure(item.measurement)}</div><Status status={item.status}/><dl className="gi-properties"><div><dt>Geometry type</dt><dd>{item.geometry_type}</dd></div><div><dt>Source CRS</dt><dd>{item.crs || 'Not provided'}</dd></div><div><dt>Measurement CRS</dt><dd>{item.measurement_crs || 'Not applicable'}</dd></div>{props.map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{typeof value === 'object' ? JSON.stringify(value) : String(value ?? '—')}</dd></div>)}</dl>{item.error && <div className="gi-inline-warning"><Icon name="alert" size={18}/><div><strong>Feature could not be measured</strong><p>{item.error}</p></div></div>}{item.warnings?.length > 0 && <div className="gi-inline-warning"><Icon name="alert" size={18}/><div><strong>Measurement note</strong><p>{item.warnings.join(' · ')}</p></div></div>}</div>;
}

function readRecent() {
  try {
    const saved = JSON.parse(localStorage.getItem(RECENT_KEY) || '[]');
    return Array.isArray(saved) ? saved.filter(item => /^[a-f0-9]{32}$/.test(item.id)).slice(0, 5) : [];
  } catch { return []; }
}

export default function Geospatial() {
  const fileInput = useRef(null);
  const controllerRef = useRef(null);
  const resultRef = useRef(null);
  const [dataset, setDataset] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [selectionToken, setSelectionToken] = useState(0);
  const [busy, setBusy] = useState(false);
  const [busyText, setBusyText] = useState('');
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [dragging, setDragging] = useState(false);
  const [recent, setRecent] = useState(readRecent);
  useEffect(() => () => controllerRef.current?.abort(), []);

  const inspectFeature = useCallback(item => {
    setSelectedId(String(item.id));
    setSelectionToken(current => current + 1);
    document.getElementById('explore')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, []);

  const measurements = dataset?.measurements?.measurements ?? EMPTY;
  const displayed = useMemo(() => measurements.filter(item => {
    const typeMatches = filter === 'all' || kindOf(item.geometry_type) === filter || (filter === 'failed' && item.status === 'FAILED');
    return typeMatches && `${item.id} ${item.geometry_type} ${JSON.stringify(item.properties)}`.toLowerCase().includes(query.trim().toLowerCase());
  }), [measurements, query, filter]);
  const selected = measurements.find(item => String(item.id) === String(selectedId)) || null;
  const measured = measurements.filter(item => item.status === 'MEASURED');
  const failed = measurements.filter(item => item.status === 'FAILED');
  const polygons = measured.filter(item => item.measurement?.unit === 'm2');
  const lines = measured.filter(item => item.measurement?.unit === 'm');
  const totalArea = polygons.reduce((n, item) => n + item.measurement.value, 0);
  const totalLength = lines.reduce((n, item) => n + item.measurement.value, 0);

  const saveRecent = useCallback(info => {
    const list = [{ id: info.id, filename: info.filename, created_at: info.created_at }, ...readRecent().filter(item => item.id !== info.id)].slice(0, 5);
    setRecent(list);
    try { localStorage.setItem(RECENT_KEY, JSON.stringify(list)); } catch { /* Storage may be disabled */ }
  }, []);

  const run = useCallback(async fn => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setBusy(true);
    setBusyText('Preparing dataset…');
    setError('');
    setDataset(null);
    setSelectedId(null);
    try {
      const result = await fn(controller.signal);
      if (controllerRef.current !== controller) return;
      setDataset(result);
      setQuery('');
      setFilter('all');
      requestAnimationFrame(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
    } catch (exception) {
      if (controllerRef.current === controller && exception?.name !== 'AbortError') setError(exception?.message || 'Unable to process the selected file.');
    } finally {
      if (controllerRef.current === controller) { setBusy(false); setBusyText(''); }
    }
  }, []);

  const upload = useCallback(file => {
    if (!file) return;
    void run(async signal => {
      setBusyText('Validating and measuring geospatial features…');
      const info = await uploadDataset(file, signal);
      setBusyText('Retrieving geometries, measurements and CRS information…');
      const result = await getDatasetBundle(info.id, signal);
      saveRecent(info);
      return result;
    });
  }, [run, saveRecent]);

  const trySample = useCallback(sample => {
    void run(async signal => {
      setBusyText('Loading sample file…');
      const file = await sampleAsFile(sample, signal);
      setBusyText('Processing example through the same upload API…');
      const info = await uploadDataset(file, signal);
      const result = await getDatasetBundle(info.id, signal);
      saveRecent(info);
      return result;
    });
  }, [run, saveRecent]);

  const openRecent = useCallback(file => {
    void run(async signal => {
      setBusyText('Retrieving saved analysis…');
      return getDatasetBundle(file.id, signal);
    });
  }, [run]);

  const onDrop = event => {
    event.preventDefault();
    setDragging(false);
    if (!busy) upload(event.dataTransfer.files?.[0]);
  };

  return <div className="gi-page">
    <header className="gi-header"><Link className="gi-brand" to="/geospatial" aria-label="GeoInsight analysis home"><span className="gi-brand-symbol"><Icon name="layers" size={23}/></span><span className="gi-brand-name">Geo<span>Insight</span><small>GEOSPATIAL MEASUREMENT WORKSPACE</small></span></Link><nav className="gi-header-actions" aria-label="Resources"><span className="gi-header-label"><span className="gi-header-dot"/> FastAPI · Shapely · PROJ</span><a href="/docs" target="_blank" rel="noreferrer">API reference <Icon name="external" size={15}/></a></nav></header>
    <main className="gi-main">
      <section className="gi-intro"><div className="gi-eyebrow"><Icon name="crosshair" size={15}/> GEOINSIGHT / ANALYSIS WORKSPACE</div><h1>Geospatial measurement, <span>made verifiable.</span></h1><p>Convert survey files into accurate area and distance reports. Inspect geometries on a map, understand the CRS transformation and trace each result to its source feature.</p><div className="gi-intro-meta"><span><Icon name="check" size={15}/> KML & zipped Shapefile</span><span><Icon name="check" size={15}/> Projected measurements</span><span><Icon name="check" size={15}/> API-verifiable results</span></div></section>
      <nav className="gi-workflow" aria-label="Analysis steps"><a className="active" href="#import"><b>01</b><span><strong>Import</strong><small>Upload or try sample</small></span></a><a href="#explore" className={dataset ? 'active' : ''}><b>02</b><span><strong>Explore</strong><small>Inspect mapped geometry</small></span></a><a href="#records" className={dataset ? 'active' : ''}><b>03</b><span><strong>Verify</strong><small>Review and export results</small></span></a></nav>
      <section id="import" className="gi-import-section"><div className="gi-section-head"><div><div className="gi-eyebrow-mini">STEP 01 / INPUT</div><h2>Import your geospatial file</h2><p>Choose a file from your device or use one of the provided demonstration datasets.</p></div><span className="gi-upload-limit">Maximum upload: 10 MiB</span></div>
        <div className="gi-import-grid"><div className={`gi-upload ${dragging ? 'gi-upload-dragging' : ''}`} onDragEnter={event => { event.preventDefault(); setDragging(true); }} onDragOver={event => event.preventDefault()} onDragLeave={event => { event.preventDefault(); setDragging(false); }} onDrop={onDrop}><span className="gi-upload-icon"><Icon name="upload" size={27}/></span><h3>Drop a dataset to begin</h3><p>Accepted formats: <strong>.kml</strong> or <strong>.zip</strong> containing a Shapefile</p><input ref={fileInput} type="file" accept=".kml,.zip" hidden onChange={event => { upload(event.target.files?.[0]); event.target.value = ''; }} aria-label="Choose geospatial file"/><button type="button" className="gi-btn-primary" disabled={busy} onClick={() => fileInput.current?.click()}><Icon name="file" size={18}/>{busy ? 'Processing…' : 'Choose file'}</button><small>Your file is processed by the FastAPI measurement service.</small></div>
          <div className="gi-samples"><div className="gi-samples-head"><span className="gi-eyebrow-mini">TRY AN EXAMPLE</span><h3>Start with sample data</h3><p>Sample buttons upload real files through the same API—not precomputed display values.</p></div>{EXAMPLE_DATASETS.map((sample, index) => <button key={sample.id} className="gi-sample-row" type="button" disabled={busy} onClick={() => trySample(sample)}><span className="gi-sample-number">0{index + 1}</span><span><strong>{sample.name}</strong><small>{sample.description}</small></span><Icon name="arrow" size={17}/></button>)}</div></div>
        {busy && <div className="gi-loading" role="status"><span className="gi-spinner"/>{busyText}</div>}
        {error && <div role="alert" className="gi-error"><Icon name="alert" size={20}/><div><strong>File could not be processed</strong><p>{error}</p></div><button type="button" onClick={() => setError('')} aria-label="Dismiss error"><Icon name="close" size={18}/></button></div>}
      </section>
      {!dataset && !busy && <div className="gi-waiting"><span><Icon name="map" size={25}/></span><div><strong>Ready for analysis</strong><p>Upload a KML or zipped Shapefile to unlock an interactive map, measured features and a downloadable report.</p></div></div>}
      {dataset && <section ref={resultRef} className="gi-results" aria-label="Geospatial analysis results" aria-live="polite"><div className="gi-report-head"><div><div className="gi-eyebrow-mini">ANALYSIS COMPLETE / {dataset.metadata.id.slice(0, 8)}</div><h2>{dataset.metadata.filename}</h2><p>{dataset.metadata.feature_count} features extracted <span aria-hidden="true">·</span> Source CRS: <strong>{dataset.metadata.crs || 'Unknown'}</strong></p></div><div className="gi-report-actions"><span className={`gi-result-status ${failed.length ? 'gi-result-attention' : ''}`}><Icon name={failed.length ? 'alert' : 'check'} size={16}/>{failed.length ? `${failed.length} feature${failed.length === 1 ? '' : 's'} need attention` : 'Processing complete'}</span><button className="gi-btn-outline" type="button" onClick={() => downloadCSV(dataset.metadata.filename, dataset.measurements)}><Icon name="download" size={18}/> Export CSV</button></div></div>
        {failed.length > 0 && <div role="status" className="gi-result-warning"><Icon name="alert" size={20}/><span>{failed.length} feature{failed.length !== 1 ? 's' : ''} could not be measured. Select the affected feature in the table to review the reason. Valid measurements are preserved.</span></div>}
        <div className="gi-stats"><Stat icon="layers" title="Extracted features" value={dataset.metadata.feature_count.toLocaleString()} note="Features in uploaded dataset"/><Stat icon="area" title="Polygon area" value={polygons.length ? formatMeasure({ value: totalArea, unit: 'm2' }, true) : '—'} note={`${polygons.length} successfully measured polygon${polygons.length === 1 ? '' : 's'}`}/><Stat icon="route" title="Line length" value={lines.length ? formatMeasure({ value: totalLength, unit: 'm' }, true) : '—'} note={`${lines.length} successfully measured line${lines.length === 1 ? '' : 's'}`}/><Stat icon={failed.length ? 'alert' : 'check'} title="Measured features" value={`${measured.length} / ${measurements.length}`} note={`${failed.length} failed · ${measurements.length - measured.length - failed.length} not applicable`} variation={failed.length ? 'warning' : ''}/></div>
        <section id="explore" className="gi-analysis-section"><div className="gi-section-head"><div><div className="gi-eyebrow-mini">STEP 02 / EXPLORE</div><h2>Geometry explorer</h2><p>See every mappable feature and select one to inspect its calculations and original attributes.</p></div><span className="gi-measurement-note"><Icon name="crosshair" size={16}/> Map in EPSG:4326</span></div><div className="gi-explorer-grid"><div className="gi-map-panel"><GeometryMap geojson={dataset.geojson} datasetId={dataset.metadata.id} selectedId={selectedId} setSelectedId={setSelectedId} selectionToken={selectionToken}/></div><div className="gi-detail-panel"><FeaturePanel item={selected} featureCount={measurements.length}/></div></div></section>
        <section id="records" className="gi-records"><div className="gi-records-head"><div><div className="gi-eyebrow-mini">STEP 03 / VERIFY</div><h2>Feature measurements</h2><p>Every row represents a parsed feature. Use the filters, then select a row to inspect its provenance on the map.</p></div><div className="gi-table-filters"><input aria-label="Search features" placeholder="Search features" value={query} onChange={event => setQuery(event.target.value)}/><select aria-label="Filter features" value={filter} onChange={event => setFilter(event.target.value)}><option value="all">All features</option><option value="polygon">Polygons</option><option value="line">Lines</option><option value="point">Points</option><option value="failed">Failed</option></select></div></div><div className="gi-table-scroll"><table className="gi-table"><thead><tr><th>Feature</th><th>Geometry</th><th>Measurement</th><th>Status</th><th>Inspect</th></tr></thead><tbody>{displayed.length ? displayed.map(item => <tr key={`${item.index}:${item.id}`} className={String(item.id) === String(selectedId) ? 'selected' : ''} tabIndex={0} title={`Inspect ${featureName(item)} on the map`} onClick={() => inspectFeature(item)} onKeyDown={event => { if (event.target === event.currentTarget && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); inspectFeature(item); } }}><td><strong>{featureName(item)}</strong><small>ID: {item.id}</small></td><td><span className={`gi-geometry gi-geometry-${kindOf(item.geometry_type)}`}>{item.geometry_type}</span></td><td>{formatMeasure(item.measurement)}</td><td><Status status={item.status}/></td><td><button type="button" className="gi-inspect-btn" onClick={event => { event.stopPropagation(); inspectFeature(item); }} aria-label={`Inspect ${featureName(item)}`}><Icon name="crosshair" size={18}/></button></td></tr>) : <tr><td colSpan={5} className="gi-empty-table">No features match your filters.</td></tr>}</tbody></table></div></section>
        <div className="gi-provenance"><Icon name="ruler" size={22}/><div><strong>How were the measurements calculated?</strong><p>Polygon area and line length are computed on projected geometries in metric units. Inspect any feature to see its source CRS and measurement CRS. The map uses WGS84 coordinates for display only.</p></div><a href="/docs" target="_blank" rel="noreferrer">Inspect REST API <Icon name="external" size={15}/></a></div>
      </section>}
      {recent.length > 0 && <section className="gi-recent"><div className="gi-section-head"><div><div className="gi-eyebrow-mini">REVISIT</div><h2>Recent analyses</h2><p>These five links are saved in this browser. Results are retrieved from the API, not browser-generated.</p></div></div><div className="gi-recent-list">{recent.map(file => <button type="button" key={file.id} disabled={busy} onClick={() => openRecent(file)}><Icon name="history" size={19}/><span><strong>{file.filename}</strong><small>ID: {file.id.slice(0, 8)}</small></span><Icon name="arrow" size={17}/></button>)}</div></section>}
      <footer className="gi-footer"><span><Icon name="layers" size={17}/> GeoInsight · Geospatial measurement API</span><span>Built with FastAPI, Shapely, PROJ & React Leaflet</span><a href="/docs" target="_blank" rel="noreferrer">API documentation <Icon name="external" size={14}/></a></footer>
    </main>
  </div>;
}
