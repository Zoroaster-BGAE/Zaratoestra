"""
diagnose_b1.py
==============
Run this BEFORE task_b1_constrained.py to understand what's happening.
    python diagnose_b1.py
"""
import torch
import torch.nn as nn
import config

# ── 1. Check what features actually look like with N_MFCC=13 ───────────────
# N_MFCC=13 passed explicitly below
from utils.data_loader import build_loaders

print("=" * 55)
print("STEP 1: Data sanity check")
print("=" * 55)
train_loader, val_loader, test_loader, feature_dim = build_loaders(n_mfcc=13)
print(f"feature_dim : {feature_dim}  (expected 39 = 3*13)")

x_batch, y_batch = next(iter(train_loader))
print(f"x shape     : {x_batch.shape}  (expected B=64, T=100, F=39)")
print(f"y shape     : {y_batch.shape}")
print(f"x mean      : {x_batch.mean():.4f}  (expected ~0 after normalisation)")
print(f"x std       : {x_batch.std():.4f}   (expected ~1 after normalisation)")
print(f"y classes   : {sorted(y_batch.unique().tolist())}")
print(f"class balance: {[(y_batch==i).sum().item() for i in range(10)]}")

# ── 2. Check gradient flow through a single batch ─────────────────────────
print()
print("=" * 55)
print("STEP 2: Gradient flow test")
print("=" * 55)

class ConstrainedGRU(nn.Module):
    def __init__(self, input_size, proj_dim=32, hidden_size=40, num_classes=10):
        super().__init__()
        self.proj = nn.Linear(input_size, proj_dim)
        self.norm = nn.LayerNorm(proj_dim)
        self.act  = nn.ReLU()
        self.gru  = nn.GRU(proj_dim, hidden_size, num_layers=1, batch_first=True)
        self.fc   = nn.Linear(hidden_size, num_classes)

    def forward(self, x):
        B, T, F = x.shape
        x = self.act(self.norm(self.proj(x.view(B * T, F))))
        x = x.view(B, T, -1)
        _, h_n = self.gru(x)
        return self.fc(h_n[-1])

model = ConstrainedGRU(feature_dim)
criterion = nn.CrossEntropyLoss()

model.train()
logits = model(x_batch)
loss = criterion(logits, y_batch)
loss.backward()

print(f"Loss on first batch : {loss.item():.4f}  (random = {torch.log(torch.tensor(10.)):.4f})")
print(f"Logits range        : [{logits.min().item():.3f}, {logits.max().item():.3f}]")
print(f"Predicted classes   : {logits.argmax(1).unique().tolist()}")
print()
print("Gradient norms per layer:")
for name, param in model.named_parameters():
    if param.grad is not None:
        gnorm = param.grad.norm().item()
        print(f"  {name:<30} grad_norm={gnorm:.6f}  {'<< DEAD' if gnorm < 1e-6 else ''}")

# ── 3. Simulate 20 training steps and watch loss ──────────────────────────
print()
print("=" * 55)
print("STEP 3: 20-step loss trajectory (should drop from ~2.30)")
print("=" * 55)
model = ConstrainedGRU(feature_dim)
opt   = torch.optim.Adam(model.parameters(), lr=1e-3)
model.train()

for step, (x, y) in enumerate(train_loader):
    if step >= 20:
        break
    opt.zero_grad()
    loss = criterion(model(x), y)
    loss.backward()
    opt.step()
    acc = (model(x).argmax(1) == y).float().mean().item()
    print(f"  step {step+1:02d}: loss={loss.item():.4f}  acc={acc:.3f}")

print()
print("If loss is NOT dropping by step 10, the problem is in the data pipeline.")
print("If loss drops here but not in training, the problem is in the training loop.")
