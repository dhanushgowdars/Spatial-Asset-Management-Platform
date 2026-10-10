import { Link } from 'react-router-dom';
import './ReviewerWalkthrough.css';

// The expectations below describe independent fixture examples, never arbitrary uploads.
const checks = [
  {
    n: '01', title: 'Required file ingestion',
    task: 'Open Measure. Process a KML and a zipped ESRI Shapefile.',
    proof: 'Confirm the source format, extracted records, per-feature geometry, area or length, and source CRS.',
    route: '/geospatial', cta: 'Test file measurement',
  },
  {
    n: '02', title: 'Known-size measurement',
    task: 'Try the 100 m square sample on the Measure page.',
    proof: 'Expect 10,000 m². Select its feature and inspect source CRS, projected calculation CRS and provenance.',
    route: '/geospatial', cta: 'Inspect measurement',
  },
  {
    n: '03', title: 'Quality & invalid data',
    task: 'Use the verified example on Survey quality.',
    proof: 'Expect 3 features: 1 measured, 1 point not applicable, 1 failed with TRANSFORM_FAILED.',
    route: '/geospatial/quality', cta: 'Review QA evidence',
  },
  {
    n: '04', title: 'Derived spatial operations',
    task: 'Try the known comparison, topology and route–zone fixtures.',
    proof: 'Compare: 5,000 m² added / removed / shared. Topology: 5,000 m² overlap. Route: 140 m total = 40 m inside + 100 m outside.',
    route: '/geospatial/compare', cta: 'Explore survey change',
  },
  {
    n: '05', title: 'Reproducibility & export',
    task: 'Select map layers and corresponding feature rows, then export available results.',
    proof: 'Confirm that metric values, input records, calculation method and coordinate-system evidence agree with the API output.',
    route: '/geospatial/routes', cta: 'Inspect route results',
  },
];

export default function ReviewerWalkthrough() {
  return (
    <section className="gg-section gg-reviewer" id="reviewer" aria-labelledby="gg-reviewer-title">
      <div className="gg-section-title">
        <span>REVIEWER WALKTHROUGH / ACCEPTANCE CHECKS</span>
        <h2 id="gg-reviewer-title">Review the calculations, not just the interface.</h2>
        <p>Five concrete checks connect the original geospatial assignment to its API, the on-map evidence and the optional spatial-intelligence extensions.</p>
      </div>
      <div className="gg-reviewer-intro">
        <div>
          <strong>Start with the assignment requirements.</strong>
          <p>KML and zipped Shapefile ingestion, polygon area, line length and retrievable results are the core deliverables. The other modules demonstrate additional GIS workflows.</p>
        </div>
        <Link to="/geospatial">Open the measurement workspace <span aria-hidden="true">↗</span></Link>
      </div>
      <div className="gg-reviewer-grid">
        {checks.map((item) => (
          <article className="gg-reviewer-card" key={item.n}>
            <div className="gg-reviewer-card-head"><span>{item.n}</span><h3>{item.title}</h3></div>
            <p className="gg-reviewer-task">{item.task}</p>
            <div className="gg-reviewer-proof"><strong>Check the evidence</strong><p>{item.proof}</p></div>
            <Link to={item.route}>{item.cta} <span aria-hidden="true">↗</span></Link>
          </article>
        ))}
      </div>
      <div className="gg-reviewer-boundary" role="note">
        <div className="gg-reviewer-boundary-icon" aria-hidden="true">i</div>
        <div>
          <strong>Scope and accuracy, clearly stated</strong>
          <p>All figures above are expectations for specific test fixtures, not guarantees for uploaded survey data. GeoInsight performs <b>2D vector</b> geospatial operations using projected coordinates; it is not a cadastral certification service, 3D terrain-volume calculator or raw drone-image processing engine. Large geographic extents require projection-distortion review.</p>
        </div>
      </div>
    </section>
  );
}
