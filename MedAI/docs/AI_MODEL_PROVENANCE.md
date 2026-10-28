# AI model provenance, intended use and limitations

## Model in use (when enabled)

| Item | Value |
|------|-------|
| Name | TorchXRayVision DenseNet-121, weights `densenet121-res224-all` |
| Library | `torchxrayvision` 1.5.7 (https://github.com/mlmed/torchxrayvision) |
| Code licence | Apache License 2.0 (verified from the repository `LICENSE` on 2026-10-28) |
| Weights URL | `https://github.com/mlmed/torchxrayvision/releases/download/v1/nih-pc-chex-mimic_ch-google-openi-kaggle-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt` |
| Upstream file SHA-256 | `56524913dd16a906422e8d8b66a7a5c46be1d82eb7ac012d8103776f1aa68899` (28,382,008 bytes) |
| Converted state_dict | written locally by `ai/inference/fetch_pretrained.py`; its SHA-256 is recorded in `ai/model_config.json` and stored with every analysis |
| Architecture | DenseNet-121, 1-channel input, 224×224, 18 sigmoid outputs |
| Training data (per upstream) | NIH ChestX-ray14, PadChest, CheXpert, MIMIC-CXR, Google (NIH labels), OpenI, RSNA/Kaggle |
| References | Cohen et al., *TorchXRayVision: A library of chest X-ray datasets and models*, MIDL 2022 (arXiv:2111.00595); Cohen et al., *On the limits of cross-domain generalization in automated X-ray prediction*, MIDL 2020 (arXiv:2002.02497) |

### Verification performed for this project
1. Source: official GitHub release of the library's maintainers, referenced from the library's own `model_urls`.
2. Integrity: SHA-256 recorded above and enforced by `fetch_pretrained.py`.
3. Safety: the upstream file is a legacy-format pickled `nn.Module`. A static scan of every pickle
   `GLOBAL` showed only `collections.OrderedDict`, `torch` storage/tensor rebuild helpers,
   `torch.nn` layer classes and `torchxrayvision.models` DenseNet classes. It is loaded with an
   allowlisting unpickler and converted to a plain `state_dict`, which the application loads with
   `torch.load(weights_only=True)`.
4. Architecture: the converted `state_dict` loads with `strict=True` into `xrv.models.DenseNet(num_classes=18, in_channels=1)`.
5. Function: real inference was executed in automated tests (structure only) and the end-to-end smoke test.

### Licensing caveat
The *code* is Apache-2.0. The *weights* were trained on datasets with differing terms (some
research-only or credentialed). The weights are therefore **not redistributed** in this repository
or ZIP; each installation downloads them from the upstream release. Check the dataset terms before
any commercial or clinical use.

## Preprocessing (must match training)
Grayscale decode (8/16-bit) → scale to [-1024, 1024] → centre-crop to square → resize to 224×224
with `skimage.transform.resize` (identical to `xrv.datasets.XRayCenterCrop` + `XRayResizer`).

## Output meaning
Each output is `op_norm(sigmoid(logit))`: values are rescaled so that **0.5 corresponds to the
per-label operating threshold** shipped with the weights. Consequently:
- scores are **not calibrated probabilities** and must not be read as "x % chance of disease";
- "above threshold" means only that the model's output exceeds its published operating point;
- scores are not comparable across labels as measures of likelihood or severity.

## Intended use (this project)
Education and demonstration of a decision-support workflow in which a qualified clinician
independently reviews every image. **Not** for diagnosis, triage, screening or treatment decisions.

## Known limitations
- Not validated by this project on any local population, scanner, or acquisition protocol.
  Published cross-dataset studies (Cohen et al. 2020) show substantial performance drops across sites.
- No out-of-distribution detection: the model outputs scores for *any* grayscale image, including
  non-chest images. MedAI only rejects colour photographs and very small images.
- Trained mainly on frontal (PA/AP) adult radiographs; lateral views and paediatric images are out of scope.
- Labels in the training data were largely extracted automatically from radiology reports (noisy).
- **Severity is not estimated.** A higher score does not indicate a more severe condition.
- Input is an exported PNG/JPEG; windowing/bit-depth loss from DICOM export can change outputs.

## Changing the model
Any new model (including one trained with `ai/training/train.py`) must be documented here with:
dataset name/version/licence, split method, test-set metrics from `ai/evaluation/evaluate.py`,
checkpoint SHA-256, preprocessing, and known failure modes — before it is enabled.
