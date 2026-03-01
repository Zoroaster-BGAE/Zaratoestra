"""
utils/data_preprocessing.py
============================
Feature extraction and normalisation utilities.
All functions accept explicit parameters — no global config reads.
"""

import numpy as np
import librosa


def extract_features(path: str, n_mfcc: int, sample_rate: int,
                     n_fft: int, hop_length: int) -> np.ndarray:
    """
    Load a .wav file and return MFCC + delta + delta-delta.

    Returns
    -------
    np.ndarray, shape (T, 3 * n_mfcc)
    """
    y, _ = librosa.load(path, sr=sample_rate, mono=True)
    mfcc   = librosa.feature.mfcc(y=y, sr=sample_rate, n_mfcc=n_mfcc,
                                   n_fft=n_fft, hop_length=hop_length)
    delta  = librosa.feature.delta(mfcc)
    delta2 = librosa.feature.delta(mfcc, order=2)
    return np.concatenate([mfcc, delta, delta2], axis=0).T  # (T, 3*n_mfcc)


def pad_or_truncate(feat: np.ndarray, max_len: int) -> np.ndarray:
    T, F = feat.shape
    if T >= max_len:
        return feat[:max_len]
    return np.concatenate([feat, np.zeros((max_len - T, F), dtype=feat.dtype)], axis=0)


def compute_stats(file_paths: list, n_mfcc: int, sample_rate: int,
                  n_fft: int, hop_length: int) -> tuple:
    """
    Compute per-feature mean/std over file_paths (training split only).
    Concatenates RAW frames only (no padding) so stats are not skewed
    by zero-padded frames.
    """
    all_feats = [extract_features(p, n_mfcc, sample_rate, n_fft, hop_length)
                 for p in file_paths]
    # Concatenate variable-length arrays BEFORE padding — no zeros included
    all_feats = np.concatenate(all_feats, axis=0)
    return all_feats.mean(axis=0), all_feats.std(axis=0)
