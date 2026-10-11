import { useMemo, useState } from 'react';
import { briefNumber, buildSurveyChangeBrief, changeBriefDownloadName } from './surveyChangeBrief.mjs';
import './SurveyChangeBrief.css';

function downloadBrief(brief) {
  const file = new Blob([JSON.stringify(brief, null, 2)], { type: 'application/json;charset=utf-8' });
  const objectUrl = URL.createObjectURL(file);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = changeBriefDownloadName(brief);
  document.body.appendChild(link);
  try { link.click(); } finally { link.remove(); setTimeout(() => URL.revokeObjectURL(objectUrl), 1000); }
}

export default function SurveyChangeBrief({ result }) {
  const prepared = useMemo(() => buildSurveyChangeBrief(result), [result]);
  const [error, setError] = useState('');
  if (!prepared.ok) return <section className="scb-unavailable" role="status" aria-label="Survey decision brief unavailable"><strong>Decision brief unavailable</strong><p>{prepared.error} The original API results and map remain available for inspection.</p></section>;
  const { brief } = prepared;
  const { metrics: m, derived_display: pct, interpretation: interpretation } = brief;
  const tone = interpretation.category;
  return <section className="scb-panel" aria-labelledby="scb-heading">
    <div className="scb-header">
      <div className="scb-head-copy">
        <div className="scb-kicker">SURVEY CHANGE DECISION BRIEF / API EVIDENCE</div>
        <h3 id="scb-heading">{interpretation.headline}</h3>
        <p>{interpretation.explanation}</p>
      </div>
      <button className="scb-download" type="button" onClick={() => { setError(''); try { downloadBrief(brief); } catch { setError('Could not download the comparison brief. The source analysis has not changed.'); } }}>↓ Download decision brief JSON</button>
    </div>
    {error && <p className="scb-error" role="alert">{error}</p>}
    <div className="scb-file-pair" aria-label="Compared source datasets"><div><span>BASELINE DATASET</span><strong title={brief.datasets.baseline.filename}>{brief.datasets.baseline.filename}</strong><small>ID {brief.datasets.baseline.id.slice(0,8)}</small></div><span className="scb-connector" aria-hidden="true">→</span><div><span>CURRENT DATASET</span><strong title={brief.datasets.current.filename}>{brief.datasets.current.filename}</strong><small>ID {brief.datasets.current.id.slice(0,8)}</small></div></div>
    <div className="scb-insights" aria-label="Comparison interpretation">
      <div><span>Net area change</span><strong className={`scb-net scb-${tone}`}>{m.net_change_m2 > 0 ? '+' : ''}{briefNumber(m.net_change_m2)} m²</strong><small>{m.net_change_m2 > 0 ? '+' : ''}{briefNumber(pct.net_change_pct_of_baseline)}% vs baseline</small></div>
      <div><span>Added footprint</span><strong>{briefNumber(m.added_area_m2)} m²</strong><small>Current only · green map layer</small></div>
      <div><span>Removed footprint</span><strong>{briefNumber(m.removed_area_m2)} m²</strong><small>Baseline only · red map layer</small></div>
      <div><span>Shared overlap</span><strong>{briefNumber(m.overlap_area_m2)} m²</strong><small>{briefNumber(m.intersection_over_union_pct)}% intersection / union</small></div>
    </div>
    <div className="scb-spatial">
      <div className="scb-spatial-head"><strong>Spatial change composition</strong><span>Shares of combined footprint ({briefNumber(m.union_area_m2)} m²)</span></div>
      <div className="scb-stack" role="img" aria-label={`Union consists of ${briefNumber(pct.removed_pct_of_union)} percent removed, ${briefNumber(pct.overlap_pct_of_union)} percent unchanged overlap, and ${briefNumber(pct.added_pct_of_union)} percent added.`}>
        {m.removed_area_m2 > 0 && <span className="scb-part scb-removed" style={{ flex: m.removed_area_m2 }}/>}
        {m.overlap_area_m2 > 0 && <span className="scb-part scb-overlap" style={{ flex: m.overlap_area_m2 }}/>}
        {m.added_area_m2 > 0 && <span className="scb-part scb-added" style={{ flex: m.added_area_m2 }}/>}
      </div>
      <div className="scb-legend"><span><i className="scb-dot scb-removed"/> Removed {briefNumber(pct.removed_pct_of_union)}%</span><span><i className="scb-dot scb-overlap"/> Unchanged {briefNumber(pct.overlap_pct_of_union)}%</span><span><i className="scb-dot scb-added"/> Added {briefNumber(pct.added_pct_of_union)}%</span></div>
    </div>
    <div className="scb-footer"><p><strong>Evidence:</strong> {brief.calculation.method.replaceAll('_',' ')} · {brief.calculation.measurement_crs} · m². {interpretation.review_note}</p>{brief.quality.partial ? <p className="scb-partial" role="status"><strong>Partial comparison:</strong> {brief.quality.excluded_feature_count} excluded source feature(s); inspect the original API report before decisions.</p> : <p><strong>Coverage:</strong> No excluded source features were reported.</p>}{brief.quality.warnings.length>0&&<details><summary>{brief.quality.warnings.length} technical advisory note(s)</summary><ul>{brief.quality.warnings.map((note,i)=><li key={i}>{note}</li>)}</ul></details>}<small>Derived from stored survey comparison results; not independent GIS verification, engineering approval, or legal boundary certification.</small></div>
  </section>;
}
