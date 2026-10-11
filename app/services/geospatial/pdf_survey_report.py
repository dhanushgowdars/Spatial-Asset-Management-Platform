"""Professional, bounded PDF view of the *existing* persisted GeoInsight JSON report.

No re-measurement, geometry processing, source properties or raw geometry are used.
Use the JSON export as the complete, machine-readable audit record.
"""
from __future__ import annotations

from html import escape
from io import BytesIO
from math import isfinite

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

GREEN = colors.HexColor('#087665')
NAVY = colors.HexColor('#153747')
MUTED = colors.HexColor('#627b86')
FAINT = colors.HexColor('#e4edef')
PALE = colors.HexColor('#f1f9f6')
MARGIN = 18 * mm
MAX_FEATURES_PDF = 2000

TITLE = ParagraphStyle('GI_Title', fontName='Helvetica-Bold', fontSize=23, leading=29, textColor=NAVY, spaceAfter=9)
HEADING = ParagraphStyle('GI_Heading', fontName='Helvetica-Bold', fontSize=12.5, leading=16, textColor=NAVY, spaceBefore=14, spaceAfter=7)
BODY = ParagraphStyle('GI_Body', fontName='Helvetica', fontSize=9, leading=13.5, textColor=NAVY, spaceAfter=6)
SMALL = ParagraphStyle('GI_Small', parent=BODY, fontSize=7.8, leading=10.7, textColor=MUTED, spaceAfter=4)
CELL = ParagraphStyle('GI_Cell', fontName='Helvetica', fontSize=7.4, leading=10.5, textColor=NAVY)
CELL_BOLD = ParagraphStyle('GI_CellBold', parent=CELL, fontName='Helvetica-Bold', textColor=GREEN)


def clean(value, length: int = 180) -> str:
    """Safe paragraph text, bounded to avoid layout abuse by uploaded metadata."""
    normalized = ' '.join(str(value if value is not None else 'Not specified').split())
    if len(normalized) > length:
        normalized = normalized[:length - 3] + '...'
    return escape(normalized, quote=True)


def fmt(value, suffix: str = '') -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        return 'Not available'
    # PDF displays up to three decimals while the JSON retains exact stored values.
    rounded = round(float(value), 3)
    if rounded == 0:
        rounded = 0.0
    return f'{rounded:,.3f}'.rstrip('0').rstrip('.') + suffix


def P(value, style=BODY, length=180):
    return Paragraph(clean(value, length), style)


def _kv(rows, width):
    left = width * .31
    table = Table([[P(label, CELL_BOLD, 90), P(value, CELL, 180)] for label, value in rows], colWidths=[left, width-left], hAlign='LEFT')
    table.setStyle(TableStyle([
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LINEBELOW',(0,0),(-1,-2),.35,FAINT),
        ('BOTTOMPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),8),
        ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
    ]))
    return table


def _page(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setStrokeColor(FAINT)
    canvas.setLineWidth(.6)
    canvas.line(MARGIN, h - 13*mm, w-MARGIN, h-13*mm)
    canvas.setFont('Helvetica-Bold', 8)
    canvas.setFillColor(GREEN)
    canvas.drawString(MARGIN, h - 10.5*mm, 'GEOINSIGHT  /  VERIFIABLE MEASUREMENTS')
    canvas.setStrokeColor(FAINT)
    canvas.line(MARGIN, 15*mm, w-MARGIN, 15*mm)
    canvas.setFillColor(MUTED)
    canvas.setFont('Helvetica', 7.6)
    canvas.drawString(MARGIN, 10.7*mm, 'Generated from persisted results  |  Not a survey-grade certification')
    canvas.drawRightString(w-MARGIN, 10.7*mm, f'Page {doc.page}')
    canvas.restoreState()


def render_pdf_verification_report(report: dict) -> bytes:
    """Render a printable survey summary; preserve the full values in the JSON report.

    Raises ValueError if the report shape exceeds bounded PDF export policy.
    """
    if report.get('report_type') != 'geoinsight_measurement_verification' or report.get('schema_version') != '1.0':
        raise ValueError('Unsupported verification report schema')
    features = report.get('features')
    if not isinstance(features, list) or len(features) > MAX_FEATURES_PDF:
        raise ValueError(f'PDF export supports up to {MAX_FEATURES_PDF} feature records')
    provenance = report['provenance']
    processing = report['processing']
    summary = report['summary']
    if processing['feature_count'] != len(features):
        raise ValueError('Stored report feature count mismatch')
    counts = summary['counts']
    totals = summary['totals']
    pdf = BytesIO()
    doc = SimpleDocTemplate(pdf, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=23*mm,
                            bottomMargin=24*mm, title='GeoInsight Survey Measurement Report',
                            author='GeoInsight', pageCompression=1, invariant=1)
    width = A4[0] - 2 * MARGIN
    story = [Spacer(1,7*mm), Paragraph('Survey measurement report', TITLE),
             P('Export of verified, stored geospatial processing results. All measurements are 2D projected-planar estimates, not independently certified.', BODY, 500),
             HRFlowable(width='100%', thickness=1.2, color=GREEN, spaceAfter=13)]
    cards = [
        ('Extracted', str(processing['feature_count'])),
        ('Measured', str(counts.get('measured', 0))),
        ('Polygon area', fmt(totals.get('area_m2'), ' m²')),
        ('Line length', fmt(totals.get('length_m'), ' m')),
    ]
    cells = [[Paragraph(clean(label,50), SMALL), Paragraph(clean(value,50), HEADING)] for label,value in cards]
    cardtable=Table([cells],colWidths=[width/4]*4, hAlign='LEFT')
    cardtable.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),PALE),('BOX',(0,0),(-1,-1),.5,FAINT),
        ('INNERGRID',(0,0),(-1,-1),.5,FAINT),('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),6),
        ('TOPPADDING',(0,0),(-1,-1),12),('BOTTOMPADDING',(0,0),(-1,-1),6),
    ]))
    story.extend([cardtable, Paragraph('Source and calculation provenance', HEADING)])
    story.append(_kv([
        ('Source filename', provenance.get('filename')),
        ('File record ID', provenance.get('file_id')),
        ('Input SHA-256', provenance.get('input_sha256')),
        ('Source CRS', provenance.get('source_crs')),
        ('Measurement CRS', next(iter({f.get('measurement_crs') for f in features if f.get('measurement_crs')})) if len({f.get('measurement_crs') for f in features if f.get('measurement_crs')}) == 1 else 'Multiple per-feature projections' if any(f.get('measurement_crs') for f in features) else 'Not applicable'),
        ('Measurement method', processing.get('measurement_basis')),
        ('Saved at', provenance.get('uploaded_at')),
    ], width))
    story.append(Paragraph('Processing breakdown', HEADING))
    story.append(_kv([
        ('Processing status', processing.get('status')),
        ('Polygon / line records', f"{counts.get('polygons_measured',0)} / {counts.get('lines_measured',0)}"),
        ('Failed / Not applicable', f"{counts.get('failed',0)} / {counts.get('not_applicable',0)}"),
        ('Feature warnings', str(summary.get('warning_features',0))),
        ('Total interpretation', summary.get('total_note')),
    ], width))
    story.append(Paragraph('Interpretation and limitations', HEADING))
    for note in report.get('limitations', [])[:12]:
        story.append(Paragraph('&#8226; ' + clean(note,450), SMALL))
    advisories = []
    for feature in features:
        if feature.get('warnings') or feature.get('error'):
            advisories.append((feature.get('id'), list(feature.get('warnings') or []) + ([feature['error']] if feature.get('error') else [])))
    if advisories:
        story.append(Paragraph('Feature warnings and errors (first 8 records)', HEADING))
        for feature_id, notes in advisories[:8]:
            story.append(P(str(feature_id) + ': ' + ' | '.join(str(x) for x in notes), SMALL, 350))
        if len(advisories) > 8:
            story.append(P(f'{len(advisories)-8} additional affected records are detailed in the JSON report.', SMALL))
    story.extend([Spacer(1,6*mm), Paragraph('Feature measurement appendix', HEADING),
                  P('Complete feature list from the persisted report. Per-feature warnings and exact numeric precision remain available in the JSON download.', SMALL, 350)])
    head = [P('Record',CELL_BOLD),P('Geometry',CELL_BOLD),P('Status',CELL_BOLD),P('Measurement',CELL_BOLD),P('Metric CRS',CELL_BOLD)]
    rows = [head]
    for feature in features:
        measurement = feature.get('measurement')
        measure_text = ('Not measured' if not isinstance(measurement,dict) else
                        fmt(measurement.get('value'), ' m²' if measurement.get('unit') == 'm2' else ' m' if measurement.get('unit')=='m' else ' '+str(measurement.get('unit') or '')))
        # Area measurements may carry a persisted polygon perimeter. Display it
        # as supplementary evidence; never derive or fabricate it in the PDF.
        measurement_cell = [P(measure_text, CELL, 38)]
        perimeter = feature.get('perimeter_m')
        if (isinstance(measurement, dict) and measurement.get('type') == 'area'
                and feature.get('geometry_type') in ('Polygon', 'MultiPolygon')
                and isinstance(perimeter, (int, float)) and not isinstance(perimeter, bool)
                and isfinite(perimeter) and perimeter >= 0):
            measurement_cell.append(P('Perimeter: ' + fmt(perimeter, ' m'), SMALL, 42))
        record = f"{feature.get('index', '?')}: {feature.get('id', '?')}"
        rows.append([
            P(record,CELL,40), P(feature.get('geometry_type'),CELL,32), P(feature.get('status'),CELL,22),
            measurement_cell, P(feature.get('measurement_crs') or '-',CELL,34),
        ])
    # Tables break across pages and repeat headers; bound the number of records.
    table = Table(rows, colWidths=[width*.23,width*.19,width*.17,width*.2,width*.21], repeatRows=1, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),PALE),('LINEBELOW',(0,0),(-1,0),.8,GREEN),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white, colors.HexColor('#f8fbfb')]),
        ('LINEBELOW',(0,1),(-1,-1),.18,FAINT),('VALIGN',(0,0),(-1,-1),'TOP'),
        ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
        ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),5),
    ]))
    story.append(table)
    doc.build(story,onFirstPage=_page,onLaterPages=_page)
    data=pdf.getvalue()
    if not data.startswith(b'%PDF-') or len(data)>8*1024*1024:
        raise ValueError('PDF generation failed or generated file exceeds size limit')
    return data
