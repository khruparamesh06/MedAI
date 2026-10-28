"""Model construction for each supported backend. PyTorch is imported lazily by callers."""
from __future__ import annotations

# Published metadata for TorchXRayVision weights (copied from torchxrayvision.models.model_urls so the
# label list and operating points are pinned in this repository and auditable).
XRV_LABELS_ALL = [
    "Atelectasis", "Consolidation", "Infiltration", "Pneumothorax", "Edema", "Emphysema", "Fibrosis",
    "Effusion", "Pneumonia", "Pleural_Thickening", "Cardiomegaly", "Nodule", "Mass", "Hernia",
    "Lung Lesion", "Fracture", "Lung Opacity", "Enlarged Cardiomediastinum",
]
XRV_OP_THRESHS_ALL = [
    0.07422872, 0.038290843, 0.09814756, 0.0098118475, 0.023601074, 0.0022490358, 0.010060724,
    0.103246614, 0.056810737, 0.026791653, 0.050318155, 0.023985857, 0.01939503, 0.042889766,
    0.053369623, 0.035975814, 0.20204692, 0.05015312,
]

# Human-readable display names. Underscored upstream labels are kept as the stored key.
DISPLAY_NAMES = {
    "Pleural_Thickening": "Pleural thickening",
    "Effusion": "Pleural effusion",
    "Lung Lesion": "Lung lesion",
    "Lung Opacity": "Lung opacity",
    "Enlarged Cardiomediastinum": "Enlarged cardiomediastinum",
}


def build_xrv_densenet(num_classes: int):
    import torchxrayvision as xrv
    return xrv.models.DenseNet(num_classes=num_classes, in_channels=1)


def build_densenet121_grayscale(num_classes: int):
    """torchvision DenseNet-121 adapted to 1-channel input; used by ai/training/train.py."""
    import torch
    import torchvision

    model = torchvision.models.densenet121(weights=None, num_classes=num_classes)
    model.features.conv0 = torch.nn.Conv2d(1, 64, kernel_size=7, stride=2, padding=3, bias=False)
    return model
