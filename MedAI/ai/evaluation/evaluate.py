"""
Evaluate the configured model (pretrained TorchXRayVision OR a locally trained checkpoint) on a
labelled manifest, using exactly the same inference path the application uses.

    backend\\.venv\\Scripts\\python -m ai.evaluation.evaluate ^
        --csv ai\\data\\manifest.csv --images-root ai\\data --split test ^
        --config ai\\model_config.json --report ai\\runs\\eval-report.json

Label columns in the manifest are matched to model labels by name (e.g. "Effusion").
Images in the manifest's training split must not be used to report final performance.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ai.evaluation.metrics import per_label_report
from ai.inference.service import XrayModelService
from ai.preprocessing.xray import ImageNotSuitable, open_image
from ai.training.dataset import load_manifest


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", type=Path, required=True)
    p.add_argument("--images-root", type=Path, required=True)
    p.add_argument("--config", type=Path, default=Path("ai/model_config.json"))
    p.add_argument("--split", default="test", choices=["train", "val", "test", "all"])
    p.add_argument("--threshold", type=float, default=0.5)
    p.add_argument("--report", type=Path, default=None)
    args = p.parse_args(argv)

    service = XrayModelService(args.config)
    status = service.status()
    if not status.available:
        raise SystemExit(f"Model not available: {status.reason}")

    with open(args.csv, newline="", encoding="utf-8") as f:
        columns = set(csv.DictReader(f).fieldnames or [])
    labels = [l for l in status.labels if l in columns]
    if not labels:
        raise SystemExit(f"No manifest columns match model labels {status.labels}")
    samples = [s for s in load_manifest(args.csv, args.images_root, labels) if args.split in ("all", s.split)]
    print(f"Evaluating {status.model_name} {status.model_version} on {len(samples)} images, labels: {labels}")

    y_true, scores, skipped = [], [], 0
    for s in samples:
        try:
            pred = service.predict(open_image(s.path.read_bytes()))
        except ImageNotSuitable as exc:
            skipped += 1
            print(f"  skipped {s.path.name}: {exc}")
            continue
        by_label = {f["label"]: f["score"] for f in pred.findings}
        y_true.append(s.labels)
        scores.append([by_label[l] for l in labels])
    if not y_true:
        raise SystemExit("No images could be evaluated.")

    report = per_label_report(np.array(y_true), np.array(scores), labels, args.threshold)
    out = {
        "model": {"name": status.model_name, "version": status.model_version, "weights_sha256": status.weights_sha256,
                  "score_type": status.score_type},
        "manifest": str(args.csv), "split": args.split, "evaluated": len(y_true), "skipped": skipped,
        "threshold": args.threshold, "created_at": datetime.now(timezone.utc).isoformat(), "metrics": report,
    }
    for label in labels:
        r = report[label]
        auc = "n/a" if r["auroc"] is None else f"{r['auroc']:.3f}"
        print(f"  {label:28s} AUROC={auc}  n={r['n']}  positives={r['positives']}")
    print(f"  mean AUROC: {report['_mean_auroc']}")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(out, indent=2))
        print(f"Report written to {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
