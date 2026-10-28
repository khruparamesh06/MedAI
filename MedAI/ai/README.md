# MedAI AI module

This package is independent of the web API: the backend imports `ai.inference.service`, and the
same preprocessing is used for inference, training and evaluation.

```
ai/
├── model_config.default.json   shipped config: model DISABLED
├── model_config.json           local config written by fetch_pretrained.py (git-ignored)
├── preprocessing/xray.py       decoding, suitability checks, TorchXRayVision-compatible preprocessing
├── inference/
│   ├── service.py              XrayModelService: status(), predict()  — never fabricates output
│   ├── models.py               model builders + pinned label list / operating thresholds
│   └── fetch_pretrained.py     safe download + verification + conversion of pretrained weights
├── training/
│   ├── dataset.py              CSV manifest interface, patient-level train/val/test split
│   └── train.py                DenseNet-121 training with masked BCE, best-checkpoint saving
├── evaluation/
│   ├── metrics.py              AUROC (rank-based), sensitivity/specificity/PPV
│   └── evaluate.py             evaluates the *configured* model through the real inference path
└── weights/                    downloaded/converted weights (git-ignored, never redistributed here)
```

## Model states

`XrayModelService.status()` returns one of:

| state | meaning | UI |
|-------|---------|----|
| `not_configured` | config disabled, weights file missing, or PyTorch not installed | “Model not configured”; analysis endpoint returns **503** and stores nothing |
| `error` | checksum mismatch, unsupported backend/architecture, or load failure | same as above, with the reason |
| `ready` | genuine weights loaded and verified | “Run AI analysis” available |

## Option 1 — pretrained TorchXRayVision DenseNet-121 (recommended)

```powershell
backend\.venv\Scripts\python -m pip install -r backend\requirements-ai.txt
backend\.venv\Scripts\python ai\inference\fetch_pretrained.py
```

What the script does (see the source for details):
1. Downloads `nih-pc-chex-mimic_ch-google-openi-kaggle-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt`
   from the official release `https://github.com/mlmed/torchxrayvision/releases/download/v1/`.
2. Verifies SHA-256 `56524913dd16a906422e8d8b66a7a5c46be1d82eb7ac012d8103776f1aa68899`.
3. Statically scans the pickle and refuses anything outside an allowlist of PyTorch /
   TorchXRayVision layer classes (the upstream file is a full pickled module, and unpickling
   untrusted files can execute code).
4. Loads it with a restricted unpickler, saves a plain `state_dict`, and records its SHA-256 in
   `ai/model_config.json`. The app then loads it with `torch.load(weights_only=True)` and refuses to
   load if the checksum changes.

Supported labels (18): Atelectasis, Consolidation, Infiltration, Pneumothorax, Edema, Emphysema,
Fibrosis, Effusion, Pneumonia, Pleural_Thickening, Cardiomegaly, Nodule, Mass, Hernia,
Lung Lesion, Fracture, Lung Opacity, Enlarged Cardiomediastinum.

**Score meaning:** the model's sigmoid output is rescaled (TorchXRayVision `op_norm`) so that 0.5
equals the per-label operating threshold published with the weights. Scores are *not* calibrated
probabilities. See [../docs/AI_MODEL_PROVENANCE.md](../docs/AI_MODEL_PROVENANCE.md).

**GPU (optional):** install a CUDA build of PyTorch instead of the CPU one, e.g.
`pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128`, and set
`"device": "cuda"` in `ai/model_config.json`. Measured on the build machine (laptop CPU, PyTorch CPU
build): about 1.3–1.7 s per 1024×1024 image including preprocessing, ~4 s for the first request.

## Option 2 — train your own model

1. **Obtain a dataset you are permitted to use.** Examples (check each licence and terms yourself;
   some require registration or credentialed access and forbid redistribution):
   - NIH ChestX-ray14 — https://nihcc.app.box.com/v/ChestXray-NIHCC (publicly released by the NIH Clinical Center; read its terms and cite the paper)
   - RSNA Pneumonia Detection Challenge (Kaggle competition terms)
   - CheXpert (Stanford research-use agreement), MIMIC-CXR (PhysioNet credentialed access)
   Store data under `ai/data/` (git-ignored). Never put real patient data in the repository.
2. **Create a manifest CSV** (`ai/data/manifest.csv`):
   ```csv
   path,patient_id,Atelectasis,Cardiomegaly,Effusion,Pneumonia
   images/00000001_000.png,1,0,1,0,0
   images/00000001_001.png,1,,1,1,0
   ```
   `1` = present, `0` = absent, empty = unknown (masked). Images of one patient always land in the
   same split (deterministic hash, 70/15/15) unless you add a `split` column.
3. **Train** (from the MedAI folder):
   ```powershell
   backend\.venv\Scripts\python -m ai.training.train --csv ai\data\manifest.csv --images-root ai\data `
     --labels Atelectasis,Cardiomegaly,Effusion,Pneumonia --epochs 10 `
     --out ai\checkpoints\medai-densenet121-v1.pt `
     --dataset-description "NIH ChestX-ray14 subset (terms: <licence>), downloaded YYYY-MM-DD"
   ```
4. **Configure it** — `ai/model_config.json` (`weights_sha256` is **required**; the service refuses to
   load weights without a pinned checksum):
   ```json
   { "enabled": true, "backend": "checkpoint",
     "weights_path": "checkpoints/medai-densenet121-v1.pt",
     "weights_sha256": "<output of: certutil -hashfile ai\\checkpoints\\medai-densenet121-v1.pt SHA256>",
     "device": "cpu" }
   ```
5. **Evaluate on the held-out test split** and record the results in the provenance document:
   ```powershell
   backend\.venv\Scripts\python -m ai.evaluation.evaluate --csv ai\data\manifest.csv --images-root ai\data `
     --split test --config ai\model_config.json --report ai\runs\eval-test.json
   ```
   The same command evaluates the pretrained model (label columns are matched by name). Note that
   the pretrained model was trained on NIH/CheXpert/MIMIC/etc., so evaluating it on those same
   public datasets overestimates real-world performance.

## Tests

`backend/app/tests/test_xrays_ai.py` and `test_ai_pipeline.py` cover: not-configured behaviour,
missing weights, checksum mismatch, preprocessing, suitability checks, metrics, manifest safety,
a checkpoint save/load round trip (tiny synthetic data, weights discarded), and — when the genuine
weights are installed — real inference through the API.
