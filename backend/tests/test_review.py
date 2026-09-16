import io
import json
from zipfile import ZipFile
import numpy as np
import pytest
from app.analysis.review import review_signal
from app.analysis.export import export_comparison_zip, export_zip


def fixture():
    fps = 20
    t = np.arange(0, 38, 1/fps)
    raw = 30000 + 100*np.sin(2*np.pi*.25*t)
    raw[(t>=18)&(t<24)] = 30000+(t[(t>=18)&(t<24)]-18)/6*2000
    raw[(t>=24)&(t<29)] = 32000
    raw[(t>=29)&(t<35)] = 32000-(t[(t>=29)&(t<35)]-29)/6*2000
    raw[t>=35] = 30000
    return raw, t*1000, fps, {'tidal':(3,15),'maxInhale':(18,26),'exhalePrep':(26,29),'maxExhale':(29,37)}


def test_slow_manoeuvre_preserves_dc_plateau_and_ratio():
    raw, times, fps, phases = fixture()
    result = review_signal(raw, times, fps, phases)
    assert result['quality_status'] == 'checks_passed'
    assert result['metrics']['vc_px'] == pytest.approx(2000, rel=.03)
    assert result['metrics']['vt_px'] == pytest.approx(200, rel=.05)
    assert result['metrics']['ratio'] == pytest.approx(10, rel=.05)
    assert np.median(result['waveform'][(times>=24500)&(times<28000)]) == pytest.approx(32000)


def test_missing_tidal_frames_withhold_vt_but_preserve_vc():
    raw, times, fps, phases = fixture()
    keep = ~((times>6000)&(times<8500))
    result = review_signal(raw[keep],times[keep],fps,phases)
    assert result['metrics']['vt_px'] is None
    assert result['metrics']['ratio'] is None
    assert result['metrics']['vc_px'] is not None
    assert 'incomplete_tidal' in result['diagnostic']['vt_reasons']
    assert result['diagnostic']['vt_px'] is not None


def test_truncated_exhale_withholds_vc_not_tidal():
    raw, times, fps, phases = fixture()
    keep=times<32000
    result=review_signal(raw[keep],times[keep],fps,phases)
    assert result['metrics']['vt_px'] is not None
    assert result['metrics']['vc_px'] is None
    assert 'incomplete_maxExhale' in result['diagnostic']['vc_reasons']


def test_noise_in_tidal_does_not_poison_vital_noise_estimate():
    raw, times, fps, phases=fixture()
    mask=(times>=3000)&(times<15000)
    raw[mask]+=np.random.default_rng(4).normal(0,600,mask.sum())
    result=review_signal(raw,times,fps,phases)
    assert result['metrics']['vt_px'] is None
    assert result['metrics']['vc_px'] is not None


def test_timestamp_origin_and_missing_phases():
    raw,times,fps,phases=fixture()
    offset=2500
    shifted={key:(a+offset/1000,b+offset/1000) for key,(a,b) in phases.items()}
    a=review_signal(raw,times,fps,phases)
    b=review_signal(raw,times+offset,fps,shifted)
    assert b['timestamps_ms'][0] == offset
    assert b['metrics']['ratio'] == pytest.approx(a['metrics']['ratio'])
    assert review_signal(raw,times,fps,{'maxInhale':(100,102)})['metrics']['ratio'] is None


def test_flat_signal_is_not_a_valid_result():
    raw,times,fps,phases=fixture()
    result=review_signal(np.full_like(raw,30000),times,fps,phases)
    assert result['quality_status']=='review_required'
    assert result['metrics']['ratio'] is None


def test_moderate_tidal_variability_keeps_values_with_caution():
    raw, times, fps, phases = fixture()
    seconds = times/1000
    amplitude = np.select([seconds < 7, seconds < 11], [20, 100], default=180)
    tidal = (seconds >= 3) & (seconds < 15)
    raw[tidal] = 30000 + amplitude[tidal]*np.sin(2*np.pi*.25*seconds[tidal])
    result = review_signal(raw, times, fps, phases)
    assert result['quality_status'] == 'usable_with_caution'
    assert result['metrics']['vt_px'] is not None
    assert result['metrics']['ratio'] is not None
    assert result['diagnostic']['vt_reasons'] == []
    assert 'variable_tidal_amplitudes' in result['diagnostic']['vt_warnings']


def test_export_is_portable_and_preserves_nulls():
    result={'vc_px':None,'vt_px':None,'ratio':None,'quality':{'status':'review_required','warnings':['=unsafe']},
            'diagnostic':{'vc_px':12.5},'waveform':[5,6,7],'timestamps_ms':[0,100,200],
            'source_waveform':[4,6,8],'raw_timestamps_ms':[0,100,200]}
    with ZipFile(io.BytesIO(export_zip(result))) as archive:
        assert set(archive.namelist())=={'analysis.csv','analysis.json','waveform.svg','README.txt'}
        parsed=json.loads(archive.read('analysis.json'))
        assert parsed['vc_px'] is None and parsed['diagnostic']['vc_px']==12.5
        csv=archive.read('analysis.csv').decode('utf-8-sig')
        assert "'=unsafe" in csv and 'offline_raw' in csv
        assert '<polyline' in archive.read('waveform.svg').decode()


def test_multi_run_export_contains_summary_table_and_scaled_traces():
    first = {'analysis_id': 'run-one', 'vc_px': 600, 'vt_px': 150, 'ratio': 4,
             'quality': {'status': 'checks_passed'}, 'timestamps_ms': [0, 100, 200],
             'waveform': [10, 20, 15]}
    second = {'analysis_id': 'run-two', 'vc_px': None, 'vt_px': None, 'ratio': None,
              'quality': {'status': 'review_required'}, 'timestamps_ms': [0, 100, 200],
              'waveform': [2, 4, 3]}
    with ZipFile(io.BytesIO(export_comparison_zip([first, second]))) as archive:
        assert set(archive.namelist()) == {'comparison.csv', 'comparison.json', 'comparison.svg', 'README.txt'}
        payload = json.loads(archive.read('comparison.json'))
        assert len(payload['summary']) == 2
        assert payload['summary'][1]['ratio'] is None
        assert [point['scaled_value'] for point in payload['normalized_traces'][0]['points']] == [0, 1, .5]
        svg = archive.read('comparison.svg').decode()
        assert 'Repeated-measurement Vc/Vt comparison' in svg
        assert 'Our method / backend' in svg
        assert 'Vt (px)' in svg and 'Vc (px)' in svg and 'Vc/Vt' in svg
        assert 'run-one' in svg and 'run-two' in svg and '<polyline' in svg
