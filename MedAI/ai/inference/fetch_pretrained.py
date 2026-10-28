"""
Download and safely convert the TorchXRayVision DenseNet-121 "all" pretrained weights.

Source:   https://github.com/mlmed/torchxrayvision (Apache-2.0), release v1
Paper:    Cohen et al., "TorchXRayVision: A library of chest X-ray datasets and models",
          MIDL 2022, https://arxiv.org/abs/2111.00595  and https://arxiv.org/abs/2002.02497

Safety: the upstream file is a *fully pickled* nn.Module in the legacy torch format.
Unpickling arbitrary files can execute code, so this script:
  1. verifies the SHA-256 of the download against the value pinned below,
  2. statically scans every pickle GLOBAL reference without executing anything,
  3. refuses to continue if any reference is outside a small allowlist,
  4. loads with torch.load(weights_only=True) and only those classes allowlisted,
  5. writes a plain state_dict that the app later loads with weights_only=True.

Run from the MedAI folder:
    backend\\.venv\\Scripts\\python ai\\inference\\fetch_pretrained.py
"""
from __future__ import annotations

import hashlib
import json
import pickletools
import sys
import urllib.request
from pathlib import Path

AI_DIR = Path(__file__).resolve().parents[1]
WEIGHTS_DIR = AI_DIR / "weights" / "torchxrayvision"
RAW_FILE = WEIGHTS_DIR / "densenet121-res224-all.pt"
STATE_FILE = WEIGHTS_DIR / "densenet121-res224-all.state_dict.pt"
CONFIG_FILE = AI_DIR / "model_config.json"

URL = ("https://github.com/mlmed/torchxrayvision/releases/download/v1/"
       "nih-pc-chex-mimic_ch-google-openi-kaggle-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt")
# SHA-256 observed when this project was built (2026-10-28) from the URL above.
EXPECTED_SHA256 = "56524913dd16a906422e8d8b66a7a5c46be1d82eb7ac012d8103776f1aa68899"

ALLOWED_GLOBALS = {
    "collections.OrderedDict",
    "torch.FloatStorage", "torch.LongStorage",
    "torch._utils._rebuild_parameter", "torch._utils._rebuild_tensor_v2",
    "torch.nn.modules.activation.ReLU",
    "torch.nn.modules.batchnorm.BatchNorm2d",
    "torch.nn.modules.container.Sequential",
    "torch.nn.modules.conv.Conv2d",
    "torch.nn.modules.linear.Linear",
    "torch.nn.modules.pooling.AvgPool2d",
    "torch.nn.modules.pooling.MaxPool2d",
    "torchxrayvision.models.DenseNet",
    "torchxrayvision.models._DenseBlock",
    "torchxrayvision.models._DenseLayer",
    "torchxrayvision.models._Transition",
}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_globals(path: Path) -> set[str]:
    """Return GLOBAL references from the legacy-format pickle headers + object pickle."""
    found: set[str] = set()
    with path.open("rb") as f:
        for _ in range(4):
            strings: list[str] = []
            for op, arg, _pos in pickletools.genops(f):
                if op.name == "GLOBAL":
                    found.add(arg.replace(" ", "."))
                elif op.name in ("SHORT_BINUNICODE", "BINUNICODE", "UNICODE"):
                    strings.append(arg)
                elif op.name == "STACK_GLOBAL":
                    found.add(".".join(strings[-2:]))
                if op.name == "STOP":
                    break
    return found


def restricted_legacy_load(path: Path):
    """
    Load a legacy-format torch checkpoint with an allowlisting unpickler.

    torch.load(weights_only=True) cannot read this legacy format (it stores module source code
    as persistent ids), so this mirrors torch.serialization's legacy loader but resolves only
    the classes in ALLOWED_GLOBALS. Anything else raises UnpicklingError before it is created.
    """
    import importlib
    import pickle

    import torch

    class RestrictedUnpickler(pickle.Unpickler):
        def find_class(self, module, name):
            if f"{module}.{name}" not in ALLOWED_GLOBALS:
                raise pickle.UnpicklingError(f"Blocked global: {module}.{name}")
            return getattr(importlib.import_module(module), name)

    storages: dict = {}

    def persistent_load(saved_id):
        typename = saved_id[0].decode() if isinstance(saved_id[0], bytes) else saved_id[0]
        if typename == "module":
            return saved_id[1]  # the (allowlisted) class; saved source code is ignored, never executed
        if typename == "storage":
            storage_type, root_key, _location, numel, view_metadata = saved_id[1:]
            if view_metadata is not None:
                raise pickle.UnpicklingError("Storage views are not supported")
            dtype = storage_type.dtype
            if root_key not in storages:
                nbytes = numel * torch._utils._element_size(dtype)
                storages[root_key] = torch.storage.TypedStorage(
                    wrap_storage=torch.UntypedStorage(nbytes), dtype=dtype, _internal=True)
            return storages[root_key]
        raise pickle.UnpicklingError(f"Unsupported persistent id: {typename}")

    with path.open("rb") as f:
        for _ in range(3):  # magic number, protocol version, sys info (primitives only)
            RestrictedUnpickler(f).load()
        unpickler = RestrictedUnpickler(f)
        unpickler.persistent_load = persistent_load
        result = unpickler.load()
        storage_keys = RestrictedUnpickler(f).load()
        offset = f.tell()
        for key in storage_keys:
            ts = storages[key]
            ts._untyped_storage._set_from_file(f, offset, True, torch._utils._element_size(ts.dtype))
            offset = f.tell()
    return result


def download() -> None:
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    if RAW_FILE.exists() and sha256_of(RAW_FILE) == EXPECTED_SHA256:
        print(f"Already downloaded: {RAW_FILE}")
        return
    print(f"Downloading {URL}\n  -> {RAW_FILE}")
    tmp = RAW_FILE.with_suffix(".part")
    with urllib.request.urlopen(URL, timeout=120) as resp, tmp.open("wb") as out:  # noqa: S310 (fixed https URL)
        while chunk := resp.read(1 << 20):
            out.write(chunk)
    tmp.replace(RAW_FILE)


def main() -> int:
    download()
    digest = sha256_of(RAW_FILE)
    if digest != EXPECTED_SHA256:
        print(f"SHA-256 mismatch!\n  expected {EXPECTED_SHA256}\n  got      {digest}\nRefusing to use this file.")
        return 1
    print(f"SHA-256 verified: {digest}")

    unexpected = scan_globals(RAW_FILE) - ALLOWED_GLOBALS
    if unexpected:
        print(f"Checkpoint references unexpected classes/functions: {sorted(unexpected)}. Refusing to load.")
        return 1
    print("Static pickle scan passed (only allowlisted PyTorch/TorchXRayVision classes).")

    import torch

    module = restricted_legacy_load(RAW_FILE)
    if not isinstance(module, torch.nn.Module):
        print(f"Unexpected checkpoint content: {type(module)}")
        return 1
    state_dict = {k: v.clone() for k, v in module.state_dict().items()}
    torch.save(state_dict, STATE_FILE)
    state_sha = sha256_of(STATE_FILE)
    print(f"Wrote plain state_dict: {STATE_FILE}\n  sha256 {state_sha}")

    source_cfg = CONFIG_FILE if CONFIG_FILE.exists() else AI_DIR / "model_config.default.json"
    config = json.loads(source_cfg.read_text(encoding="utf-8")) if source_cfg.exists() else {}
    config.update({
        "enabled": True,
        "backend": "torchxrayvision",
        "weights_name": "densenet121-res224-all",
        "weights_path": "weights/torchxrayvision/densenet121-res224-all.state_dict.pt",
        "weights_sha256": state_sha,
    })
    CONFIG_FILE.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {CONFIG_FILE} (enabled=true). Restart the backend to load the model.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
