"""
diagnose_b1.py
==============
Run this BEFORE task_b1_constrained.py to verify the data pipeline is healthy.
    python diagnose_b1.py

Expected output:
  NORMALISATION CHECK: PASS   (x_std of non-padded frames ≈ 1.00)
  Loss drops from ~2.30 toward ~2.00 within 20 steps

WHY x_batch.std() ≠ 1.0 (this is expected, not a bug)
------------------------------------------------------
FSDD recordings average ≈ 44 frames at 100 fps (HOP=80, SR=8000) out of
MAX_LEN=100.  After normalisation each real frame has std≈1, but ~56% of
batch entries are zero-padded (value 0 ≈ normalised mean).  The global
batch std is therefore sqrt(0.44) ≈ 0.66, NOT the per-feature normalised
std.  This script masks out the pre-padded zeros and measures the REAL
frame std, which should be ≈ 1.00.

WHY pre-padding (not post-padding)
-----------------------------------
With post-padding, the RNN's final hidden state h_T is contaminated by
~56 zero-input steps applied AFTER the real audio ends.  With pre-padding
(zeros first, audio last) the final state reflects the actual content →
the model can learn to classify digits.
"""
import sys
import torch
import torch.nn as nn
import config
from utils.data_loader import build_loaders
from utils.data_preprocessing import compute_stats, extract_features

N_MFCC = 13

# ── 1. Data sanity check ────────────────────────────────────────────────────

print("=" * 60)
print("STEP 1: Data sanity check  (N_MFCC=13)")
print("=" * 60)

train_loader, val_loader, test_loader, feature_dim = build_loaders(n_mfcc=N_MFCC)

print(f"feature_dim : {feature_dim}  (expected 39 = 3*{N_MFCC})")

x_batch, y_batch = next(iter(train_loader))
print(f"x shape     : {x_batch.shape}  (expected B=64, T=100, F=39)")
print(f"y shape     : {y_batch.shape}")
print(f"y classes   : {sorted(y_batch.unique().tolist())}")
print(f"class balance: {[(y_batch==i).sum().item() for i in range(10)]}")

# ── Global batch std (diluted by ~56% zero-padded frames — expected ~0.66) ──
x_mean_global = x_batch.mean().item()
x_std_global  = x_batch.std().item()
print()
print(f"x mean (global, all frames)    : {x_mean_global:.4f}  (expected ~0)")
print(f"x std  (global, all frames)    : {x_std_global:.4f}  (expected ~0.66 due to zero-padding)")

# ── Non-padded frames only (detect pre-pad leading zeros via abs-sum mask) ──
# After normalisation each feature has mean≈0; a genuine all-zero frame means
# it is a padding frame.  Using a small epsilon handles floating-point noise.
mask   = x_batch.abs().sum(dim=-1) > 1e-7   # (B, T) bool
x_real = x_batch[mask]                       # (N_real, F=39)

n = N_MFCC
x_std_all    = x_real.std().item()
x_std_mfcc   = x_real[:, :n].std().item()
x_std_delta  = x_real[:, n:2*n].std().item()
x_std_delta2 = x_real[:, 2*n:].std().item()

real_frac = mask.float().mean().item()
print(f"real frame fraction in batch   : {real_frac:.4f}  (expected ~0.44)")
print()
print(f"x std  (non-padded, all 39 F)  : {x_std_all:.4f}   <- normalisation check")
print(f"x std  (non-padded, MFCC  0-12): {x_std_mfcc:.4f}")
print(f"x std  (non-padded, delta13-25): {x_std_delta:.4f}")
print(f"x std  (non-padded, dd   26-38): {x_std_delta2:.4f}")

# ── Per-feature std vector (from compute_stats on training files) ────────────
# Re-use first batch's file paths as a proxy (or load directly via loader internals)
# Simplest: inspect the dataset object stored in the loader
train_ds  = train_loader.dataset
std_vec   = train_ds.std           # numpy array shape (39,) stored by SpokenDigitDataset
print()
print(f"compute_stats std vector: "
      f"min={std_vec.min():.4f}  max={std_vec.max():.4f}  mean={std_vec.mean():.4f}")
if std_vec.min() < 1e-3:
    print(f"  WARNING: near-zero std entries detected — "
          f"{(std_vec < 1e-3).sum()} features have std < 1e-3")
else:
    print("  All per-feature stds look healthy (no near-zero entries).")

# ── PASS / FAIL ──────────────────────────────────────────────────────────────
print()
if 0.9 < x_std_all < 1.1:
    print(f"NORMALISATION CHECK: PASS  ({x_std_all:.4f} in [0.9, 1.1])")
else:
    print(f"NORMALISATION CHECK: FAIL  ({x_std_all:.4f} not in [0.9, 1.1])")
    print("  Check utils/data_preprocessing.py — "
          "normalisation or padding order may be wrong.")
    sys.exit(1)


# ── 2. Gradient flow test ───────────────────────────────────────────────────

print()
print("=" * 60)
print("STEP 2: Gradient flow test  (ConstrainedMGU, the actual model)")
print("=" * 60)

# Import the real B1 student model so we test the actual architecture
from task_b1_constrained import ConstrainedMGU

model     = ConstrainedMGU().to("cpu")
criterion = nn.CrossEntropyLoss()

model.train()
logits = model(x_batch)
loss   = criterion(logits, y_batch)
loss.backward()

print(f"Loss on first batch : {loss.item():.4f}  "
      f"(random baseline ≈ {torch.log(torch.tensor(10.0)):.4f})")
print(f"Logits range        : [{logits.min().item():.3f}, {logits.max().item():.3f}]")
print(f"Predicted classes   : {sorted(logits.argmax(1).unique().tolist())}")
print()
print("Gradient norms per layer:")
any_dead = False
for name, param in model.named_parameters():
    if param.grad is not None:
        gnorm  = param.grad.norm().item()
        dead   = gnorm < 1e-6
        flag   = "  << DEAD" if dead else ""
        if dead:
            any_dead = True
        print(f"  {name:<40} grad_norm={gnorm:.6f}{flag}")

if any_dead:
    print("WARNING: dead gradients detected — check architecture.")
else:
    print("All layers have healthy gradients.")


# ── 3. 20-step loss trajectory ──────────────────────────────────────────────

print()
print("=" * 60)
print("STEP 3: 20-step loss trajectory  (should drop from ~2.30 by step 10)")
print("=" * 60)

model = ConstrainedMGU().to("cpu")
opt   = torch.optim.Adam(model.parameters(), lr=1e-3)
model.train()

losses = []
for step, (x, y) in enumerate(train_loader):
    if step >= 20:
        break
    opt.zero_grad()
    out  = model(x)
    loss = criterion(out, y)
    loss.backward()
    nn.utils.clip_grad_norm_(model.parameters(), 1.0)
    opt.step()
    with torch.no_grad():
        acc = (model(x).argmax(1) == y).float().mean().item()
    losses.append(loss.item())
    print(f"  step {step+1:02d}: loss={loss.item():.4f}  acc={acc:.3f}")

print()
drop = losses[0] - losses[-1]
if losses[-1] < losses[0] and losses[9] < losses[0]:
    print(f"LOSS TRAJECTORY: PASS  (dropped {drop:.4f} over 20 steps)")
else:
    print(f"LOSS TRAJECTORY: FAIL  "
          f"(start={losses[0]:.4f}, step10={losses[9]:.4f}, end={losses[-1]:.4f})")
    print("  If loss does not drop, the problem is in the data pipeline.")
    print("  If loss drops here but not in training, check the training loop.")
