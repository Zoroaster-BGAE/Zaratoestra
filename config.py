"""
config.py
=========
Central configuration for all hyperparameters and paths.

Task A  ->  original unconstrained model  (hidden=128, layers=1)
Task B1 ->  memory-constrained model      (hidden=20,  layers=1, float32)
Task B2 ->  quantized model               (hidden=20,  layers=1, int8)
"""

import torch

# -- Paths ------------------------------------------------------------------
RECORDINGS_DIR  = "free-spoken-digit-dataset/recordings"
CHECKPOINT_PATH = "best_model.pt"
CHECKPOINT_B1   = "best_model_b1_constrained.pt"
CHECKPOINT_B2   = "best_model_b2_quantized.pt"

# -- Audio / Feature extraction ---------------------------------------------
SAMPLE_RATE = 8000   # FSDD recordings are 8 kHz
HOP_LENGTH  = 80     # ~10 ms per frame  ->  100 frames ~= 1 s
N_FFT       = 512
N_MFCC      = 40     # MFCC coefficients; total feature dim = 3 * N_MFCC = 120
MAX_LEN     = 100    # fixed sequence length (frames) after pad / truncate

# -- Model - Task A (baseline, unconstrained) -------------------------------
HIDDEN_SIZE = 128
NUM_LAYERS  = 1
DROPOUT     = 0.3
NUM_CLASSES = 10

# -- Model - Task B1 (36 kB memory constraint per layer) -------------------
# GRU param count formula:
#   weight_ih : 3 * H * I
#   weight_hh : 3 * H * H
#   bias_ih   : 3 * H
#   bias_hh   : 3 * H
#   Total     : 3 * H * (I + H + 2)
#
# 36 kB = 36,000 bytes / 4 bytes per float32 = 9,000 params max per layer
#
# Solving for H with I=120:
#   H=20 -> 3*20*(120+20+2) = 8,520 params -> 34,080 bytes  fits
#   H=21 -> 3*21*(120+21+2) = 9,009 params -> 36,036 bytes  exceeds limit
#
# Maximum allowed hidden_size is 20
HIDDEN_SIZE_B1 = 20
NUM_LAYERS_B1  = 1     # single layer keeps constraint simple to verify
DROPOUT_B1     = 0.1   # less dropout: smaller model needs all its capacity

# -- Training ---------------------------------------------------------------
BATCH_SIZE = 64
LR         = 1e-3
EPOCHS     = 50       # more epochs to compensate for smaller model capacity
DEVICE     = "cuda" if torch.cuda.is_available() else "cpu"
