import { useState } from 'react';
import { Link } from 'react-router-dom';
import GeoNav from '../GeoNav/GeoNav';
import './GeoGuide.css';
import ReviewerWalkthrough from './ReviewerWalkthrough';

const pages = [
  { n: '01', title: 'Measure survey files', route: '/geospatial', task: 'Import KML, zipped Shapefile, GeoJSON or KMZ. Inspect polygon area, line length, CRS, source attributes and an interactive map.', input: 'KML or zipped Shapefile', result: 'Feature areas in m² and lengths in m; record metadata, map and CSV export.', demo: 'KML mixed geometries or Shapefile 100 m square (10,000 m²).' },
  { n: '02', title: 'Survey quality & evidence', route: '/geospatial/quality', task: 'Inspect measured, non-applicable and failed geometry features. See validation issues and calculation evidence without losing valid results.', input: 'One survey dataset', result: 'Counts, QA findings, evidence, mapped valid geometries and exports.', demo: 'quality_demo.geojson: three features, one measured, one not applicable and one TRANSFORM_FAILED.' },
  { n: '03', title: 'Compare surveys', route: '/geospatial/compare', task: 'Compare baseline and current polygon boundaries in a common projected CRS to identify newly added, removed and overlapping land.', input: 'Two polygon survey datasets', result: 'Added / removed / unchanged area in m², net change, overlap percentage and GeoJSON map layers.', demo: 'c4a_baseline.geojson + c4a_current.geojson: 5,000 m² added, 5,000 m² removed, 5,000 m² overlap.' },
  { n: '04', title: 'Polygon topology', route: '/geospatial/topology', task: 'Find overlapping parcel boundaries and measure shared land. Optionally supply a reference site boundary to evaluate coverage gaps.', input: 'Polygon dataset; optional reference polygon dataset', result: 'Intersecting feature pairs and overlap areas; boundary gap checks only when a reference is given.', demo: 'c4a_topology.geojson: one overlap pair, 5,000 m² intersection.' },
  { n: '05', title: 'Routes & restricted zones', route: '/geospatial/routes', task: 'Analyze road, utility or survey route geometry against site or restricted-zone polygons.', input: 'One line dataset and one polygon zone dataset', result: 'Route length inside and outside zone unions and the clipped crossing geometry.', demo: 'c4a_route.geojson + c4a_zone.geojson: 140 m route, 40 m inside and 100 m outside.' },
];

const steps = [
  { n: '1', title: 'Choose an analysis', detail: 'Start with Measure for the assignment requirements. Use a specialized page for QA, comparisons, topology or route crossings.' },
  { n: '2', title: 'Upload your own data', detail: 'Use Upload on the relevant page. Files are sent to the same-origin FastAPI server; eligible saved files can be selected again.' },
  { n: '3', title: 'Run the calculation', detail: 'Click Analyze selected data. GeoInsight validates inputs and returns calculated values from the backend spatial engine.' },
  { n: '4', title: 'Read the results and inspect geometry', detail: 'The map initially shows all valid geometries. Select a feature in the map or table to highlight it and see details beside the table.' },
  { n: '5', title: 'Export and verify', detail: 'Download CSV, JSON or GeoJSON where available. Compare measurements with the input CRS and any reported quality warnings.' },
];

const tour = [
  { label:'Import & measure', icon:'▱', title:'Turn survey files into reliable measurements', body:'Import KML, GeoJSON, KMZ or zipped Shapefiles. See projected polygon area and line length alongside source coordinates, original attributes and record provenance.', link:'/geospatial', action:'Open measurement workspace' },
  { label:'Quality control', icon:'◎', title:'Catch issues without losing valid records', body:'Inspect measured, not-applicable and failed features. Review coordinate transformation errors and distortion advisories beside their original survey records.', link:'/geospatial/quality', action:'Explore survey quality' },
  { label:'Compare surveys', icon:'◫', title:'See what was added, removed or unchanged', body:'Compare baseline and current polygon extents using geometric overlap and difference. Interpret added, removed and shared areas with a color-coded map.', link:'/geospatial/compare', action:'Explore change detection' },
  { label:'Topology checks', icon:'⬡', title:'Identify overlapping parcels and coverage gaps', body:'Check parcel-pair overlaps and, when you provide a reference boundary, calculate uncovered or out-of-bound site areas.', link:'/geospatial/topology', action:'Explore topology' },
  { label:'Routes & zones', icon:'⌁', title:'Measure route impact through restricted zones', body:'Overlay lines with polygons to distinguish distance inside a zone from distance outside it, without manually tracing crossing segments.', link:'/geospatial/routes', action:'Explore route analysis' },
];


/* GEOINSIGHT_GUIDE_REVIEW_V1 */
const faqEntries = [
  {
    "question": "Why do I see “Not applicable” for a Point?",
    "answer": "Point geometries have a position but no polygon area or line length. This is expected, not a failed measurement.",
    "category": "Quality & scope"
  },
  {
    "question": "Why are there no shapes on the map for an invalid record?",
    "answer": "Unusable coordinates cannot be displayed reliably. The issue and source record remain available in the QA table even when that shape can't be mapped.",
    "category": "Quality & scope"
  },
  {
    "question": "Why am I seeing no overlap or zero added area?",
    "answer": "Identical polygons have zero added/removed area. Different datasets may be disjoint or overlap. Verify that you selected the intended baseline/current files; try the verified example for a known 5,000 m² change.",
    "category": "Measurements & CRS"
  },
  {
    "question": "Why won't an uploaded file appear in a route or polygon selector?",
    "answer": "Selectors use the geometry types present in measured features. A file with only lines cannot serve as a polygon zone, and vice versa.",
    "category": "Files & uploads"
  },
  {
    "question": "What does “Partial result” mean?",
    "answer": "At least one invalid or unmeasurable feature was excluded from the spatial operation. Inspect its QA report before interpreting area and length totals.",
    "category": "Quality & scope"
  },
  {
    "question": "Can I download or revisit an analysis?",
    "answer": "Use the export buttons on the result page. Recently uploaded file references may be available in the same browser; server-side persistence depends on the deployment's configured database.",
    "category": "Files & uploads"
  },
  {
    "question": "Why does a dataset show 100% overlap with zero change?",
    "answer": "The selected baseline and current polygon footprints are spatially identical, so added area and removed area are both zero. If this is unexpected, confirm that you selected two different survey files.",
    "category": "Measurements & CRS"
  },
  {
    "question": "Why does the map show WGS84 even if the measurement uses UTM?",
    "answer": "The map uses longitude and latitude for display (EPSG:4326). Area and line length are calculated in a metric projected CRS. Source CRS and calculation CRS are shown separately so you can verify that degrees were not treated as metres.",
    "category": "Measurements & CRS"
  },
  {
    "question": "What should I do with a projection distortion warning?",
    "answer": "Check the feature extent and its calculation CRS before using the result for engineering decisions. Very large or geographically scattered geometries may need a different measurement strategy. The warning does not mean a feature failed to parse.",
    "category": "Measurements & CRS"
  },
  {
    "question": "Why are features not measured or excluded from an overlay?",
    "answer": "Points do not have measurable polygon area or line length, while invalid coordinates and unusable geometries cannot produce trusted spatial calculations. Inspect the individual QA result and any partial-result advisory.",
    "category": "Quality & scope"
  },
  {
    "question": "Is this a GIS survey certification or a drone image processor?",
    "answer": "No. GeoInsight works with 2D vector geometry. It does not certify legal survey boundaries, process raw imagery or compute 3D terrain volumes. It is intended for transparent file-based measurement and spatial analysis.",
    "category": "Quality & scope"
  },
  {
    "question": "Do I need to use the verified sample to use a page?",
    "answer": "No. Each module accepts compatible uploaded GIS files. The sample option is only a transparent demonstration: example files are uploaded to the real API and measured independently of the displayed expectation.",
    "category": "Files & uploads"
  }
];

function PageCard({ p }) { return <article className="gg-page-card">
  <div className="gg-page-top"><span className="gg-number">{p.n}</span><h3>{p.title}</h3><Link to={p.route}>Open page <span aria-hidden="true">↗</span></Link></div>
  <p>{p.task}</p>
  <dl><div><dt>Input</dt><dd>{p.input}</dd></div><div><dt>Output</dt><dd>{p.result}</dd></div><div><dt>Verified sample</dt><dd>{p.demo}</dd></div></dl>
</article>; }
function Anchor({ to, children }) { return <a href={`#${to}`}>{children}</a>; }
export default function GeoGuide() {
  const [tourIndex, setTourIndex] = useState(0);
  const [faqQuery, setFaqQuery] = useState('');
  const [faqFilter, setFaqFilter] = useState('All questions');
  const visibleFaqs = faqEntries.filter(item => (faqFilter === 'All questions' || item.category === faqFilter) && (item.question + ' ' + item.answer).toLowerCase().includes(faqQuery.trim().toLowerCase()));
  const activeTour=tour[tourIndex];
  return <div className="gg-shell"><GeoNav withBrand/><main className="gg-main">
  <header className="gg-hero"><div className="gg-eyebrow">GEOINSIGHT / DOCUMENTATION</div><h1>About GeoInsight <span>&amp; user guide</span></h1><p>A practical guide to accurate 2D geospatial measurements, quality review and survey analysis—what every page does, how to use it and how to interpret the results.</p>
    <div className="gg-summary"><span><b>5</b> analysis workflows</span><span><b>4</b> supported upload types</span><span><b>API</b>-verified spatial results</span></div>
  </header>
  <section className="gg-tour" aria-label="Interactive tour of GeoInsight modules">
    <div className="gg-tour-head"><span className="gg-tour-eyebrow">INTERACTIVE WORKFLOW TOUR</span><div className="gg-tour-controls"><span className="gg-tour-count">{String(tourIndex + 1).padStart(2,'0')} / {String(tour.length).padStart(2,'0')}</span><button type="button" onClick={()=>setTourIndex(i=>(i-1+tour.length)%tour.length)} aria-label="Previous workflow">←</button><button type="button" onClick={()=>setTourIndex(i=>(i+1)%tour.length)} aria-label="Next workflow">→</button></div></div>
    <div className="gg-tour-content" aria-live="polite"><div className="gg-tour-visual"><span className="gg-tour-visual-icon" aria-hidden="true">{activeTour.icon}</span><span>{activeTour.label}</span></div><div className="gg-tour-description"><span className="gg-tour-step">WORKFLOW {String(tourIndex + 1).padStart(2,'0')}</span><h2>{activeTour.title}</h2><p>{activeTour.body}</p><Link to={activeTour.link}>{activeTour.action} ↗</Link></div></div>
    <div className="gg-tour-dots" role="group" aria-label="Select a workflow">{tour.map((step,i)=><button key={step.label} type="button" className={i===tourIndex?'active':''} onClick={()=>setTourIndex(i)} aria-label={`Show ${step.label}`} aria-pressed={i===tourIndex}><span className="gg-tour-dot"/>{step.label}</button>)}</div>
    <div className="gg-tour-progress" role="progressbar" aria-label="Workflow tour progress" aria-valuemin={1} aria-valuemax={tour.length} aria-valuenow={tourIndex + 1}><span style={{width: `${Math.round((tourIndex + 1) * 100 / tour.length)}%`}} /></div>
  </section>
  <nav className="gg-toc" aria-label="Guide sections"><Anchor to="quick-start">Quick start</Anchor><Anchor to="pages">Feature reference</Anchor><Anchor to="reviewer">Reviewer walkthrough</Anchor><Anchor to="trust">How results work</Anchor><Anchor to="limits">Rules & limitations</Anchor><Anchor to="api">REST APIs</Anchor><Anchor to="troubleshooting">Troubleshooting</Anchor></nav>
  <section className="gg-section" id="quick-start"><div className="gg-section-title"><span>GET STARTED</span><h2>From upload to an evidence-backed result</h2><p>You can use your own datasets, or try a verified example to explore a known result. Examples are optional and are processed through the same APIs as manual uploads.</p></div><div className="gg-steps">{steps.map(s=><article key={s.n}><strong>{s.n}</strong><div><h3>{s.title}</h3><p>{s.detail}</p></div></article>)}</div>
  <div className="gg-choice"><div><b>Working with your own GIS file?</b><p>Use Upload and Analyze. Don't confuse an example's expected value with a guarantee for unrelated data.</p></div><div><b>Just reviewing the project?</b><p>Click Try verified sample on an analysis page. Live API results are checked against defined fixture expectations.</p></div></div></section>
  <section className="gg-section" id="pages"><div className="gg-section-title"><span>FEATURES / PAGES</span><h2>What each GeoInsight page does</h2><p>The original Aereo assignment is first; the other four pages are optional spatial-intelligence extensions.</p></div><div className="gg-pages">{pages.map(p=><PageCard key={p.n} p={p}/>)}</div></section>
  <ReviewerWalkthrough />
  <section className="gg-section" id="trust"><div className="gg-section-title"><span>ENGINEERING APPROACH</span><h2>Why the outputs are verifiable</h2></div><div className="gg-grid"><div><h3>Correct coordinate units</h3><p>Survey coordinates may arrive in geographic or projected reference systems. The engine computes metric area and length in an appropriate projected CRS. The map displays WGS84 for visualization only; longitude/latitude degrees aren't treated as metres.</p></div><div><h3>Geometry-aware processing</h3><p>Polygons and multipolygons yield area; lines and multilines yield length. Points have positions but no area or line length. Polygon holes and multipart geometries are accounted for in the spatial operations.</p></div><div><h3>Quality and provenance</h3><p>Each record includes its geometry status and available source/measurement CRS. Invalid coordinates and unsupported conditions are reported rather than silently treated as valid. File identity and record evidence support traceability.</p></div><div><h3>Independent test fixtures</h3><p>Known-size examples are analyzed through the backend and compared with numerical expectations. These examples illustrate correctness of specific cases; they don't certify arbitrary surveys or cadastral precision.</p></div></div><p className="gg-note"><b>What makes GeoInsight useful:</b> it connects file ingestion, individual measurements, QA explanations, change detection, topology and route impact in one reproducible workflow. It is a focused engineering demonstration, not a replacement for a full drone processing platform.</p></section>
  <section className="gg-section" id="limits"><div className="gg-section-title"><span>BEFORE RELYING ON A RESULT</span><h2>Data requirements, rules & limitations</h2></div>
    <div className="gg-rules"><article><strong>File types and size</strong><p>Use <code>.kml</code>, <code>.kmz</code>, <code>.geojson</code> or a zipped ESRI Shapefile containing required components. The documented upload limit is 10 MiB; oversized or malformed uploads are rejected.</p></article>
    <article><strong>Input geometry roles</strong><p>Comparison needs two polygon datasets. Topology needs polygons and optionally a site boundary. Route–zone analysis requires lines for routes and polygons for zones. Invalid or unmappable features may be excluded; inspect any partial-result warning.</p></article>
    <article><strong>Metric meaning</strong><p>Area summaries add individual feature areas, so overlapping polygons may be double-counted. Compare uses geometric union/intersection/difference. Route lengths inside overlapping zones are unioned to avoid counting the same route section twice.</p></article>
    <article><strong>Accuracy and scope</strong><p>These are <b>2D projected vector</b> measurements. Projection distortion and source data accuracy matter. GeoInsight doesn't process raw drone imagery, point clouds, DEMs, 3D terrain volumes or certified land boundaries.</p></article>
    <article><strong>Security and privacy</strong><p>Only upload data you're authorized to process. Don't include confidential survey data in public demo deployments. The current reviewer-facing upload API does not establish a private workspace or enterprise authentication boundary.</p></article>
    <article><strong>AI and automation</strong><p>Area, length, QA and overlay results are calculated by deterministic geospatial libraries. Verified examples do not use AI-generated numbers. The interface intentionally doesn't claim AI-based imagery interpretation.</p></article></div>
  </section>
  <section className="gg-section" id="api"><div className="gg-section-title"><span>DEVELOPER REFERENCE</span><h2>REST API quick reference</h2><p>All five pages use the FastAPI service. Open the interactive documentation for request parameters and response schemas.</p></div>
    <div className="gg-endpoints"><code>POST /api/files/</code><span>Upload a geospatial file</span><code>GET /api/files/{'{file_id}'}/</code><span>Inspect saved file metadata</span><code>GET /api/files/{'{file_id}'}/measurements/</code><span>Get feature measurements</span><code>GET /api/files/{'{file_id}'}/quality/</code><span>Get issues and statuses</span><code>GET /api/files/{'{file_id}'}/summary/</code><span>Get computed totals</span><code>GET /api/files/{'{file_id}'}/export/</code><span>Export results to supported formats</span><code>POST /api/analysis/compare</code><span>Compare two survey footprints</span><code>POST /api/analysis/topology</code><span>Inspect parcel overlaps and gaps</span><code>POST /api/analysis/route-zones</code><span>Analyze route crossings</span></div><a className="gg-api-link" href="/docs" target="_blank" rel="noreferrer">Open interactive Swagger API docs ↗</a>
  </section>
  <section className="gg-section" id="troubleshooting"><div className="gg-section-title"><span>TROUBLESHOOTING / PRACTICAL ANSWERS</span><h2>Common questions, answered clearly</h2><p>Find guidance on file compatibility, measurements, projected coordinate systems and interpreting quality warnings.</p></div>
    <div className="gg-faq-tools"><label className="gg-faq-search"><span>Search questions</span><input type="search" placeholder="Search uploads, CRS, warnings…" value={faqQuery} onChange={event=>setFaqQuery(event.target.value)} /></label>
      <div className="gg-faq-filters" role="group" aria-label="Filter questions by topic">{['All questions','Files & uploads','Measurements & CRS','Quality & scope'].map(filter=><button key={filter} type="button" aria-pressed={faqFilter===filter} onClick={()=>setFaqFilter(filter)}>{filter}</button>)}</div>
    </div>
    <p className="gg-faq-meta" role="status">Showing {visibleFaqs.length} of {faqEntries.length} answers</p>
    {visibleFaqs.length > 0 ? <div className="gg-faq">{visibleFaqs.map(item=><details key={item.question}><summary>{item.question}</summary><p>{item.answer}</p></details>)}</div> : <p className="gg-faq-empty">No questions match your search. Try a different term or choose All questions.</p>}
  </section>
  <footer className="gg-footer"><span>GeoInsight · Aereo geospatial engineering assignment</span><Link to="/geospatial">Return to measurement workspace ↗</Link></footer>
</main></div>; }
