"""Audio descriptor extraction.

Uses librosa (with soundfile) as the default backend. Optional extras:
pyloudnorm for integrated loudness, Essentia if installed. All optional
dependencies degrade gracefully — the app never hard-fails on a missing
audio backend; it records a warning in the descriptor set instead.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional, Union

import numpy as np

from .models import AudioDescriptorSet

try:  # librosa is the default backend but the app must survive without it
    import librosa

    LIBROSA_AVAILABLE = True
except ImportError:  # pragma: no cover - environment dependent
    librosa = None
    LIBROSA_AVAILABLE = False

try:
    import pyloudnorm

    PYLOUDNORM_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    pyloudnorm = None
    PYLOUDNORM_AVAILABLE = False

try:  # Essentia is a bonus, never required
    import essentia.standard  # noqa: F401

    ESSENTIA_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    ESSENTIA_AVAILABLE = False

SUPPORTED_EXTENSIONS = (".wav", ".aiff", ".aif", ".flac", ".mp3", ".ogg")


def _estimate_tempo(y: np.ndarray, sr: int) -> Optional[float]:
    """Estimate tempo, tolerating librosa API differences across versions."""
    try:
        try:
            from librosa.feature import rhythm

            tempo = rhythm.tempo(y=y, sr=sr)
        except ImportError:
            tempo = librosa.beat.tempo(y=y, sr=sr)
        value = float(np.atleast_1d(tempo)[0])
        return round(value, 2) if value > 0 else None
    except Exception:
        return None


def extract_descriptors(
    source: Union[str, Path, bytes, io.BytesIO],
    descriptor_id: str,
    source_id: str,
    source_type: str = "file",
    file_path: Optional[str] = None,
) -> AudioDescriptorSet:
    """Extract a descriptor set from an audio file path or in-memory bytes.

    Returns a populated AudioDescriptorSet; on failure, returns a set whose
    ``warnings`` explain what could not be computed.
    """
    warnings: list[str] = []
    result = AudioDescriptorSet(
        id=descriptor_id,
        source_id=source_id,
        source_type=source_type,
        file_path=file_path,
        warnings=warnings,
    )

    if not LIBROSA_AVAILABLE:
        warnings.append(
            "librosa is not installed; audio descriptors are unavailable. "
            "Install requirements.txt to enable descriptor extraction."
        )
        return result

    try:
        if isinstance(source, bytes):
            source = io.BytesIO(source)
        y, sr = librosa.load(source, sr=None, mono=True)
    except Exception as exc:
        warnings.append(f"Could not decode audio: {exc}")
        return result

    if y.size == 0:
        warnings.append("Decoded audio is empty.")
        return result

    result.duration_seconds = round(float(len(y) / sr), 3)
    result.sample_rate = int(sr)

    rms = librosa.feature.rms(y=y)[0]
    result.rms_mean = round(float(np.mean(rms)), 6)
    result.rms_std = round(float(np.std(rms)), 6)
    peak = float(np.max(np.abs(y)))
    result.peak_amplitude = round(peak, 6)

    # Crest-factor style dynamic range approximation (peak over mean RMS).
    if result.rms_mean and result.rms_mean > 0 and peak > 0:
        result.dynamic_range_db = round(
            20.0 * float(np.log10(peak / result.rms_mean)), 2
        )

    try:
        result.spectral_centroid_mean = round(
            float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))), 2
        )
        result.spectral_bandwidth_mean = round(
            float(np.mean(librosa.feature.spectral_bandwidth(y=y, sr=sr))), 2
        )
        result.spectral_rolloff_mean = round(
            float(np.mean(librosa.feature.spectral_rolloff(y=y, sr=sr))), 2
        )
        result.zero_crossing_rate_mean = round(
            float(np.mean(librosa.feature.zero_crossing_rate(y=y))), 6
        )
        result.onset_strength_mean = round(
            float(np.mean(librosa.onset.onset_strength(y=y, sr=sr))), 4
        )
    except Exception as exc:
        warnings.append(f"Some spectral descriptors failed: {exc}")

    result.estimated_tempo = _estimate_tempo(y, sr)
    if result.estimated_tempo is None:
        warnings.append("Tempo estimation was not possible for this file.")

    if PYLOUDNORM_AVAILABLE and result.duration_seconds and result.duration_seconds >= 0.5:
        try:
            meter = pyloudnorm.Meter(sr)
            loudness = meter.integrated_loudness(y.astype(np.float64))
            if np.isfinite(loudness):
                result.integrated_loudness_lufs = round(float(loudness), 2)
        except Exception as exc:
            warnings.append(f"Integrated loudness (pyloudnorm) failed: {exc}")
    elif not PYLOUDNORM_AVAILABLE:
        warnings.append(
            "pyloudnorm not installed; integrated loudness (LUFS) not computed."
        )

    return result
