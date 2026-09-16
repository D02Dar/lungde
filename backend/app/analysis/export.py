"""Portable review exports: Excel-readable CSV, full JSON and an SVG chart."""
import csv
import io
import json
from html import escape
import math
from zipfile import ZipFile, ZIP_DEFLATED


def _phase(ms, windows):
    return next((key for key, (start, end) in windows.items() if start*1000 <= ms < end*1000), '')


def _safe(value):
    return "'"+value if isinstance(value, str) and value.startswith(('=', '+', '-', '@', '\t', '\r')) else value


def export_files(result):
    windows = result.get('capture_metadata', {}).get('phase_windows', {})
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['kind', 'series', 'time_ms', 'phase', 'name', 'value', 'unit', 'quality_status'])
    series = [('offline_raw', result.get('raw_timestamps_ms', []), result.get('source_waveform', [])),
              ('offline_processed', result.get('timestamps_ms', []), result.get('waveform', []))]
    for name, times, values in series:
        for ms, value in zip(times, values):
            writer.writerow(['trace', name, ms, _safe(_phase(ms, windows)), 'area', value, 'pixel-area proxy', 'diagnostic trace'])
    quality = result.get('quality', {}).get('status', 'legacy_unvalidated')
    for key in ('vc_px', 'vt_px', 'ratio', 'rr_bpm'):
        writer.writerow(['metric', 'offline', '', '', key, result.get(key), 'see JSON', quality])
    for key, value in result.get('diagnostic', {}).items():
        if isinstance(value, (float, int)):
            writer.writerow(['provisional', 'offline', '', '', key, value, 'see JSON', 'not a formal result'])
    for warning in result.get('quality', {}).get('warnings', []):
        writer.writerow(['quality', 'offline', '', '', 'reason', _safe(warning), '', quality])
    points = [(float(t), float(v)) for _, times, values in series for t, v in zip(times, values)]
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="440" viewBox="0 0 1200 440">',
           '<rect width="1200" height="440" fill="white"/><g font-family="Arial" fill="#26333b">',
           '<text x="75" y="28" font-size="18">Offline area: raw (gray), amplitude-preserving processed (green)</text>',
           '<text x="75" y="48" font-size="12">Pixel-area proxy, not liters. No percentile clipping. Quality: '+escape(quality)+'</text>']
    if points:
        low, high = min(v for _, v in points), max(v for _, v in points)
        pad = max(1, (high-low)*.05)
        low, high = low-pad, high+pad
        duration = max(1, max(t for t, _ in points))
        x = lambda ms: 75+ms/duration*1080
        y = lambda value: 360-(value-low)/(high-low)*285
        for i in range(5):
            value = low+(high-low)*i/4
            svg.append(f'<path d="M75 {y(value)}H1155" stroke="#dde3e0"/><text x="70" y="{y(value)+4}" font-size="11" text-anchor="end">{value:.0f}</text>')
        for phase, (start, _) in windows.items():
            svg.append(f'<path d="M{x(start*1000)} 75V360" stroke="#bac7c1" stroke-dasharray="3 4"/><text x="{x(start*1000)+3}" y="380" font-size="10">{escape(phase)}</text>')
        for i, (_, times, values) in enumerate(series):
            coordinates = ' '.join(f'{x(t):.2f},{y(v):.2f}' for t, v in zip(times, values))
            color = '#a7afb4' if i == 0 else '#00866a'
            svg.append(f'<polyline points="{coordinates}" fill="none" stroke="{color}" stroke-width="1.5"/>')
        svg.append(f'<text x="75" y="412">0 s</text><text x="1155" y="412" text-anchor="end">{duration/1000:.2f} s</text>')
    svg.append('</g></svg>')
    return {'analysis.json': json.dumps({'export_version': 'went-review-export-v1', **result}, indent=2, allow_nan=False).encode('utf-8'),
            'analysis.csv': ('\ufeff'+output.getvalue()).encode('utf-8'), 'waveform.svg': ''.join(svg).encode('utf-8'),
            'README.txt': b'CSV opens in Excel. JSON retains calibration, ROI, clocks, provisional metrics and rejection reasons. Null formal metrics are withheld. Quality checks are engineering rules, not calibrated accuracy probabilities. Pixel-area proxies are not lung volumes. Source video and evidence images are not included.\n'}


def export_zip(result):
    output = io.BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for name, contents in export_files(result).items():
            archive.writestr(name, contents)
    return output.getvalue()


def _number(value, digits=2):
    return f'{value:.{digits}f}' if isinstance(value, (int, float)) and math.isfinite(value) else '--'


def _quality_label(value):
    return {
        'checks_passed': 'Checks passed',
        'usable_with_caution': 'Usable with caution',
        'review_required': 'Review required',
        'rejected': 'Rejected',
        'legacy_unvalidated': 'Legacy / unvalidated',
    }.get(value, str(value or 'Unavailable').replace('_', ' ').title())


def _normalized_trace(result):
    times = result.get('timestamps_ms', [])
    values = result.get('waveform', [])
    points = [(float(time), float(value)) for time, value in zip(times, values)
              if isinstance(time, (int, float)) and isinstance(value, (int, float))
              and math.isfinite(time) and math.isfinite(value)]
    if len(points) < 2:
        return []
    low, high = min(value for _, value in points), max(value for _, value in points)
    span = high-low
    if span <= 1e-12:
        return [(time, 0.5) for time, _ in points]
    return [(time, (value-low)/span) for time, value in points]


def comparison_files(results):
    """Build a paper-style multi-run summary without treating proxy units as liters."""
    results = list(results)
    if not results:
        raise ValueError('At least one result is required')
    summary = []
    traces = []
    for index, result in enumerate(results, 1):
        label = str(result.get('analysis_id') or result.get('id') or f'Run {index}')
        quality = result.get('quality', {}).get('status', 'legacy_unvalidated')
        summary.append({'run': index, 'analysis_id': label, 'vc_px': result.get('vc_px'),
                        'vt_px': result.get('vt_px'), 'ratio': result.get('ratio'),
                        'quality_status': quality})
        traces.append({'run': index, 'analysis_id': label,
                       'points': [{'time_ms': time, 'scaled_value': value}
                                  for time, value in _normalized_trace(result)]})

    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['kind', 'run', 'analysis_id', 'vt_px', 'vc_px', 'vc_vt_ratio',
                     'quality_status', 'time_ms', 'scaled_value'])
    for row in summary:
        writer.writerow(['summary', row['run'], _safe(row['analysis_id']), row['vt_px'],
                         row['vc_px'], row['ratio'], row['quality_status'], '', ''])
    for trace in traces:
        for point in trace['points']:
            writer.writerow(['normalized_trace', trace['run'], _safe(trace['analysis_id']), '', '', '',
                             'shape comparison only', point['time_ms'], point['scaled_value']])

    row_height = 34
    table_top = 86
    header_height = 54
    table_body_top = table_top + header_height
    table_bottom = table_body_top + row_height*len(summary)
    chart_top = table_bottom + 64
    chart_bottom = chart_top + 330
    height = chart_bottom + 92
    columns = [70, 140, 430, 610, 790, 970, 1130]
    palette = ['#007f67', '#d24b40', '#3976a8', '#9b6b25', '#6f5aa8', '#4f7f32', '#a34378', '#58636b']
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}">',
           f'<rect width="1200" height="{height}" fill="white"/><g font-family="Arial,sans-serif" fill="#202825">',
           '<text x="70" y="36" font-size="22" font-weight="600">Repeated-measurement Vc/Vt comparison</text>',
           '<text x="70" y="58" font-size="12">Backend Vt and Vc are pixel-area proxies; Vc/Vt is unitless. Missing rejected metrics remain blank.</text>']
    def centered(label, left, right, y, size=12):
        return f'<text x="{(left+right)/2}" y="{y}" text-anchor="middle" font-size="{size}" font-weight="600">{escape(label)}</text>'
    svg.extend([
        centered('Run', columns[0], columns[1], table_top+33),
        centered('Analysis', columns[1], columns[2], table_top+33),
        centered('Our method / backend', columns[2], columns[5], table_top+19, 13),
        centered('Quality', columns[5], columns[6], table_top+33),
        centered('Vt (px)', columns[2], columns[3], table_top+45),
        centered('Vc (px)', columns[3], columns[4], table_top+45),
        centered('Vc/Vt', columns[4], columns[5], table_top+45),
    ])
    for index, x in enumerate(columns[1:-1]):
        start_y = table_top if index in (0, 1, 4) else table_top+26
        svg.append(f'<path d="M{x} {start_y}V{table_bottom}" stroke="#c9cecb"/>')
    svg.append(f'<path d="M70 {table_top}H1130M430 {table_top+26}H970M70 {table_body_top}H1130M70 {table_bottom}H1130" stroke="#7f8984"/>')
    for index, row in enumerate(summary):
        y = table_body_top+row_height*index
        values = [str(row['run']), row['analysis_id'][:30], _number(row['vt_px']),
                  _number(row['vc_px']), _number(row['ratio']), _quality_label(row['quality_status'])]
        for column, value in enumerate(values):
            if column == 1:
                svg.append(f'<text x="{columns[column]+8}" y="{y+23}" font-size="12">{escape(value)}</text>')
            else:
                svg.append(centered(value, columns[column], columns[column+1], y+23, 11.5))
        if index < len(summary)-1:
            svg.append(f'<path d="M70 {y+row_height}H1130" stroke="#e3e6e4"/>')

    svg.append(f'<text x="70" y="{chart_top-24}" font-size="17" font-weight="600">Normalized respiratory waveform comparison</text>')
    plot_left, plot_right = 90, 1130
    duration = max([point['time_ms'] for trace in traces for point in trace['points']] or [1])
    for i in range(5):
        value = i/4
        y = chart_bottom-value*(chart_bottom-chart_top)
        svg.append(f'<path d="M{plot_left} {y}H{plot_right}" stroke="#dfe4e1"/><text x="{plot_left-10}" y="{y+4}" text-anchor="end" font-size="11">{value:.2f}</text>')
    for i in range(7):
        seconds = duration/1000*i/6
        x = plot_left+(plot_right-plot_left)*i/6
        svg.append(f'<path d="M{x} {chart_top}V{chart_bottom}" stroke="#eef0ef"/><text x="{x}" y="{chart_bottom+22}" text-anchor="middle" font-size="11">{seconds:.1f}</text>')
    for index, trace in enumerate(traces):
        color = palette[index % len(palette)]
        coordinates = ' '.join(f'{plot_left+point["time_ms"]/duration*(plot_right-plot_left):.2f},{chart_bottom-point["scaled_value"]*(chart_bottom-chart_top):.2f}' for point in trace['points'])
        if coordinates:
            svg.append(f'<polyline points="{coordinates}" fill="none" stroke="{color}" stroke-width="1.7" opacity="0.9"/>')
        legend_x = 90+(index % 4)*255
        legend_y = chart_bottom+50+(index//4)*20
        svg.append(f'<path d="M{legend_x} {legend_y}h20" stroke="{color}" stroke-width="2"/><text x="{legend_x+26}" y="{legend_y+4}" font-size="11">Run {index+1} · {escape(trace["analysis_id"][:16])}</text>')
    svg.append(f'<text x="{(plot_left+plot_right)/2}" y="{height-12}" text-anchor="middle" font-size="12">Time (s)</text>')
    svg.append(f'<text x="24" y="{(chart_top+chart_bottom)/2}" transform="rotate(-90 24 {(chart_top+chart_bottom)/2})" text-anchor="middle" font-size="12">Scaled value (0–1)</text></g></svg>')

    payload = {'export_version': 'went-comparison-export-v2',
               'notes': ['Each waveform is independently min-max scaled for shape comparison.',
                         'Vc and Vt are pixel-area proxies, not liters.',
                         'Rejected formal metrics remain null.'],
               'summary': summary, 'normalized_traces': traces}
    return {'comparison.json': json.dumps(payload, indent=2, allow_nan=False).encode('utf-8'),
            'comparison.csv': ('\ufeff'+output.getvalue()).encode('utf-8'),
            'comparison.svg': ''.join(svg).encode('utf-8'),
            'README.txt': b'The SVG contains a summary table and normalized overlaid traces. CSV contains the same summary plus long-form normalized trace data. Scaling is for waveform-shape comparison only. Pixel-area amplitudes are not liters.\n'}


def export_comparison_zip(results):
    output = io.BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for name, contents in comparison_files(results).items():
            archive.writestr(name, contents)
    return output.getvalue()
