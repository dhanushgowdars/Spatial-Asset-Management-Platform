import { useEffect, useMemo, useRef, useState } from 'react';
import { GeoJSON, MapContainer, TileLayer, ZoomControl, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import GeoNav from '../GeoNav/GeoNav';
import { uploadDataset } from '../../services/geospatialService';
import { DEMOS, verifyDemo } from './demoContracts.mjs';
// GEOINSIGHT_DERIVED_PROVENANCE_V1
import { sourceMeasurement, sourceDetail, qualityDetail, qualityCrsNote, withDerivedProvenance } from './presentation.mjs';
import './SpatialIntelligence.css';

const RECENT_KEY = 'aereo:geospatial:recent:v1';
const CONFIG = {
  quality: { number: '02', eyebrow: 'QUALITY ASSURANCE', heading: 'Survey quality & evidence', subtitle: 'Review every survey feature, coordinate problem and measurement in one place.', roles: [['survey','Survey dataset']] },
  compare: { number: '03', eyebrow: 'PLAN VS ACTUAL', heading: 'Survey change detection', subtitle: 'Compare surveyed footprints with mathematically verifiable added, removed and overlapping regions.', roles: [['baseline','Baseline survey'], ['current','Current survey']] },
  topology: { number: '04', eyebrow: 'SPATIAL VALIDATION', heading: 'Polygon topology', subtitle: 'Find overlapping parcels and compare survey coverage against an optional site boundary.', roles: [['survey','Polygon survey'], ['reference','Reference boundary · optional']] },
  routes: { number: '05', eyebrow: 'INFRASTRUCTURE ANALYSIS', heading: 'Routes & restricted zones', subtitle: 'Measure road or utility routes inside and outside surveyed land-use zones.', roles: [['route','Route lines'], ['zone','Zone polygons']] },
};
const COLORS = { added:'#159b70', removed:'#e55758', unchanged_overlap:'#488fd8', overlap_area:'#e79528', uncovered_within_reference:'#e55758', outside_reference:'#8e70ce', baseline_outline:'#466dbc', current_outline:'#098f8a', source_parcel:'#667f95', reference_outline:'#8e70ce', source_route:'#244968', source_zone:'#d79a2a', route_zone_intersection:'#099c7c', survey_polygon:'#128c81', survey_line:'#c98d24', survey_point:'#3879c9' };
const NAMES = { added:'Added area', removed:'Removed area', unchanged_overlap:'Unchanged overlap', overlap_area:'Overlapping parcels', uncovered_within_reference:'Uncovered site', outside_reference:'Outside boundary', baseline_outline:'Baseline boundary', current_outline:'Current boundary', source_parcel:'Survey parcel', reference_outline:'Site reference', source_route:'Original route', source_zone:'Zone boundary', route_zone_intersection:'Route inside zone', survey_polygon:'Survey polygon', survey_line:'Survey line', survey_point:'Survey point' };
const num = value => typeof value === 'number' && Number.isFinite(value) ? (Math.abs(value) < 0.00000001 ? 0 : value).toLocaleString('en-IN', { maximumFractionDigits:2 }) : '—';
const area = value => `${num(value)} m²`;
const metres = value => `${num(value)} m`;
const pct = value => `${num(value)}%`;
const idValid = value => typeof value === 'string' && /^[a-f\d]{32}$/i.test(value);
function recentFiles() { try { const value = JSON.parse(localStorage.getItem(RECENT_KEY) || '[]'); return Array.isArray(value) ? value.filter(x => idValid(x?.id)).slice(0,12) : []; } catch { return []; } }
function remember(file) { const value = [{ id:file.id, filename:file.filename }, ...recentFiles().filter(x => x.id !== file.id)].slice(0,12); try { localStorage.setItem(RECENT_KEY, JSON.stringify(value)); } catch { /* browser storage disabled */ } return value; }
async function api(path, options) { const r = await fetch(path, options); if (!r.ok) { let text = `HTTP ${r.status}`; try { const body = await r.json(); text = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body); } catch { /* preserve status */ } throw new Error(text); } return r.json(); }
function saveJson(name, data) { const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type:'application/json' })); const link = document.createElement('a');link.href=url;link.download=name;document.body.append(link);link.click();link.remove();setTimeout(() => URL.revokeObjectURL(url),1000); }
// The four intelligence modules share one card layout. Measurements always come from the API.
const METRIC_META = {
  'Total features':['layers','Source features returned by the API'],
  'Measured':['check','Features with an area or length result'],
  'Not applicable':['point','Measurements not required for these geometries'],
  'Failed':['alert','Features that could not be measured'],
  'Area total':['area','Measured polygon area combined'],
  'Line total':['line','Measured line length combined'],
  'Baseline':['area','Baseline footprint area'],
  'Current':['area','Current footprint area'],
  'Added area':['plus','Area in current but not in baseline'],
  'Removed area':['minus','Area in baseline but not in current'],
  'Unchanged overlap':['overlap','Area common to both surveys'],
  'Net change':['change','Current area minus baseline area'],
  'Intersection / union':['percent','Overlap as a percentage of the union'],
  'Overlapping pairs':['overlap','Pairs of survey parcels that overlap'],
  'Reference gaps evaluated':['check','Site-boundary comparison performed'],
  'Uncovered site area':['area','Reference land not covered by survey'],
  'Outside site boundary':['alert','Surveyed land outside the reference boundary'],
  'Routes':['line','Route features in the input'],
  'Zones':['area','Zone features in the input'],
  'Crossing routes':['change','Routes intersecting one or more zones'],
  'Total length inside zones':['line','Combined route length within zones'],
  'Total length outside zones':['line','Combined route length beyond zones'],
};
function MetricGlyph({kind}) {
  const common={viewBox:'0 0 24 24',width:23,height:23,fill:'none',stroke:'currentColor',strokeWidth:1.9,strokeLinecap:'round',strokeLinejoin:'round','aria-hidden':true};
  const paths={
    layers:<><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/></>,
    check:<><circle cx="12" cy="12" r="9"/><path d="m7.5 12 3.1 3.2 6-6.5"/></>,
    point:<><circle cx="12" cy="12" r="5"/><path d="M12 2v4m0 12v4M2 12h4m12 0h4"/></>,
    alert:<><path d="m12 3 10 18H2L12 3Z"/><path d="M12 9v5m0 3v.2"/></>,
    area:<><path d="M4 5h16v14H4z"/><path d="m4 11 6-6m4 14 6-6"/></>,
    line:<><path d="M3 17h5l4-10 4 9h5"/><circle cx="3" cy="17" r="1.2"/><circle cx="21" cy="16" r="1.2"/></>,
    plus:<><path d="M12 4v16M4 12h16"/></>,
    minus:<><path d="M4 12h16"/></>,
    overlap:<><rect x="3" y="3" width="13" height="13" rx="2"/><rect x="8" y="8" width="13" height="13" rx="2"/></>,
    percent:<><path d="M5 19 19 5"/><circle cx="7" cy="7" r="2"/><circle cx="17" cy="17" r="2"/></>,
    change:<><path d="M4 7h16m0 0-4-4m4 4-4 4M20 17H4m0 0 4-4m-4 4 4 4"/></>,
  };
  return <svg {...common}>{paths[kind]||paths.layers}</svg>;
}
function Metric({ label, value, hint }) {
  const text = String(value);
  const parts = text.match(/^(.*?)( m²| m|%)$/);
  const [icon,defaultHint]=METRIC_META[label]||['layers','Calculated using the selected GIS inputs'];
  return <article className="sx-metric" title={`${label}: ${text}`} aria-label={`${label}: ${text}`}>
    <span className="sx-metric-icon"><MetricGlyph kind={icon}/></span>
    <div className="sx-metric-content"><span className="sx-metric-label">{label}</span>
      <strong className={text.length > 15 ? 'sx-metric-value is-long' : 'sx-metric-value'}><span className="sx-metric-number">{parts ? parts[1] : text}</span>{parts && <span className="sx-metric-unit">{parts[2].trim()}</span>}</strong>
      <small className="sx-metric-hint">{hint||defaultHint}</small>
    </div>
  </article>;
}

// Use stable file identities, not feature labels alone. Leaflet GeoJSON is immutable after mount.
const MAP_STYLE = {
  baseline_outline: 'boundary', current_outline: 'boundary', reference_outline: 'boundary',
  source_parcel: 'boundary', source_zone: 'boundary', source_route: 'line', survey_line: 'line',
  route_zone_intersection: 'line', survey_point: 'point',
};
const MAP_EXPLANATION = {
  compare: 'Dashed outlines show the original surveys. Solid tinted areas show geometry added, removed or unchanged between them.',
  topology: 'Dashed outlines show survey parcels and the optional site boundary. Filled colors identify overlaps, uncovered site area or survey area outside the site.',
  routes: 'The dark line shows the complete route. Dashed amber boundaries are restricted zones; green lines mark route sections inside them.',
  quality: 'Colored geometry identifies survey polygons, lines and points. A selection uses a dark outline without changing its category color.',
};

function MapViewport({ features, selected, onlySelected, dataKey, fitRequest }) {
  const map = useMap();
  const lastFit = useRef('');
  const ids = features.map(f=>f._key).join('|');
  // Maps mounted in lazy layouts may initially have an outdated container size.
  useEffect(() => {
    const el = map.getContainer();
    let frame=0;
    const resize=()=>{cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>map.invalidateSize({pan:false,animate:false}));};
    const observer = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(resize) : null;
    observer?.observe(el);
    window.addEventListener('resize',resize);
    resize();
    return ()=>{observer?.disconnect();window.removeEventListener('resize',resize);cancelAnimationFrame(frame);};
  },[map]);
  useEffect(()=>{
    const key=`${dataKey}|${ids}|${onlySelected?selected:'all'}|${fitRequest}`;
    if(lastFit.current===key) return;
    lastFit.current=key;
    const visible=onlySelected&&selected?features.filter(f=>f._key===selected):features;
    if(!visible.length) return;
    try {
      const bounds=L.geoJSON({type:'FeatureCollection',features:visible}).getBounds();
      if(bounds.isValid()){
        map.invalidateSize({pan:false,animate:false});
        // Additional breathing room prevents the shape from touching the viewport boundary.
        map.fitBounds(bounds.pad(.24),{maxZoom:18,animate:false,padding:[26,26]});
      }
    } catch { /* Unmappable input is documented in quality results. */ }
  },[map,features,ids,selected,onlySelected,dataKey,fitRequest]);
  return null;
}
function SurveyMap({ features, title, mode, datasetKey, selected, onSelect }) {
  const [streets,setStreets]=useState(true);
  const [onlySelected,setOnlySelected]=useState(false);
  const [fitRequest,setFitRequest]=useState(0);
  const selectedMappable=features.some(f=>f._key===selected);
  const displayed=useMemo(()=>onlySelected&&selectedMappable?features.filter(f=>f._key===selected):features,[features,onlySelected,selectedMappable,selected]);
  const data=useMemo(()=>({type:'FeatureCollection',features:displayed}),[displayed]);
  const layerKey=`${datasetKey}|${displayed.map(f=>f._key).join('|')}`;
  const selectedFeature=displayed.find(f=>f._key===selected);
  const legend=[...new Set(features.map(f=>f._category))].filter(k=>COLORS[k]);
  const describe=f=>NAMES[f._category] || f.properties?.name || f.properties?.Name || 'Survey feature';
  const style=f=>{
    const kind=MAP_STYLE[f._category]||'area';
    const color=COLORS[f._category]||'#087f73';
    const focused=Boolean(selected&&f._key===selected);
    const outline=kind==='boundary';
    return {
      color:focused?'#123e57':color,
      weight:focused?5.3:outline?3:kind==='line'?4.7:2.8,
      fillColor:color,
      // Boundaries remain transparent; only actual result regions have colored fills.
      fillOpacity:outline||kind==='line'?0:focused?.59:.43,
      opacity:selected&&!focused?.72:1,
      dashArray:focused?undefined:outline?'8 5':undefined,
      lineCap:'round',lineJoin:'round',
    };
  };
  return <section className="sx-map-card" aria-label={title}>
    <div className="sx-map-toolbar">
      <div><h3>{title}</h3><p>Explore every mapped layer. Select a shape or table row to inspect its evidence.</p></div>
      <div className="sx-map-actions" role="group" aria-label="Map display controls">
        <button type="button" onClick={()=>{setOnlySelected(false);setFitRequest(n=>n+1);}} title="Fit the full dataset in the map">⌖ Fit all</button>
        <button type="button" aria-pressed={onlySelected} className={onlySelected?'active':''} disabled={!selectedMappable} onClick={()=>{setOnlySelected(v=>!v);setFitRequest(n=>n+1);}}>Focus selection</button>
        <button type="button" aria-pressed={streets} className={streets?'active':''} onClick={()=>setStreets(v=>!v)}>{streets?'Streets on':'Streets off'}</button>
      </div>
    </div>
    <div className="sx-map-canvas">
      <MapContainer center={[12.2,76.6]} zoom={5} zoomControl={false} scrollWheelZoom={false} className="sx-leaflet">
        {streets&&<TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'/>}
        {displayed.length>0&&<GeoJSON key={layerKey} data={data} style={style} pointToLayer={(f,latlng)=>{const focus=f._key===selected;const c=COLORS[f._category]||'#367cc5';return L.circleMarker(latlng,{radius:focus?10:7,color:focus?'#123e57':c,fillColor:c,fillOpacity:focus?1:.84,weight:focus?4:2});}} onEachFeature={(f,layer)=>{layer.on('click',()=>onSelect(f._key));layer.bindTooltip(describe(f),{sticky:true});}}/>}
        {selectedFeature&&<GeoJSON key={`highlight-${layerKey}-${selected}`} data={{type:'FeatureCollection',features:[selectedFeature]}} style={{color:'#123e57',weight:5.7,fillOpacity:0}} pointToLayer={(f,latlng)=>L.circleMarker(latlng,{radius:11,color:'#123e57',fillColor:COLORS[f._category]||'#087d70',fillOpacity:1,weight:4})} interactive={false}/>}
        <MapViewport features={features} selected={selected} onlySelected={onlySelected} dataKey={datasetKey} fitRequest={fitRequest}/>
        <ZoomControl position="bottomright"/>
      </MapContainer>
      {!features.length&&<div className="sx-map-empty">No valid mappable geometries. Review the quality findings and source feature table.</div>}
    </div>
    <div className="sx-map-legend-panel" aria-label="Map symbology and legend">
      <div className="sx-map-legend-label">MAP LEGEND</div>
      <div className="sx-legend">{legend.map(k=>{const kind=MAP_STYLE[k]||'area';return <span key={k} title={`${NAMES[k]} · ${kind==='boundary'?'dashed outline':kind==='line'?'line':kind==='point'?'point marker':'filled result area'}`}><i className={`sx-symbol sx-symbol-${kind}`} style={{'--symbol-color':COLORS[k]}} aria-hidden="true"/><b>{NAMES[k]}</b></span>;})}</div>
      <p className="sx-map-interpretation">{MAP_EXPLANATION[mode]} <strong>Dark border = selected feature.</strong></p>
    </div>
  </section>;
}
function mapLayer(collection, category, prefix) { return (collection?.features||[]).filter(f=>f?.geometry).map((f,i)=>({ ...f, _category:category||f.properties?.category||'survey_polygon',_key:`${prefix}-${i}`,properties:{...f.properties} })); }
function analysisLayer(result,mode) { const data = mode==='compare'?result.change_geojson:mode==='topology'?result.geojson:result.intersection_geojson;return (data?.features||[]).filter(f=>f?.geometry).map((f,i)=>({ ...f,_category: mode==='routes'?'route_zone_intersection':f.properties?.category||'overlap_area',_key:`analysis-${i}` })).map(feature => withDerivedProvenance(feature, result, mode)); }

function Verification({ verification }) {
  if (!verification) return null;
  const passed = verification.checks.filter(check => check.pass).length;
  return <section className={`sx-sample-verification ${verification.ok ? 'is-passing' : 'is-failing'}`} role="status" aria-label="Verified sample test results">
    <div className="sx-sample-verification-header">
      <span className="sx-sample-verification-icon" aria-hidden="true">{verification.ok ? '✓' : '!'}</span>
      <div className="sx-sample-verification-copy">
        <span className="sx-sample-verification-kicker">INDEPENDENT SAMPLE CHECK</span>
        <h3>{verification.ok ? 'Sample results verified' : 'Sample verification needs review'}</h3>
        <p>{verification.message}</p>
      </div>
      <span className="sx-sample-verification-score">{passed} / {verification.checks.length} checks matched</span>
    </div>
    <details className="sx-sample-verification-details">
      <summary>Compare expected and actual values <span aria-hidden="true">↓</span></summary>
      <div className="sx-sample-checks">
        {verification.checks.map(check => <div className={`sx-sample-check ${check.pass ? 'is-passing' : 'is-failing'}`} key={check.label}>
          <span className="sx-sample-check-icon" aria-hidden="true">{check.pass ? '✓' : '!'}</span>
          <div><strong>{check.label}</strong><small>Expected</small><b>{String(check.expected)}</b><small>API result</small><b>{String(check.actual ?? 'missing')}</b></div>
        </div>)}
      </div>
    </details>
  </section>;
}
const MAX_SPATIAL_UPLOAD_BYTES = 10 * 1024 * 1024;
const SUPPORTED_SPATIAL_FILE = /\.(kml|geojson|kmz|zip)$/i;

function RolePicker({ label, role, selected, onSelect, files, allowed, onUpload, disabled }) {
  const fileInput = useRef(null);
  const dragDepth = useRef(0);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const unavailable = disabled || busy;
  const compatible = files.filter(f => allowed === 'any' || (Array.isArray(f.kinds) && f.kinds.includes(allowed)));

  const submitFile = async (file, count = 1) => {
    if (!file || unavailable) return;
    if (count !== 1) {
      setFeedback({ type: 'error', message: 'Upload one dataset at a time.' });
      return;
    }
    if (!SUPPORTED_SPATIAL_FILE.test(file.name)) {
      setFeedback({ type: 'error', message: 'Unsupported file. Choose KML, GeoJSON, KMZ or a zipped Shapefile.' });
      return;
    }
    if (file.size > MAX_SPATIAL_UPLOAD_BYTES) {
      setFeedback({ type: 'error', message: 'This file exceeds the 10 MiB upload limit.' });
      return;
    }
    setFeedback(null);
    setBusy(true);
    try {
      await onUpload(role, file);
      setFeedback({ type: 'success', message: `${file.name} uploaded and selected for analysis.` });
    } catch (error) {
      setFeedback({ type: 'error', message: error?.message || 'Upload failed. Please try another file.' });
    } finally {
      setBusy(false);
    }
  };

  const clearDrag = () => {
    dragDepth.current = 0;
    setDragging(false);
  };
  const browse = () => { if (!unavailable) fileInput.current?.click(); };

  return <div className={`sx-picker${selected ? ' has-selection' : ''}`}>
    <div className="sx-picker-main">
      <div className="sx-picker-label-row">
        <label htmlFor={`sx-${role}`}>{label}</label>
        <button type="button" className="sx-clear-input" disabled={unavailable || !selected} onClick={() => { setFeedback(null); onSelect(role, ''); }} aria-label={`Clear ${label.toLowerCase()} selection`}>Clear selection</button>
      </div>
      <p className="sx-picker-help">Select a previously uploaded, compatible dataset</p>
      <div className="sx-picker-row">
        <select id={`sx-${role}`} value={selected || ''} disabled={unavailable} onChange={e => { setFeedback(null); onSelect(role, e.target.value); }}>
          <option value="">Choose a compatible dataset</option>
          {compatible.map(f => <option key={f.id} value={f.id}>{f.filename} · {f.id.slice(0, 8)}</option>)}
        </select>
      </div>
      <small className="sx-picker-footnote">{selected ? '✓ Dataset selected — ready for analysis' : 'Choose a saved dataset, or upload one using the area beside this field.'}</small>
    </div>
    <div
      className={`sx-upload-dropzone${dragging ? ' is-dragging' : ''}${unavailable ? ' is-disabled' : ''}`}
      role="button"
      tabIndex={unavailable ? -1 : 0}
      aria-disabled={unavailable}
      aria-busy={busy}
      aria-label={`Upload ${label}: drop a file here or browse files`}
      onClick={browse}
      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); browse(); } }}
      onDragEnter={e => { e.preventDefault(); e.stopPropagation(); if (!unavailable) { dragDepth.current += 1; setDragging(true); } }}
      onDragOver={e => { e.preventDefault(); e.stopPropagation(); e.dataTransfer.dropEffect = unavailable ? 'none' : 'copy'; }}
      onDragLeave={e => { e.preventDefault(); e.stopPropagation(); if (dragDepth.current > 0) dragDepth.current -= 1; if (!dragDepth.current) setDragging(false); }}
      onDrop={e => { e.preventDefault(); e.stopPropagation(); clearDrag(); if (!unavailable) void submitFile(e.dataTransfer.files?.[0], e.dataTransfer.files?.length || 0); }}
    >
      <span className="sx-upload-icon" aria-hidden="true"><svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M12 16V4m0 0-4 4m4-4 4 4"/><path d="M4 16.5V19a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2.5"/></svg></span>
      <div className="sx-upload-copy"><strong>{busy ? 'Uploading your dataset…' : dragging ? 'Release to upload this dataset' : 'Drop your geospatial file here'}</strong><span>or <u>browse files</u> from your device</span></div>
      <small>KML, GeoJSON, KMZ or zipped Shapefile <span aria-hidden="true">·</span> Max 10 MiB</small>
    </div>
    <input ref={fileInput} className="sx-native-file-input" type="file" accept=".kml,.geojson,.kmz,.zip" tabIndex={-1} disabled={unavailable} onChange={e => { const file = e.currentTarget.files?.[0]; e.currentTarget.value = ''; void submitFile(file); }}/>
    {feedback && <p className={`sx-upload-feedback ${feedback.type}`} role={feedback.type === 'error' ? 'alert' : 'status'}>{feedback.message}</p>}
  </div>;
}
function ReadableCrs({ value }) {
  if (typeof value !== 'string' || value.length < 62) return value;
  const title = value.includes('+proj=aeqd') ? 'Local azimuthal-equidistant projection' : 'Detailed coordinate reference system';
  return <details className="sx-crs-details"><summary>{title} <span>View full definition</span></summary><code>{value}</code></details>;
}
function DetailRows({ rows }) { return <dl className="sx-evidence">{rows.map(([label,value],index)=><div key={`${label}-${index}`}><dt>{label}</dt><dd>{/CRS|projection/i.test(label) ? <ReadableCrs value={value}/> : value}</dd></div>)}</dl>; }
function GeometryTag({ value }) {
  const type = String(value ?? 'Unknown');
  const polygon = /polygon/i.test(type);
  const line = /line/i.test(type);
  const category = polygon ? 'polygon' : line ? 'line' : 'point';
  return <span className={`sx-geometry-tag ${category}`}>
    <svg className="sx-geometry-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {polygon ? <><path d="M7 4 18 6l3 10-10 5-8-7z"/><circle cx="7" cy="4" r="1.2"/><circle cx="18" cy="6" r="1.2"/><circle cx="11" cy="21" r="1.2"/></>
        : line ? <><path d="m3 17 6-10 6 8 6-10"/><circle cx="3" cy="17" r="1.6"/><circle cx="9" cy="7" r="1.6"/><circle cx="15" cy="15" r="1.6"/><circle cx="21" cy="5" r="1.6"/></>
        : <><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1" fill="currentColor"/><path d="M12 2v4m0 12v4M2 12h4m12 0h4"/></>}
    </svg>
    <span>{type}</span>
  </span>;
}
function StatusTag({ value }) {
  const status = String(value ?? 'Unknown');
  return <span className={`sx-status-tag ${status === 'FAILED' ? 'failed' : status === 'MEASURED' ? 'measured' : 'neutral'}`}><span className="sx-status-dot" aria-hidden="true"/>{status.replaceAll('_',' ').toLowerCase()}</span>;
}
function CondensedCrs({ value }) {
  const crs = String(value ?? '—');
  if (crs.length < 34) return <span className="sx-short-crs">{crs}</span>;
  return <span className="sx-short-crs" title={crs}>Local metric CRS <span aria-hidden="true">ⓘ</span></span>;
}
function safeQualityCrsNote(info, rows) {
  const source = info?.crs || 'Not provided';
  const projections = [...new Set((rows || []).filter(row => row.status === 'MEASURED' && row.measurement_crs).map(row => row.measurement_crs))];
  if (!projections.length) return `Source CRS: ${source} · No successful projected measurements`;
  if (projections.length > 1) return `Source CRS: ${source} · ${projections.length} local metric projections; inspect each feature for exact CRS`;
  if (projections[0].length > 42) return `Source CRS: ${source} · Local metric projection; exact CRS available in selected feature details`;
  return qualityCrsNote(info, rows);
}

function EvidenceDetails({ item }) {
  if (!item) return <div className="sx-empty-details">Select a survey feature to inspect its area, length, CRS and validation result.</div>;
  const detail=qualityDetail(item);
  return <div className="sx-structured-evidence"><DetailRows rows={detail.summary}/>{detail.evidence.length>0&&<details className="sx-record-provenance"><summary>More calculation evidence ({detail.evidence.length})</summary><DetailRows rows={detail.evidence}/></details>}</div>;
}

function Table({ columns, rows, selected, onChoose }) {
  const interactive = typeof onChoose === 'function';
  const featureTable = interactive;
  const display = (cell, index) => {
    if (!featureTable) return cell;
    const quality = columns.includes('Status');
    if (index === (quality ? 1 : 2)) return <GeometryTag value={cell}/>;
    if (quality && index === 2) return <StatusTag value={cell}/>;
    if (quality && index === 4) return <CondensedCrs value={cell}/>;
    if (index === 3) return <span className="sx-measurement-cell">{cell}</span>;
    return cell;
  };
  return <div className={`sx-table-scroll${featureTable ? ' sx-feature-table-scroll' : ''}`} tabIndex={0} aria-label={featureTable ? 'Feature records, page scrolls normally' : 'Scrollable analysis table'}>
    <table className={`sx-table${featureTable ? ' sx-feature-table' : ''}`}><thead><tr>{featureTable && <th scope="col" className="sx-row-number-head">#</th>}{columns.map(c=><th key={c} scope="col">{c}</th>)}{interactive&&<th scope="col">Inspect</th>}</tr></thead><tbody>
      {rows.length ? rows.map((row,idx)=><tr key={row.key} className={`${interactive ? 'sx-clickable-row' : ''} ${selected === row.key ? 'sx-selected' : ''}`} aria-selected={interactive ? selected === row.key : undefined} tabIndex={interactive?0:undefined} onClick={interactive?()=>onChoose(row.key):undefined} onKeyDown={interactive?e=>{if(e.target===e.currentTarget&&(e.key==='Enter'||e.key===' ')){e.preventDefault();onChoose(row.key);}}:undefined}>{featureTable&&<td className="sx-row-number"><span>{String(idx + 1).padStart(2, '0')}</span></td>}{row.cells.map((cell,i)=><td key={i}>{display(cell,i)}</td>)}{interactive&&<td><button type="button" className={`sx-row-open${selected===row.key?' is-viewing':''}`} aria-pressed={selected===row.key} aria-label={`Inspect ${row.cells[1]||row.cells[0]}`} onClick={e=>{e.stopPropagation();onChoose(row.key);}}>{selected===row.key?'Viewing details':'View details →'}</button></td>}</tr>) : <tr><td colSpan={columns.length+(interactive ? 1 : 0)+(featureTable?1:0)}>No records in this result.</td></tr>}
    </tbody></table>
  </div>;
}
function FeatureRecordDetails({ feature }) {
  if(!feature) return <div className="sx-record-empty"><strong>No feature selected</strong><p>Choose <b>View details</b> beside any result to inspect the verified measurements and source fields.</p></div>;
  const detail=sourceDetail(feature);const props=feature.properties||{};
  const category=NAMES[feature._category]||'Survey feature';
  const measurement=sourceMeasurement(feature);
  return <>
    <div className="sx-record-title"><span className="sx-record-kicker">FEATURE DETAILS</span><h4>{category}</h4><p>{props.name||props.survey_id||props.route_feature_id||feature.id||'Survey result'}</p></div>
    {measurement!=='—'&&<div className="sx-feature-primary"><span>Verified measurement</span><strong>{measurement}</strong></div>}
    <DetailRows rows={detail.summary}/>
    {detail.evidence.length>0&&<details className="sx-record-provenance"><summary>Calculation evidence ({detail.evidence.length})</summary><DetailRows rows={detail.evidence}/></details>}
    {detail.attributes.length>0&&<details className="sx-record-provenance"><summary>Original attributes ({detail.attributes.length})</summary><DetailRows rows={detail.attributes}/></details>}
  </>;
}

function RecordReview({mode,rows,features,qualityRows,selected,onChoose,animationKey=0}) {
  const feature=features.find(f=>f._key===selected);
  const measure=qualityRows.find(f=>`survey-${f.index}`===selected);
  const inspectorRef=useRef(null);
  // Selecting another row must reveal the START of the record, not the last scroll position.
  // This also works when an earlier feature had a long evidence section expanded.
  useEffect(()=>{if(selected&&inspectorRef.current) inspectorRef.current.scrollTop=0;},[selected,animationKey]);
  return <div className="sx-record-review">
    <Table columns={mode==='quality'?['Feature ID','Geometry','Status','Measurement','CRS']:['Layer','Record','Geometry','Measurement']} rows={rows} selected={selected} onChoose={onChoose}/>
    <aside ref={inspectorRef} tabIndex={-1} key={`${selected||'not-selected'}-${animationKey}`} className={`sx-record-inspector${selected?' sx-inspector-selected':''}`} aria-label="Selected feature record and calculations" aria-live="polite">
      {selected?<>
        <span className="sx-inspector-updated">Record opened · details updated</span>
        {mode==='quality'?<><div className="sx-record-title"><span className="sx-record-kicker">SURVEY RECORD DETAILS</span><h4>{measure?.id||'Feature details'}</h4><p>Measurements, coordinate system and validation findings</p></div><EvidenceDetails item={measure}/></>:<FeatureRecordDetails feature={feature}/>}
      </>:<div className="sx-record-empty"><span className="sx-record-kicker">FEATURE INSPECTOR</span><h4>Select a result to inspect</h4><p>Click a shape on the map or choose a row in the table. The selected record appears here with its measurements and evidence.</p></div>}
    </aside>
  </div>;
}

export default function SpatialIntelligence({ mode='quality' }) {
  const setting = CONFIG[mode]||CONFIG.quality;
  const [files,setFiles]=useState(recentFiles); const [roles,setRoles]=useState({});
  const [meta,setMeta]=useState({}); const [result,setResult]=useState(null);const [failure,setFailure]=useState('');
  const [working,setWorking]=useState(false);const [uploading,setUploading]=useState(false);
  const activeUploads=useRef(0);
  const [demoRun,setDemoRun]=useState(false);const [verification,setVerification]=useState(null);const [selected,setSelected]=useState(null);
  const [sourceFeatures,setSourceFeatures]=useState([]);
  const [resetVersion,setResetVersion]=useState(0);
  const recordsRef=useRef(null);
  const [selectionVersion,setSelectionVersion]=useState(0);
  const chooseFeature=(key,fromMap=false)=>{
    setSelected(key);
    // Increment even on re-select so the inspector returns to its heading every time.
    setSelectionVersion(current=>current+1);
    if (!key) return;
    requestAnimationFrame(()=>{
      const section=recordsRef.current;
      const inspector=section?.querySelector('.sx-record-inspector');
      if (!section||!inspector) return;
      inspector.scrollTop=0;
      const bounds=inspector.getBoundingClientRect();
      const visible=bounds.top>=100 && bounds.top<window.innerHeight-160;
      // Map/quality finding clicks bring the results into view. Table clicks only
      // move the page when the record panel is hidden; otherwise preserve the row.
      if (fromMap||!visible) {
        const reduce=window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
        section.scrollIntoView({behavior:reduce?'auto':'smooth',block:'start'});
      }
      inspector.focus({preventScroll:true});
    });
  };
  const jumpToRecords=()=>{
    const reduce=window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    const inspector=recordsRef.current?.querySelector('.sx-record-inspector');
    if(inspector) inspector.scrollTop=0;
    recordsRef.current?.scrollIntoView({behavior:reduce?'auto':'smooth',block:'start'});
  };
  const roleTypes={survey:mode==='quality'?'any':'polygon',reference:'polygon',baseline:'polygon',current:'polygon',route:'line',zone:'polygon'};
  useEffect(()=>{let alive=true;Promise.allSettled(files.slice(0,12).filter(f=>!meta[f.id]).map(async f=>{const d=await api(`/api/files/${f.id}/measurements/`);return [f.id,[...new Set((d.measurements||[]).filter(x=>x.status==='MEASURED').map(x=>/Polygon/.test(x.geometry_type)?'polygon':/LineString/.test(x.geometry_type)?'line':null).filter(Boolean))]];})).then(all=>{if(!alive)return;const addition=Object.fromEntries(all.filter(x=>x.status==='fulfilled').map(x=>x.value));if(Object.keys(addition).length)setMeta(p=>({...p,...addition}));});return()=>{alive=false;};},[files,meta]);
  const available=useMemo(()=>files.map(f=>({...f,kinds:meta[f.id]})).sort((a,b)=>a.filename.localeCompare(b.filename)),[files,meta]);
  const onChoose=(role,id)=>{setRoles(p=>({...p,[role]:id}));setResult(null);setSourceFeatures([]);setSelected(null);setDemoRun(false);setVerification(null);setFailure('');};
  const resetWorkspace=()=>{
    if(working || uploading) return;
    setRoles({});
    setResult(null);
    setSourceFeatures([]);
    setFailure('');
    setSelected(null);
    setDemoRun(false);
    setVerification(null);
    setResetVersion(version=>version+1);
  };
  async function upload(role,file) {
    activeUploads.current+=1;
    setUploading(true);
    try {
      const record=await uploadDataset(file);
      setFiles(remember(record));
      onChoose(role,record.id);
    } catch(e) {
      setFailure(e.message);
      throw e;
    } finally {
      activeUploads.current-=1;
      setUploading(activeUploads.current>0);
    }
  }
  async function execute(selectedRoles,currentMode) {
    if(currentMode==='quality'){
      if(!idValid(selectedRoles.survey))throw new Error('Select a survey dataset or run the supplied QA example.');
      const id=selectedRoles.survey;
      const [info,quality,summary,measurements,geojson]=await Promise.all([
        api(`/api/files/${id}/`),api(`/api/files/${id}/quality/`),api(`/api/files/${id}/summary/`),api(`/api/files/${id}/measurements/`),api(`/api/files/${id}/geojson/`)]);
      return {info,quality,summary,measurements,geojson};
    }
    const inputs = currentMode==='compare'?['baseline','current']:currentMode==='topology'?['survey']:['route','zone'];
    if(inputs.some(r=>!idValid(selectedRoles[r])))throw new Error('Select all required datasets; each input must have the appropriate geometry type.');
    const request=currentMode==='compare'?{baseline_file_id:selectedRoles.baseline,current_file_id:selectedRoles.current}
      :currentMode==='topology'?{file_id:selectedRoles.survey,reference_file_id:selectedRoles.reference||null}
      :{route_file_id:selectedRoles.route,zone_file_id:selectedRoles.zone};
    const path=currentMode==='compare'?'compare':currentMode==='topology'?'topology':'route-zones';
    const analysis=await api(`/api/analysis/${path}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});
    const cats=currentMode==='compare'?[['baseline','baseline_outline'],['current','current_outline']]:currentMode==='topology'?[['survey','source_parcel'],...(selectedRoles.reference?[['reference','reference_outline']]:[])]:[['route','source_route'],['zone','source_zone']];
    const all=await Promise.all(cats.map(async ([r,category])=>{const d=await api(`/api/files/${selectedRoles[r]}/geojson/`);return mapLayer(d,category,r); }));
    return {...analysis,_sourceFeatures:all.flat()};
  }
  const run=async ()=>{setWorking(true);setDemoRun(false);setResult(null);setVerification(null);setFailure('');setSelected(null);try{const data=await execute(roles,mode);setResult(data);setSourceFeatures(mode==='quality'?mapLayer(data.geojson,null,'survey').map(f=>({...f,_key:`survey-${data.measurements.measurements.find(x=>String(x.id)===String(f.id))?.index ?? 0}`,_category:/Polygon/.test(f.geometry.type)?'survey_polygon':/LineString/.test(f.geometry.type)?'survey_line':'survey_point'})):data._sourceFeatures);}catch(e){setFailure(e.message);}finally{setWorking(false);}};
  const runDemo=async()=>{setWorking(true);setDemoRun(true);setResult(null);setVerification(null);setFailure('');setSelected(null);try{
    const newRoles={...roles};for(const item of DEMOS[mode].files){const response=await fetch(`/samples/${item.name}`);if(!response.ok)throw new Error(`Missing public sample: ${item.name} (HTTP ${response.status}). Rebuild Docker with included assets.`);const data=new File([await response.blob()],item.name,{type:'application/geo+json'});const record=await uploadDataset(data);newRoles[item.role]=record.id;setFiles(remember(record));}
    if(mode==='topology')newRoles.reference='';setRoles(newRoles);
    const data=await execute(newRoles,mode);setResult(data);setVerification(verifyDemo(mode,data));setSourceFeatures(mode==='quality'?mapLayer(data.geojson,null,'survey').map(f=>({...f,_key:`survey-${data.measurements.measurements.find(x=>String(x.id)===String(f.id))?.index ?? 0}`,_category:/Polygon/.test(f.geometry.type)?'survey_polygon':/LineString/.test(f.geometry.type)?'survey_line':'survey_point'})):data._sourceFeatures);
  }catch(e){setFailure(e.message);}finally{setWorking(false);}};
  const analysisFeatures=useMemo(()=>result&&mode!=='quality'?[...(sourceFeatures||[]),...analysisLayer(result,mode)]:sourceFeatures,[result,sourceFeatures,mode]);
  const qualityRows=result?.measurements?.measurements||[];
  const allFeatures=mode==='quality'?analysisFeatures:analysisFeatures;
  const mapTitle=mode==='quality'?'Survey geometry — all valid features':mode==='compare'?'Added, removed and unchanged survey footprints':mode==='topology'?'Parcel overlaps and boundary coverage':'Routes, zone boundaries and crossing segments';
  const mapRows=allFeatures.map(f=>({key:f._key,cells:[NAMES[f._category]||'Geometry',f.properties?.name||f.properties?.Name||f.properties?.route_feature_id||f.properties?.category||f.id||'—',f.geometry?.type||'—',sourceMeasurement(f)]}));
  return <div className="sx-app"><GeoNav withBrand/><main className="sx-main">
    <div className="sx-heading"><div><div className="sx-kicker">GEOINSIGHT / {setting.eyebrow}</div><h1>{setting.heading}</h1><p>{setting.subtitle}</p></div><div className="sx-summary-badge"><span>MODULE {setting.number}</span><strong>API-powered geospatial analysis</strong><small>2D vector geometry · projected metrics</small></div></div>
    <section className="sx-workflow"><div className="sx-section-top"><div><span className="sx-step">01 — SELECT DATA</span><h2>Choose your input datasets</h2><p>Upload your own KML, zipped Shapefile, GeoJSON or KMZ. Each input is filtered by the geometry required for this analysis. For a quick demonstration, use Try verified sample.</p></div><button className="sx-demo-btn" type="button" disabled={working||uploading} onClick={()=>void runDemo()}>{working?'Running and verifying…':'▶ Try verified sample'}</button></div>
      <div className={`sx-roles${setting.roles.length === 1 ? ' sx-roles-single' : ''}`}>{setting.roles.map(([role,label])=><RolePicker key={`${role}-${resetVersion}`} label={label} role={role} selected={roles[role]} onSelect={onChoose} files={available} allowed={roleTypes[role]} disabled={working||uploading} onUpload={upload}/>)}</div>
      <div className="sx-buttons"><div className="sx-button-group"><button type="button" className="sx-primary" disabled={working||uploading||!setting.roles.filter(([r])=>r!=='reference').every(([r])=>idValid(roles[r]))} onClick={()=>void run()}>{working?'Analyzing…':'Analyze selected data →'}</button><button type="button" className="sx-reset-btn" disabled={working||uploading} onClick={resetWorkspace} aria-label="Reset this analysis workspace and clear all selected datasets">↺ Reset workspace</button></div><span>Projected metric calculations · Source CRS retained · No AI-generated numbers</span></div>
      {failure&&<div className="sx-error" role="alert"><strong>Could not complete analysis</strong><p>{failure}</p></div>}
    </section>
    {demoRun&&<Verification verification={verification}/>}
    <section className="sx-results"><div className="sx-section-top"><div><span className="sx-step">02 — VERIFIED OUTPUT</span><h2>Analysis results</h2><p>{result?'All results below are returned by the actual FastAPI service.':'Choose your inputs and run an analysis. The known demo will show the expected and actual measurements side by side.'}</p></div>{result&&<div className="sx-downloads"><button type="button" onClick={()=>saveJson(`geoinsight-${mode}-result.json`,result)}>Download report JSON</button>{mode==='quality'?<><a href={`/api/files/${roles.survey}/export/?format=csv`}>Download CSV</a><a href={`/api/files/${roles.survey}/export/?format=geojson`}>Download GeoJSON</a></>:<button type="button" onClick={()=>saveJson(`geoinsight-${mode}.geojson`,mode==='compare'?result.change_geojson:mode==='topology'?result.geojson:result.intersection_geojson)}>Download map GeoJSON</button>}</div>}</div>
      {!result?<div className="sx-placeholder"><div className="sx-placeholder-icon">◇</div><strong>Waiting for a real geospatial analysis</strong><p>Upload your own compatible data, or choose Try verified sample to process known survey files and compare live API measurements with independently defined expected results.</p></div>:<>
        {mode==='quality'&&<><div className="sx-metrics sx-metrics-quality"><Metric label="Total features" value={result.quality.summary.total_features}/><Metric label="Measured" value={result.quality.summary.measured}/><Metric label="Not applicable" value={result.quality.summary.not_applicable}/><Metric label="Failed" value={result.quality.summary.failed}/><Metric label="Area total" value={area(result.summary.totals.area_m2)}/><Metric label="Line total" value={metres(result.summary.totals.length_m)}/></div><div className="sx-quality-bar"><strong>{result.quality.issues.length?`${result.quality.issues.length} issue(s) to review`:'No reported geometry issues'}</strong><span>{result.info.filename} · {result.info.crs||'CRS unavailable'} · {result.info.status}</span></div></>}
        {mode==='compare'&&<div className="sx-metrics sx-metrics-compare"><Metric label="Baseline" value={area(result.metrics.baseline_area_m2)}/><Metric label="Current" value={area(result.metrics.current_area_m2)}/><Metric label="Added area" value={area(result.metrics.added_area_m2)}/><Metric label="Removed area" value={area(result.metrics.removed_area_m2)}/><Metric label="Unchanged overlap" value={area(result.metrics.overlap_area_m2)}/><Metric label="Net change" value={area(result.metrics.net_change_m2)}/><Metric label="Intersection / union" value={pct(result.metrics.intersection_over_union_pct)}/></div>}
        {mode==='topology'&&<div className="sx-metrics sx-metrics-topology"><Metric label="Overlapping pairs" value={result.overlap_pair_count}/><Metric label="Reference gaps evaluated" value={result.gaps_evaluated?'Yes':'No'}/><Metric label="Uncovered site area" value={result.boundary_comparison?area(result.boundary_comparison.uncovered_area_m2):'Not evaluated'}/><Metric label="Outside site boundary" value={result.boundary_comparison?area(result.boundary_comparison.outside_reference_area_m2):'Not evaluated'}/></div>}
        {mode==='routes'&&<div className="sx-metrics sx-metrics-routes"><Metric label="Routes" value={result.summary.route_count}/><Metric label="Zones" value={result.summary.zone_count}/><Metric label="Crossing routes" value={result.summary.routes_crossing_zones}/><Metric label="Total length inside zones" value={metres(result.summary.total_length_inside_any_zone_m)}/><Metric label="Total length outside zones" value={metres(result.routes.reduce((s,r)=>s+r.outside_all_zones_m,0))}/></div>}
        {result.partial&&<p className="sx-caution"><strong>Partial result:</strong> Invalid or unmeasured input features were excluded. Review input quality before relying on the area totals.</p>}
        <div className="sx-two-column"><div><SurveyMap key={mode} features={allFeatures} title={mapTitle} mode={mode} datasetKey={JSON.stringify(roles)} selected={selected} onSelect={key=>chooseFeature(key,true)}/></div><div className="sx-side-panel"><div className="sx-panel-heading"><h3>{mode==='quality'?'Quality findings & review': 'Map layers & selection'}</h3><span>{mode==='quality'?`${result.quality.summary.issue_count} findings`:`${allFeatures.length} mapped features`}</span></div>
          {mode==='quality'?<><p className="sx-findings-intro">{result.quality.issues.length ? `${result.quality.issues.length} feature advisories. Review any warning before using the measurements for engineering decisions.` : 'All features passed the reported quality checks.'}</p><div className="sx-issues" role="region" aria-label="Quality findings; scroll this panel to review warnings" tabIndex={result.quality.issues.length > 3 ? 0 : undefined}>{result.quality.issues.length?result.quality.issues.map((issue,i)=><button key={`${issue.code}-${i}`} type="button" onClick={()=>{chooseFeature(`survey-${issue.feature_index}`,true);}} className={`sx-issue ${String(issue.severity).toLowerCase()==='warning'?'is-warning':'is-error'} ${selected===`survey-${issue.feature_index}`?'active':''}`} aria-pressed={selected===`survey-${issue.feature_index}`}><span className="sx-issue-meta"><b>{issue.severity}</b><span>Feature {issue.feature_id}</span></span><strong>{issue.code.replaceAll('_',' ')}</strong><small>{issue.message}</small></button>):<p className="sx-green-note">No quality issues reported.</p>}</div><div className="sx-divider"/><p className="sx-side-tip">Select a finding to highlight its feature. Full measurements and evidence appear <strong>beside its row below</strong>.</p></>:<><p className="sx-side-tip">{mode==='compare'?'Blue fill marks unchanged overlap; green marks added area and red marks removed area. Dashed blue and teal lines distinguish the two original survey outlines.':mode==='topology'?'Slate dashes show survey parcels, violet dashes show the optional reference boundary, orange fill shows parcel overlap, red fill shows uncovered site and violet fill shows outside area.':'Navy is the full route, a dashed amber line marks restricted-zone boundaries, and green marks the route segment within a zone.'}</p>{selected?<div className="sx-map-selection-note"><span>Viewing map feature</span><strong>{NAMES[allFeatures.find(f=>f._key===selected)?._category]||'Survey geometry'}</strong><small>Detailed attributes are shown beside the highlighted row in the feature table below.</small></div>:<p className="sx-map-selection-note">Select any result to highlight it. A detailed inspector sits next to the feature table below.</p>}</>}
          {selected&&<button type="button" className="sx-jump-records" onClick={jumpToRecords}>View selected feature beside its table row ↓</button>}
        </div></div>
        {mode==='quality'?<section ref={recordsRef} className="sx-dataset-table"><div className="sx-panel-heading"><h3>All survey features</h3><span>{qualityRows.length} source records</span></div><RecordReview mode={mode} rows={qualityRows.map(f=>({key:`survey-${f.index}`,cells:[f.id,f.geometry_type,f.status,f.measurement?`${num(f.measurement.value)} ${f.measurement.unit==='m2'?'m²':f.measurement.unit}`:'—',f.measurement_crs||'—']}))} selected={selected} onChoose={key=>chooseFeature(key)} qualityRows={qualityRows} features={allFeatures} animationKey={selectionVersion}/></section>:<section ref={recordsRef} className="sx-dataset-table"><div className="sx-panel-heading"><h3>All mapped features</h3><span>{mapRows.length} layers / shapes</span></div><RecordReview mode={mode} rows={mapRows} selected={selected} onChoose={key=>chooseFeature(key)} qualityRows={qualityRows} features={allFeatures} animationKey={selectionVersion}/>{mode==='topology'&&<><h3>Overlapping parcel pairs</h3><Table columns={['Parcel A','Parcel B','Overlap area']} rows={result.overlap_issues.map((x,i)=>({key:`pair-${i}`,cells:[x.feature_a,x.feature_b,area(x.overlap_area_m2)]}))}/></>}{mode==='routes'&&<><h3>Route length breakdown</h3><Table columns={['Route','Total length','Inside zones','Outside zones']} rows={result.routes.map((r,i)=>({key:`route-${i}`,cells:[r.route_feature_id,metres(r.length_m),metres(r.inside_any_zone_m),metres(r.outside_all_zones_m)]}))}/></>}</section>}
        <aside className="sx-analysis-guidance" aria-label="Measurement interpretation and limits"><div className="sx-guidance-icon" aria-hidden="true">ⓘ</div><div className="sx-guidance-body"><strong>Measurement method & important limitations</strong><p><b>Method:</b> {(result.method||'projected planar geometry').replaceAll('_',' ')}. <b>{mode==='quality'?safeQualityCrsNote(result.info,qualityRows):`Calculation CRS: ${result.measurement_crs||'See each feature'}`}</b>.</p><p>Area and length are calculated from 2D vector geometries using projected coordinates; these are not 3D terrain measurements. For very large or polar datasets, evaluate projection distortion before engineering use.</p>{result.warnings?.length>0&&<details className="sx-guidance-warnings"><summary>{result.warnings.length} additional technical advisory{result.warnings.length===1?'':' notes'} — show details</summary><ul>{result.warnings.map((w,i)=><li key={i}>{w}</li>)}</ul></details>}</div></aside>
      </>}
    </section>
    <footer className="sx-footer">GeoInsight · FastAPI + Shapely + PROJ <span>Independent fixture verification · Evidence-linked geospatial reporting</span></footer>
  </main></div>;
}
