"""
Train a DenseNet-121 (1-channel) multi-label chest X-ray classifier on a dataset you are licensed to use.

    backend\\.venv\\Scripts\\python -m ai.training.train ^
        --csv ai\\data\\manifest.csv --images-root ai\\data ^
        --labels Atelectasis,Cardiomegaly,Effusion,Pneumonia ^
        --epochs 10 --out ai\\checkpoints\\medai-densenet121-v1.pt ^
        --dataset-description "NIH ChestX-ray14 subset (licence/terms), downloaded YYYY-MM-DD"

Run from the MedAI folder. The best checkpoint (by validation mean AUROC) is saved as a plain dict
(state_dict + metadata) that the inference service loads with torch.load(weights_only=True).
A checkpoint is NOT clinically validated just because it trains: evaluate it on the held-out
test split (ai/evaluation/evaluate.py) and document the results in docs/AI_MODEL_PROVENANCE.md.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ai.evaluation.metrics import per_label_report
from ai.inference.models import build_densenet121_grayscale
from ai.preprocessing.xray import PreprocessConfig
from ai.training.dataset import XrayDataset, load_manifest


def masked_bce(logits, targets):
    import torch
    mask = ~torch.isnan(targets)
    if not mask.any():
        return logits.sum() * 0
    return torch.nn.functional.binary_cross_entropy_with_logits(logits[mask], targets[mask])


def predict(model, loader, device):
    import torch
    model.eval()
    ys, ps = [], []
    with torch.inference_mode():
        for x, y in loader:
            ps.append(torch.sigmoid(model(x.to(device))).cpu().numpy())
            ys.append(y.numpy())
    return np.concatenate(ys), np.concatenate(ps)


def main(argv=None) -> int:
    import torch
    from torch.utils.data import DataLoader

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", type=Path, required=True)
    p.add_argument("--images-root", type=Path, required=True)
    p.add_argument("--labels", required=True, help="Comma-separated label columns")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--image-size", type=int, default=224)
    p.add_argument("--workers", type=int, default=0)
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--model-version", default=None)
    p.add_argument("--dataset-description", required=True,
                   help="Name, licence and date of the dataset (stored in the checkpoint for provenance)")
    args = p.parse_args(argv)

    torch.manual_seed(args.seed)
    labels = [l.strip() for l in args.labels.split(",") if l.strip()]
    pre = PreprocessConfig(image_size=args.image_size)
    samples = load_manifest(args.csv, args.images_root, labels)
    by_split = {s: [x for x in samples if x.split == s] for s in ("train", "val", "test")}
    print({k: len(v) for k, v in by_split.items()})
    if not by_split["train"] or not by_split["val"]:
        raise SystemExit("Need at least one training and one validation image.")

    train_loader = DataLoader(XrayDataset(by_split["train"], pre, train=True, seed=args.seed),
                              batch_size=args.batch_size, shuffle=True, num_workers=args.workers)
    val_loader = DataLoader(XrayDataset(by_split["val"], pre), batch_size=args.batch_size, num_workers=args.workers)

    model = build_densenet121_grayscale(len(labels)).to(args.device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-5)
    best, history = -math.inf, []
    args.out.parent.mkdir(parents=True, exist_ok=True)

    for epoch in range(1, args.epochs + 1):
        model.train()
        t0, total, n = time.time(), 0.0, 0
        for x, y in train_loader:
            x, y = x.to(args.device), y.to(args.device)
            loss = masked_bce(model(x), y)
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += float(loss.detach()) * len(x)
            n += len(x)
        y_val, p_val = predict(model, val_loader, args.device)
        report = per_label_report(y_val, p_val, labels)
        mean_auc = report["_mean_auroc"]
        history.append({"epoch": epoch, "train_loss": total / max(n, 1), "val_mean_auroc": mean_auc})
        print(f"epoch {epoch}: train_loss={total / max(n, 1):.4f} val_mean_auroc={mean_auc} ({time.time() - t0:.0f}s)")

        score = mean_auc if mean_auc is not None else -total
        if score > best:
            best = score
            torch.save({
                "architecture": "densenet121_grayscale",
                "labels": labels,
                "state_dict": {k: v.detach().cpu() for k, v in model.state_dict().items()},
                "preprocess": pre.to_dict(),
                "model_name": "MedAI DenseNet-121 (locally trained)",
                "model_version": args.model_version or args.out.stem,
                "trained_on": args.dataset_description,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "torch_version": str(torch.__version__),
                "epoch": epoch,
                "val_report": json.loads(json.dumps(report)),
                "split_counts": {k: len(v) for k, v in by_split.items()},
                "seed": args.seed,
            }, args.out)
            print(f"  saved best checkpoint -> {args.out}")

    (args.out.with_suffix(".history.json")).write_text(json.dumps(history, indent=2))
    print("Done. Next: evaluate on the held-out test split with ai/evaluation/evaluate.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
