import { useEffect, useRef, useState } from 'react';
import { evidenceSummary, reportFilename, retrieveVerificationReport } from './surveyEvidence.mjs';
import './SurveyEvidencePassport.css';

export default function SurveyEvidencePassport({ dataset }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [downloaded, setDownloaded] = useState(false);
  const requestRef = useRef(null);
  const summary = evidenceSummary(dataset);

  useEffect(() => () => requestRef.current?.abort(), []);
  if (!summary) return null;

  const download = async () => {
    if (loading) return;
    const controller = new AbortController();
    requestRef.current = controller;
    setLoading(true);
    setError('');
    setDownloaded(false);
    try {
      const text = await retrieveVerificationReport(dataset.metadata, { signal: controller.signal });
      if (controller.signal.aborted) return;
      const blob = new Blob([text], { type: 'application/json;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      try {
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = reportFilename(dataset.metadata.id);
        document.body.appendChild(anchor);
        try { anchor.click(); }
        finally { anchor.remove(); }
        setDownloaded(true);
      } finally {
        // Allow the browser a turn to begin consuming the object URL.
        window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      }
    } catch (exception) {
      if (!controller.signal.aborted) setError(exception?.message || 'Could not download verification report.');
    } finally {
      if (requestRef.current === controller) { setLoading(false); requestRef.current = null; }
    }
  };

  return (
    <section className="gi-passport" aria-label="Survey evidence passport">
      <div className="gi-passport-top">
        <div>
          <div className="gi-passport-eyebrow">SURVEY EVIDENCE PASSPORT / PERSISTED DATA</div>
          <h3>Measurement evidence, ready to audit</h3>
          <p>Trace processing quality, coordinate systems and the original upload fingerprint. The downloadable JSON retains feature-level methods, warnings and accuracy limitations.</p>
        </div>
        <div className="gi-passport-downloads">
          <a className="gi-passport-pdf" href={`/api/files/${encodeURIComponent(dataset.metadata.id)}/verification-report.pdf`} download={`geoinsight-survey-${dataset.metadata.id}.pdf`}>
            <span aria-hidden="true">↓</span> Download survey PDF
          </a>
          <button className="gi-passport-download" type="button" disabled={loading} onClick={() => void download()}>
            <span aria-hidden="true">↓</span> {loading ? 'Preparing report…' : 'Download verification JSON'}
          </button>
        </div>
      </div>
      <div className="gi-passport-grid">
        <div><span>Measured features</span><strong>{summary.measured} / {summary.featureCount}</strong><small>{summary.failed} failed · {summary.remaining} other statuses</small></div>
        <div><span>Feature warnings</span><strong>{summary.warnings}</strong><small>Review per-feature evidence</small></div>
        <div><span>Source CRS</span><strong className="gi-passport-crs">{summary.sourceCRS}</strong><small>Supplied coordinate reference</small></div>
        <div><span>Measurement projection</span><strong className="gi-passport-crs">{summary.projectionLabel}</strong><small>2D projected planar measurements</small></div>
      </div>
      <div className="gi-passport-footer">
        <span><b>Input SHA-256:</b> <code title={summary.sha256 || 'Unavailable'}>{summary.sha256 || 'Unavailable'}</code></span>
        <span>Audit summary from stored results; not independent survey certification.</span>
      </div>
      {error && <p className="gi-passport-error" role="alert">{error}</p>}
      {downloaded && <p className="gi-passport-success" role="status">Report prepared for download and matched to this dataset's ID and SHA-256.</p>}
    </section>
  );
}
