"""Read-only capture analysis shared by HTTP and reproducible notebook review."""
import numpy as np
from .offline import extract_area_signal
from .fusion import fuse_signals
from .roi import normalized_to_pixels, ensure_inside
from .review import review_signal, VERSION


def capture_roi(metadata, source):
    operator = normalized_to_pixels(metadata.operator_roi, source.width, source.height)
    if metadata.roi_contract_version == 'went-roi-v2':
        roi = normalized_to_pixels(metadata.realtime_chest_roi, source.width, source.height)
        ensure_inside(roi, operator)
        if metadata.position_quality.status != 'locked':
            raise ValueError('Position quality was not locked for this ROI contract')
        return roi, 'locked_contract', []
    return operator, 'legacy_auto', ['Legacy record: operator ROI used; locked calibration is unavailable.']


def review_capture(source, metadata):
    roi, roi_source, warnings = capture_roi(metadata, source)
    try:
        threshold = float(metadata.calibration.get('referenceThreshold'))
        if not np.isfinite(threshold): threshold = None
    except (TypeError, ValueError):
        threshold = None
    polarity = metadata.calibration.get('polarity') or metadata.position_quality.subject_polarity
    extracted = extract_area_signal(source, roi, reference_threshold=threshold,
                                   dark_subject=True if polarity == 'dark' else False if polarity == 'light' else None,
                                   phase_windows=metadata.phase_windows)
    review = review_signal(extracted.raw, extracted.timestamps_ms, source.fps, metadata.phase_windows,
                           roi_pixels=roi.width*roi.height, valid_frame_ratio=extracted.valid_frame_ratio)
    if not extracted.dark_subject and extracted.highlight_saturation_ratio >= .08:
        warnings.append('light_subject_saturation')
        if review['quality_status'] == 'checks_passed':
            review['quality_status'] = 'usable_with_caution'
    review['diagnostic'].update({'search_roi': roi.model_dump(), 'analysis_roi': extracted.analysis_roi.model_dump(),
                                 'row_selection_method': extracted.row_selection_method,
                                 'signal_method': extracted.signal_method,
                                 'highlight_saturation_ratio': extracted.highlight_saturation_ratio,
                                 'selected_row_fraction': len(extracted.selected_rows) / max(1, roi.height)})
    return roi, roi_source, warnings, extracted, review


def review_comparison(metadata, extracted, review):
    """Align both paths for review without changing offline Vc/Vt metrics."""
    explicit_realtime = [sample.quality for sample in metadata.realtime_samples
                         if sample.quality is not None and np.isfinite(sample.quality)]
    realtime_quality = float(np.clip(np.median(explicit_realtime), 0.05, 1.0)) if explicit_realtime else 0.5
    status_weight = {
        'checks_passed': 1.0,
        'usable_with_caution': 0.7,
        'review_required': 0.2,
        'rejected': 0.05,
    }.get(review['quality_status'], 0.35)
    signal_support = float(np.clip((extracted.valid_frame_ratio + extracted.temporal_coherence) / 2, 0.05, 1.0))
    offline_quality = float(np.clip(status_weight * signal_support, 0.05, 1.0))
    return fuse_signals(
        metadata.realtime_samples,
        review['timestamps_ms'],
        review['waveform'],
        metadata.phase_windows,
        realtime_quality=realtime_quality,
        offline_quality=offline_quality,
    )


def review_video_file(video_path, capture_metadata, declared_duration_ms=None):
    """No database writes or HTTP requests. Same extraction and metric path as API."""
    from .video import read_video
    from ..schemas import CaptureMetadata
    metadata = CaptureMetadata.model_validate(capture_metadata)
    source = read_video(video_path, declared_duration_ms=declared_duration_ms)
    try:
        roi, roi_source, warnings, extracted, review = review_capture(source, metadata)
        comparison = review_comparison(metadata, extracted, review)
        warnings += (review['diagnostic']['vt_reasons'] + review['diagnostic']['vc_reasons']
                     + review['diagnostic']['vt_warnings'] + review['diagnostic']['vc_warnings'])
        if comparison:
            warnings += comparison.warnings
        return {**review['metrics'], 'algorithm_version': VERSION, 'confidence': None,
                'waveform': review['waveform'].tolist(), 'timestamps_ms': review['timestamps_ms'].tolist(),
                'raw_waveform': review['raw'].tolist(), 'source_waveform': extracted.raw.tolist(),
                'raw_timestamps_ms': extracted.timestamps_ms.tolist(), 'diagnostic': review['diagnostic'],
                'comparison': comparison.model_dump() if comparison else None,
                'roi': extracted.analysis_roi.model_dump(), 'roi_source': roi_source, 'selected_rows': extracted.selected_rows.tolist(),
                'diagnostics': {**source.diagnostics, 'capture_width': metadata.frame_width, 'capture_height': metadata.frame_height,
                                'reference_threshold': extracted.reference_threshold, 'subject_polarity': 'dark' if extracted.dark_subject else 'light',
                                'signal_method': extracted.signal_method, 'highlight_saturation_ratio': extracted.highlight_saturation_ratio},
                'quality': {'status': review['quality_status'], 'warnings': sorted(set(warnings)),
                            'valid_frame_ratio': extracted.valid_frame_ratio, 'periodicity': review['metrics']['periodicity'],
                            'snr': review['metrics']['snr'], 'temporal_coherence': extracted.temporal_coherence},
                'capture_metadata': capture_metadata}
    finally:
        source.close()
