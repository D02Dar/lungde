import { resampleAndFilter } from '../realtime/filter.js';

export const EXPORT_VERSION = 'went-review-export-v1';
export const COMPARISON_EXPORT_VERSION = 'went-comparison-export-v2';
const finite = Number.isFinite;
const escapeXml = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
export function phaseAt(ms, windows = {}) { return Object.entries(windows).find(([,w])=>Array.isArray(w)&&ms>=w[0]*1000&&ms<w[1]*1000)?.[0] || ''; }
export function traceRows(record) {
  const windows=record.captureRoi?.phase_windows || {};
  const rows=[];
  const append=(series,times,values)=>times?.forEach((ms,i)=>{ if(finite(ms)&&finite(values?.[i])) rows.push({series,time_ms:ms,phase:phaseAt(ms,windows),value:values[i]}); });
  const samples=(record.samples || []).filter(s=>finite(s.elapsedMs)&&finite(s.areaPx));
  append('realtime_raw',samples.map(s=>s.elapsedMs),samples.map(s=>s.areaPx));
  const clean=resampleAndFilter(samples,15);
  // This derived trace is explicitly versioned; legacy saved metrics are not recomputed.
  append('realtime_review_v3',clean.timestampsMs,clean.values);
  const offline=record.offline || {};
  append('offline_raw',offline.raw_timestamps_ms,offline.source_waveform);
  append('offline_resampled_raw',offline.timestamps_ms,offline.raw_waveform);
  append('offline_processed',offline.timestamps_ms,offline.waveform);
  return rows;
}
function waveformSource(options = {}) { return options?.source === 'realtime' ? 'realtime' : 'offline'; }
function sourceTraceRows(record, options = {}) {
  const source = waveformSource(options);
  return traceRows(record).filter(point => point.series.startsWith(source));
}
function sourceLabel(source) { return source === 'realtime' ? 'Frontend / realtime' : 'Backend / offline'; }
const PHASE_BANDS = [
  ['countdown','Ready','#f1f3f4'],
  ['tidal','Normal breathing','#edf3f7'],
  ['inhalePrep','Inhale prep','#f4f5f2'],
  ['maxInhale','Maximum inhale','#e8f3ed'],
  ['exhalePrep','Exhale prep','#f6f2ef'],
  ['maxExhale','Maximum exhale','#f8eaea'],
];
function median(values) {
  const sorted=values.filter(finite).sort((a,b)=>a-b);
  if(!sorted.length) return null;
  const middle=Math.floor(sorted.length/2);
  return sorted.length%2?sorted[middle]:(sorted[middle-1]+sorted[middle])/2;
}
function aggregatePhaseBands(records = []) {
  return PHASE_BANDS.map(([key,label,fill])=>{
    const windows=records.map(record=>record?.captureRoi?.phase_windows?.[key]).filter(window=>Array.isArray(window)&&finite(Number(window[0]))&&finite(Number(window[1])));
    const start=median(windows.map(window=>Number(window[0])*1000)),end=median(windows.map(window=>Number(window[1])*1000));
    return finite(start)&&finite(end)&&end>start?{key,label,fill,start_ms:start,end_ms:end}:null;
  }).filter(Boolean);
}
function phaseExtremumIndex(points, record, source, landmarkName, phaseNames, direction) {
  if (!points.length) return -1;
  const windows = phaseNames.map(name => record?.captureRoi?.phase_windows?.[name])
    .filter(window => Array.isArray(window) && window.length >= 2 && finite(Number(window[0])) && finite(Number(window[1])));
  const configuredPhase = windows.length > 0;
  const candidates = configuredPhase
    ? points.map((point, index) => ({point,index})).filter(({point}) => windows.some(window => point.time_ms >= Number(window[0]) * 1000 && point.time_ms <= Number(window[1]) * 1000))
    : points.map((point,index) => ({point,index}));
  // Never replace a missing target phase with a visually plausible global extremum.
  // That would turn an incomplete recording into a misleading formal landmark.
  if (!candidates.length) return -1;
  const savedLandmark = source === 'offline' ? record?.offline?.diagnostic?.landmarks?.[landmarkName]?.ms : null;
  const landmarkMs = Number(savedLandmark);
  const landmarkInPhase = !configuredPhase || windows.some(window => landmarkMs >= Number(window[0]) * 1000 && landmarkMs <= Number(window[1]) * 1000);
  if (savedLandmark != null && finite(landmarkMs) && landmarkInPhase) {
    return candidates.reduce((best, item) => Math.abs(item.point.time_ms - landmarkMs) < Math.abs(best.point.time_ms - landmarkMs) ? item : best).index;
  }
  const better = direction === 'low' ? (value, best) => value < best : (value, best) => value > best;
  return candidates.reduce((best, item) => better(item.point.value, best.point.value) ? item : best).index;
}
function inhalePeakIndex(points, record, source) { return phaseExtremumIndex(points, record, source, 'maxInhale', ['maxInhale','exhalePrep'], 'high'); }
function exhaleTroughIndex(points, record, source) { return phaseExtremumIndex(points, record, source, 'maxExhale', ['maxExhale'], 'low'); }
function primaryWaveformPoints(record, source) {
  const rows = sourceTraceRows(record, {source});
  const names = source === 'realtime'
    ? ['realtime_raw','realtime_review_v3']
    : ['offline_raw','offline_resampled_raw','offline_processed'];
  const series = names.map(name => rows.filter(point => point.series === name)).filter(points => points.length);
  return series.find(points => points[0].series.endsWith('processed') || points[0].series.includes('review')) || series.at(-1) || [];
}
function waveformLandmarks(record, options = {}) {
  const source = waveformSource(options), points = primaryWaveformPoints(record, source);
  const peakIndex = inhalePeakIndex(points, record, source), troughIndex = exhaleTroughIndex(points, record, source);
  return {
    source_series: points[0]?.series || 'unavailable',
    inhale_peak: peakIndex >= 0 ? points[peakIndex] : null,
    exhale_trough: troughIndex >= 0 ? points[troughIndex] : null,
  };
}
export function analysisJson(record, options = {}) {
  const source = waveformSource(options);
  return JSON.stringify({export_version:EXPORT_VERSION,exported_at:new Date().toISOString(),
    waveform_source:source,
    waveform_landmarks:waveformLandmarks(record,{source}),
    notes:['Pixel area proxies are not liters. Quality checks are not calibrated accuracy probabilities.',
      'Invalid formal metrics are null; provisional values are under diagnostic.',
      'Realtime review uses polarity-contour-amplitude-v4 for newly captured samples; legacy area-amplitude-v3 samples retain their original signal semantics.',
      'Missing raw arrays in legacy offline records remain unavailable; rerun offline analysis to populate them.'],
    record,trace_rows:sourceTraceRows(record,{source})},(key,value)=>{
      if(typeof Blob !== 'undefined' && value instanceof Blob) return {omitted_blob:true,size:value.size,type:value.type};
      if(typeof value==='string' && /^(data:|blob:)/.test(value)) return '[image/video payload omitted]';
      return value;
    },2);
}
function csvCell(value) {
  let text=value==null?'':String(value);
  if(typeof value==='string' && /^[=+\-@\t\r]/.test(text)) text="'"+text;
  return '"'+text.replace(/"/g,'""')+'"';
}
export function analysisCsv(record, options = {}) {
  const source = waveformSource(options);
  const rows=[['kind','series','time_ms','phase','name','value','unit','quality_status']];
  rows.push(['metadata','','','','waveform_source',source,'text','selected for export']);
  rows.push(['metadata','','','','record_title',record.title || '','text','local annotation']);
  rows.push(['metadata','','','','record_note',record.note || '','text','local annotation']);
  for(const point of sourceTraceRows(record,{source})) rows.push(['trace',point.series,point.time_ms,point.phase,'area',point.value,'pixel-area proxy','diagnostic trace']);
  const landmarks=waveformLandmarks(record,{source});
  for(const [name,point] of [['inhale_peak',landmarks.inhale_peak],['exhale_trough',landmarks.exhale_trough]]) rows.push(['landmark',landmarks.source_series,point?.time_ms ?? '',point?.phase || '',name,point?.value ?? '','pixel-area proxy',point?'phase-constrained extremum':'unavailable']);
  for(const [series,result,keys] of [['realtime',record.realtime,['vcPx','vtPx','ratio','rrBpm']],['offline',record.offline,['vc_px','vt_px','ratio','rr_bpm']]]) {
    if(!result) continue;
    const quality=result.qualityStatus || result.quality?.status || 'legacy_unvalidated';
    for(const key of keys) rows.push(['metric',series,'','',key,result[key],/ratio/.test(key)?'ratio':/rr/i.test(key)?'bpm':'pixel-area proxy',quality]);
    for(const [key,value] of Object.entries(result.diagnostic || {})) if(finite(value)) rows.push(['provisional',series,'','',key,value,'see JSON schema','not a formal result']);
    const reasons=result.invalidReasons || result.quality?.warnings || [];
    for(const reason of reasons) rows.push(['quality',series,'','reason',reason,'',quality]);
  }
  return '\uFEFF'+rows.map(row=>row.map(csvCell).join(',')).join('\r\n');
}
export function analysisSvg(record, options = {}) {
  const source=waveformSource(options),rows=sourceTraceRows(record,{source});
  const names=source==='realtime'?['realtime_raw','realtime_review_v3']:['offline_raw','offline_resampled_raw','offline_processed'];
  const series=names.map(name=>rows.filter(point=>point.series===name)).filter(points=>points.length),points=series.flat(),top=198,bottom=446;
  const tableTop=86,headerHeight=27,rowHeight=27,tableBodyTop=tableTop+headerHeight,tableBottom=tableBodyTop+rowHeight*2;
  const tableColumns=[70,280,445,610,775,940,1130];
  const metricRows=[
    ['Frontend / realtime',record?.realtime?.vtPx,record?.realtime?.vcPx,record?.realtime?.ratio,record?.realtime?.rrBpm,record?.realtime?.qualityStatus],
    ['Backend / offline',record?.offline?.vt_px,record?.offline?.vc_px,record?.offline?.ratio,record?.offline?.rr_bpm,record?.offline?.quality?.status],
  ];
  const fmt=(value,digits=2)=>finite(value)?Number(value).toFixed(digits):'--';
  const quality=value=>String(value||'Unavailable').replaceAll('_',' ');
  let body=`<rect width="1200" height="550" fill="white"/><g font-family="Arial,sans-serif" fill="#26333b"><text x="70" y="32" font-size="20" font-weight="600">Respiratory movement waveform and metrics</text><text x="70" y="55" font-size="12">${escapeXml(record.title || record.id || 'Measurement')} · Selected waveform: ${sourceLabel(source)}</text><text x="70" y="75" font-size="11" fill="#5d6964">Vt and Vc are pixel-area proxies; Vc/Vt is unitless. Formal values withheld by quality checks remain blank.</text>`;
  ['Path','Vt (px)','Vc (px)','Vc/Vt','RR (bpm)','Quality'].forEach((header,index)=>{body+=`<text x="${index===0?tableColumns[index]+8:(tableColumns[index]+tableColumns[index+1])/2}" y="${tableTop+19}"${index===0?'':' text-anchor="middle"'} font-size="11.5" font-weight="600">${escapeXml(header)}</text><path d="M${tableColumns[index+1]} ${tableTop}V${tableBottom}" stroke="#c9cecb"/>`;});
  body+=`<path d="M70 ${tableTop}H1130M70 ${tableBodyTop}H1130M70 ${tableBottom}H1130" stroke="#7f8984"/>`;
  metricRows.forEach((values,index)=>{const y=tableBodyTop+rowHeight*index;const display=[values[0],fmt(values[1],1),fmt(values[2],1),fmt(values[3]),fmt(values[4],1),quality(values[5])];display.forEach((value,column)=>{body+=`<text x="${column===0?tableColumns[column]+8:(tableColumns[column]+tableColumns[column+1])/2}" y="${y+18}"${column===0?'':' text-anchor="middle"'} font-size="11">${escapeXml(value)}</text>`;});if(index===0)body+=`<path d="M70 ${y+rowHeight}H1130" stroke="#e3e6e4"/>`;});
  body+=`<text x="70" y="${top-18}" font-size="13" font-weight="600">${escapeXml(sourceLabel(source))} waveform</text><text x="1130" y="${top-18}" text-anchor="end" font-size="10.5" fill="#5d6964">Horizontal: elapsed time · Vertical: measured image area (pixels²)</text>`;
  if(!points.length) body+=`<text x="70" y="${top+90}" font-size="15">No data available — this record has no ${escapeXml(sourceLabel(source).toLowerCase())} waveform.</text>`;
  else {
    const min=Math.min(...points.map(p=>p.value)),max=Math.max(...points.map(p=>p.value)),pad=Math.max((max-min)*.05,1),lo=min-pad,hi=max+pad,duration=Math.max(1,...points.map(p=>p.time_ms));
    const x=ms=>90+ms/duration*1050,y=value=>bottom-(value-lo)/(hi-lo)*(bottom-top);
    for(const band of aggregatePhaseBands([record])){const left=x(Math.max(0,band.start_ms)),right=x(Math.min(duration,band.end_ms)),width=Math.max(0,right-left);if(width<=0)continue;body+=`<rect x="${left}" y="${top}" width="${width}" height="${bottom-top}" fill="${band.fill}"/><path d="M${left} ${top}V${bottom}" stroke="#d5dcda"/><text x="${left+width/2}" y="${top+13}" text-anchor="middle" font-size="9" fill="#66716c">${escapeXml(band.label)}</text>`;}
    for(let i=0;i<=4;i++){const value=lo+(hi-lo)*i/4,yy=y(value);body+=`<path d="M90 ${yy}H1140" stroke="#dde3e0"/><text x="80" y="${yy+4}" font-size="11" text-anchor="end">${value.toFixed(0)}</text>`;}
    for(let i=0;i<=6;i++){const xx=90+1050*i/6,seconds=duration/1000*i/6;body+=`<path d="M${xx} ${top}V${bottom}" stroke="#eef0ef"/><text x="${xx}" y="${bottom+21}" text-anchor="middle" font-size="11">${seconds.toFixed(1)}</text>`;}
    const colorFor=name=>name.endsWith('processed')||name.includes('review')?'#00866a':name.includes('resampled')?'#4d86b5':'#a7afb4';
    series.forEach(values=>{const name=values[0].series,primary=name.endsWith('processed')||name.includes('review');body+=`<polyline fill="none" stroke="${colorFor(name)}" stroke-width="${primary?2:1.2}" points="${values.map(p=>`${x(p.time_ms).toFixed(2)},${y(p.value).toFixed(2)}`).join(' ')}"/>`;});
    const { inhale_peak:peak, exhale_trough:trough }=waveformLandmarks(record,{source});
    if(peak){const px=x(peak.time_ms),py=y(peak.value),anchor=px>970?'end':'start',dx=anchor==='end'?-9:9,label=record?.captureRoi?.phase_windows?.maxInhale||finite(Number(record?.offline?.diagnostic?.landmarks?.maxInhale?.ms))?'Inhale peak':'Waveform peak',labelY=py-top<22?py+22:py-9;body+=`<path d="M${px} ${py}V${bottom}" stroke="#c8322f" stroke-width="1" stroke-dasharray="3 4" opacity=".6"/><circle cx="${px}" cy="${py}" r="4.5" fill="#c8322f" stroke="white" stroke-width="2"/><text x="${px+dx}" y="${labelY}" text-anchor="${anchor}" font-size="11" font-weight="600" fill="#a52c2a">${label} · ${(peak.time_ms/1000).toFixed(1)} s · ${peak.value.toFixed(1)} px²</text>`;}
    if(trough){const tx=x(trough.time_ms),ty=y(trough.value),anchor=tx>970?'end':'start',dx=anchor==='end'?-9:9,label=record?.captureRoi?.phase_windows?.maxExhale||finite(Number(record?.offline?.diagnostic?.landmarks?.maxExhale?.ms))?'Exhale trough':'Waveform trough',labelY=bottom-ty<22?ty-10:ty+19;body+=`<path d="M${tx} ${ty}V${bottom}" stroke="#2878b8" stroke-width="1" stroke-dasharray="3 4" opacity=".6"/><path d="M${tx} ${ty-5}L${tx+5} ${ty}L${tx} ${ty+5}L${tx-5} ${ty}Z" fill="#2878b8" stroke="white" stroke-width="1.5"/><text x="${tx+dx}" y="${labelY}" text-anchor="${anchor}" font-size="11" font-weight="600" fill="#226797">${label} · ${(trough.time_ms/1000).toFixed(1)} s · ${trough.value.toFixed(1)} px²</text>`;}
    body+=`<text x="615" y="491" text-anchor="middle" font-size="12">Elapsed recording time (seconds)</text><text x="23" y="${(top+bottom)/2}" transform="rotate(-90 23 ${(top+bottom)/2})" text-anchor="middle" font-size="12">Image area (pixels²)</text>`;
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="550" viewBox="0 0 1200 550">${body}</g></svg>`;
}
export function downloadAnalysis(record,format,options = {}) {
  const exporters={json:[analysisJson,'application/json'],csv:[analysisCsv,'text/csv;charset=utf-8'],svg:[analysisSvg,'image/svg+xml']};
  const [build,type]=exporters[format];
  const url=URL.createObjectURL(new Blob([build(record,options)],{type}));
  const anchor=document.createElement('a'); anchor.href=url; anchor.download=`went-${String(record.id||'measurement').replace(/[^\w-]/g,'_')}.${format}`;
  document.body.appendChild(anchor); anchor.click(); anchor.remove(); setTimeout(()=>URL.revokeObjectURL(url),10000);
}

function runLabel(record, index) {
  if (String(record?.title || '').trim()) return String(record.title).trim();
  const date = new Date(record?.createdAt);
  const stamp = Number.isNaN(date.getTime()) ? '' : date.toISOString().replace('T', ' ').slice(0, 19);
  return stamp || String(record?.id || `Run ${index + 1}`);
}
function preferredComparisonTrace(record, source = 'offline') {
  const rows = traceRows(record);
  const preferred = source === 'realtime'
    ? ['realtime_review_v3', 'realtime_raw']
    : ['offline_processed', 'offline_resampled_raw', 'offline_raw'];
  for (const series of preferred) {
    const points = rows.filter(point => point.series === series && finite(point.time_ms) && finite(point.value));
    if (points.length < 2) continue;
    const values = points.map(point => point.value), low = Math.min(...values), high = Math.max(...values), span = high - low;
    const scaledPoints = points.map(point => ({ time_ms: point.time_ms, scaled_value: span > 1e-12 ? (point.value - low) / span : .5 }));
    const peakIndex = inhalePeakIndex(points, record, source);
    const troughIndex = exhaleTroughIndex(points, record, source);
    return { series, points: scaledPoints, peak: peakIndex >= 0 ? scaledPoints[peakIndex] : null, trough: troughIndex >= 0 ? scaledPoints[troughIndex] : null };
  }
  return { series: 'unavailable', points: [], peak: null, trough: null };
}
export function comparisonRows(records = [], options = {}) {
  const source = waveformSource(options);
  return records.map((record, index) => {
    const realtimeRatio = record?.realtime?.ratio;
    const offlineRatio = record?.offline?.ratio;
    const realtimeVc = record?.realtime?.vcPx;
    const realtimeVt = record?.realtime?.vtPx;
    const offlineVc = record?.offline?.vc_px;
    const offlineVt = record?.offline?.vt_px;
    return {
      run: index + 1,
      id: String(record?.id || `run-${index + 1}`),
      label: runLabel(record, index),
      note: String(record?.note || ''),
      created_at: record?.createdAt || null,
      realtime_ratio: finite(realtimeRatio) ? realtimeRatio : null,
      offline_ratio: finite(offlineRatio) ? offlineRatio : null,
      realtime_vc_px: finite(realtimeVc) ? realtimeVc : null,
      realtime_vt_px: finite(realtimeVt) ? realtimeVt : null,
      offline_vc_px: finite(offlineVc) ? offlineVc : null,
      offline_vt_px: finite(offlineVt) ? offlineVt : null,
      difference_percent: finite(realtimeRatio) && finite(offlineRatio) && Math.abs(realtimeRatio) > 1e-12 ? Math.abs(offlineRatio - realtimeRatio) / Math.abs(realtimeRatio) * 100 : null,
      // Retain the v1 aliases for consumers that already read the offline-only fields.
      vc_px: finite(offlineVc) ? offlineVc : null,
      vt_px: finite(offlineVt) ? offlineVt : null,
      quality_status: record?.offline?.quality?.status || record?.realtime?.qualityStatus || 'legacy_unvalidated',
      ...preferredComparisonTrace(record, source),
    };
  });
}
export function comparisonJson(records, options = {}) {
  const source = waveformSource(options), rows = comparisonRows(records, {source});
  return JSON.stringify({
    export_version: COMPARISON_EXPORT_VERSION,
    exported_at: new Date().toISOString(),
    waveform_source: source,
    phase_intervals: aggregatePhaseBands(records),
    notes: [
      'Difference (%) compares offline Vc/Vt with realtime Vc/Vt; it is not error against a spirometer.',
      'Each waveform is independently min-max scaled to 0–1 for shape comparison.',
      'Vc and Vt are image pixel-area proxies, not liters. Rejected formal metrics remain null.',
    ],
    summary: rows.map(({ points, ...row }) => row),
    normalized_traces: rows.map(row => ({ run: row.run, id: row.id, label: row.label, source_series: row.series, inhale_peak: row.peak, exhale_trough: row.trough, points: row.points })),
  }, null, 2);
}
export function comparisonCsv(records, options = {}) {
  const source = waveformSource(options), rows = comparisonRows(records, {source});
  const table = [['kind','run','record_id','label','note','realtime_vt_px','realtime_vc_px','realtime_vc_vt','offline_vt_px','offline_vc_px','offline_vc_vt','difference_percent','quality_status','source_series','time_ms','scaled_value','inhale_peak_time_ms','exhale_trough_time_ms']];
  for (const row of rows) {
    table.push(['summary',row.run,row.id,row.label,row.note,row.realtime_vt_px,row.realtime_vc_px,row.realtime_ratio,row.offline_vt_px,row.offline_vc_px,row.offline_ratio,row.difference_percent,row.quality_status,row.series,'','',row.peak?.time_ms,row.trough?.time_ms]);
    for (const point of row.points) table.push(['normalized_trace',row.run,row.id,row.label,row.note,'','','','','','','','shape comparison only',row.series,point.time_ms,point.scaled_value,'','']);
  }
  return '\uFEFF' + table.map(row => row.map(csvCell).join(',')).join('\r\n');
}
export function comparisonSvg(records, options = {}) {
  const source = waveformSource(options), rows = comparisonRows(records, {source});
  if (!rows.length) throw new Error('Select at least one record');
  const rowHeight = 28, tableTop = 88, headerHeight = 52, tableBodyTop = tableTop + headerHeight, tableBottom = tableBodyTop + rowHeight * rows.length;
  const chartTitleY = tableBottom + 45, chartTop = chartTitleY + 80, chartBottom = chartTop + 280, legendTop = chartBottom + 72;
  const legendRows = Math.max(1, Math.ceil(rows.length / 4)), height = legendTop + legendRows * 20 + 32;
  const columns = [55,105,285,375,465,555,645,735,825,945,1145];
  const colors = ['#007f67','#d24b40','#3976a8','#9b6b25','#6f5aa8','#4f7f32','#a34378','#58636b'];
  const fmt = (value, digits=2) => finite(value) ? value.toFixed(digits) : '--';
  const qualityLabel = value => ({checks_passed:'Checks passed',usable_with_caution:'Usable with caution',review_required:'Review required',rejected:'Rejected',legacy_unvalidated:'Legacy / unvalidated'}[value] || String(value || 'Unavailable').replaceAll('_',' '));
  const centered = (label, left, right, y, size=12) => `<text x="${(left+right)/2}" y="${y}" text-anchor="middle" font-size="${size}" font-weight="600">${escapeXml(label)}</text>`;
  let body = `<rect width="1200" height="${height}" fill="white"/><g font-family="Arial,sans-serif" fill="#202825"><text x="55" y="30" font-size="22" font-weight="600">Repeated-measurement Vc/Vt comparison</text><text x="55" y="52" font-size="12">Waveform source: ${sourceLabel(source)} · Difference compares backend with frontend, not against a spirometer.</text><text x="55" y="69" font-size="11" fill="#69736f">Vt and Vc are pixel-area proxies; Vc/Vt is unitless. — means unavailable or withheld by quality checks.</text>`;
  body += centered('Run', columns[0], columns[1], tableTop+32, 12);
  body += centered('Measurement', columns[1], columns[2], tableTop+32, 12);
  body += centered('Frontend / realtime', columns[2], columns[5], tableTop+18, 12.5);
  body += centered('Backend / offline', columns[5], columns[8], tableTop+18, 12.5);
  body += centered('Difference (%)', columns[8], columns[9], tableTop+32, 12);
  body += centered('Quality', columns[9], columns[10], tableTop+32, 12);
  ['Vt (px)','Vc (px)','Vc/Vt','Vt (px)','Vc (px)','Vc/Vt'].forEach((header,index) => {
    body += centered(header, columns[index+2], columns[index+3], tableTop+43, 11.5);
  });
  columns.slice(1,-1).forEach((x,index) => {
    const groupBoundary = [0,1,4,7,8].includes(index);
    const startY = groupBoundary ? tableTop : tableTop+24;
    body += `<path d="M${x} ${startY}V${tableBottom}" stroke="#c9cecb"/>`;
  });
  body += `<path d="M55 ${tableTop}H1145M285 ${tableTop+24}H825M55 ${tableBodyTop}H1145M55 ${tableBottom}H1145" stroke="#7f8984"/>`;
  rows.forEach((row,index) => {
    const y=tableBodyTop+rowHeight*index;
    const values=[row.run,String(row.label).slice(0,25),fmt(row.realtime_vt_px,1),fmt(row.realtime_vc_px,1),fmt(row.realtime_ratio),fmt(row.offline_vt_px,1),fmt(row.offline_vc_px,1),fmt(row.offline_ratio),fmt(row.difference_percent,1),qualityLabel(row.quality_status)];
    values.forEach((value,column)=>{ const center=column!==1; body+=`<text x="${center?(columns[column]+columns[column+1])/2:columns[column]+7}" y="${y+19}"${center?' text-anchor="middle"':''} font-size="${column===9?'10.5':'11'}">${escapeXml(value)}</text>`; });
    if(index<rows.length-1) body+=`<path d="M55 ${y+rowHeight}H1145" stroke="#e3e6e4"/>`;
  });
  const plotLeft=90,plotRight=1145,duration=Math.max(1,...rows.flatMap(row=>row.points.map(point=>point.time_ms)));
  body+=`<text x="55" y="${tableBottom+18}" font-size="10.5" fill="#69736f">Table values summarize each run; empty values are not converted to zero.</text><text x="55" y="${chartTitleY}" font-size="17" font-weight="600">Normalized waveform shape</text><text x="55" y="${chartTitleY+18}" font-size="11" fill="#69736f">Each run is scaled independently: 0 = that run’s minimum, 1 = that run’s maximum. Compare timing and shape, not amplitude.</text><text x="55" y="${chartTitleY+40}" font-size="10.5" font-weight="600" fill="#4e5955">Inhale peaks</text>`;
  rows.forEach((row,index)=>{const x=135+index*126,color=colors[index%colors.length],label=row.peak?`R${row.run} · ${(row.peak.time_ms/1000).toFixed(1)} s`:`R${row.run} · unavailable`;body+=`<circle cx="${x}" cy="${chartTitleY+37}" r="3.5" fill="${color}"/><text x="${x+7}" y="${chartTitleY+41}" font-size="10" fill="${color}">${label}</text>`;});
  body+=`<text x="55" y="${chartTitleY+60}" font-size="10.5" font-weight="600" fill="#4e5955">Exhale troughs</text>`;
  rows.forEach((row,index)=>{const x=135+index*126,color=colors[index%colors.length],label=row.trough?`R${row.run} · ${(row.trough.time_ms/1000).toFixed(1)} s`:`R${row.run} · unavailable`;body+=`<path d="M${x} ${chartTitleY+53}l4 4-4 4-4-4Z" fill="white" stroke="${color}" stroke-width="1.5"/><text x="${x+7}" y="${chartTitleY+61}" font-size="10" fill="${color}">${label}</text>`;});
  for(const band of aggregatePhaseBands(records)){const left=plotLeft+Math.max(0,band.start_ms)/duration*(plotRight-plotLeft),right=plotLeft+Math.min(duration,band.end_ms)/duration*(plotRight-plotLeft),width=Math.max(0,right-left);if(width<=0)continue;body+=`<rect x="${left}" y="${chartTop}" width="${width}" height="${chartBottom-chartTop}" fill="${band.fill}"/><path d="M${left} ${chartTop}V${chartBottom}" stroke="#d5dcda"/><text x="${left+width/2}" y="${chartTop+13}" text-anchor="middle" font-size="9" fill="#66716c">${escapeXml(band.label)}</text>`;}
  for(let i=0;i<=4;i++){const value=i/4,y=chartBottom-value*(chartBottom-chartTop);body+=`<path d="M${plotLeft} ${y}H${plotRight}" stroke="#dfe4e1"/><text x="${plotLeft-10}" y="${y+4}" text-anchor="end" font-size="11">${value.toFixed(2)}</text>`;}
  for(let i=0;i<=6;i++){const x=plotLeft+(plotRight-plotLeft)*i/6,seconds=duration/1000*i/6;body+=`<path d="M${x} ${chartTop}V${chartBottom}" stroke="#eef0ef"/><text x="${x}" y="${chartBottom+22}" text-anchor="middle" font-size="11">${seconds.toFixed(1)}</text>`;}
  rows.forEach((row,index)=>{
    const color=colors[index%colors.length];
    if(row.points.length) body+=`<polyline fill="none" stroke="${color}" stroke-width="1.7" opacity=".9" points="${row.points.map(point=>`${(plotLeft+point.time_ms/duration*(plotRight-plotLeft)).toFixed(2)},${(chartBottom-point.scaled_value*(chartBottom-chartTop)).toFixed(2)}`).join(' ')}"/>`;
    if(row.peak){const px=plotLeft+row.peak.time_ms/duration*(plotRight-plotLeft),py=chartBottom-row.peak.scaled_value*(chartBottom-chartTop);body+=`<circle cx="${px}" cy="${py}" r="4.5" fill="${color}" stroke="white" stroke-width="1.75"/>`;}
    if(row.trough){const tx=plotLeft+row.trough.time_ms/duration*(plotRight-plotLeft),ty=chartBottom-row.trough.scaled_value*(chartBottom-chartTop);body+=`<path d="M${tx} ${ty-5}L${tx+5} ${ty}L${tx} ${ty+5}L${tx-5} ${ty}Z" fill="white" stroke="${color}" stroke-width="2"/>`;}
    const x=90+(index%4)*262,y=legendTop+Math.floor(index/4)*20;
    const availability=row.points.length?sourceLabel(source):`${sourceLabel(source)} unavailable`;
    body+=`<path d="M${x} ${y}h20" stroke="${color}" stroke-width="2"/><text x="${x+26}" y="${y+4}" font-size="11">Run ${row.run} · ${escapeXml(availability)}</text>`;
  });
  body+=`<text x="617" y="${chartBottom+43}" text-anchor="middle" font-size="12">Elapsed recording time (seconds)</text><text x="22" y="${(chartTop+chartBottom)/2}" transform="rotate(-90 22 ${(chartTop+chartBottom)/2})" text-anchor="middle" font-size="12">Normalized shape within each run (0–1)</text></g>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="${height}" viewBox="0 0 1200 ${height}">${body}</svg>`;
}
export function downloadComparison(records, format, options = {}) {
  const exporters={json:[comparisonJson,'application/json'],csv:[comparisonCsv,'text/csv;charset=utf-8'],svg:[comparisonSvg,'image/svg+xml']};
  const selected=Array.from(records || []).slice(0,8), pair=exporters[format];
  if(!selected.length) throw new Error('Select at least one record');
  if(!pair) throw new Error(`Unsupported export format: ${format}`);
  const [build,type]=pair,url=URL.createObjectURL(new Blob([build(selected,options)],{type}));
  const anchor=document.createElement('a'); anchor.href=url; anchor.download=`went-comparison-${selected.length}-runs.${format}`;
  document.body.appendChild(anchor); anchor.click(); anchor.remove(); setTimeout(()=>URL.revokeObjectURL(url),10000);
}
