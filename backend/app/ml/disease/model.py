from __future__ import annotations

import torch
from torch import nn
from torchvision.models import (MobileNet_V3_Small_Weights, ResNet18_Weights,
                                mobilenet_v3_small, resnet18)

from app.ml.disease.config import CLASS_NAMES


def build_model(*, pretrained: bool = True, num_classes: int = len(CLASS_NAMES),
                architecture: str = "mobilenet_v3_small") -> nn.Module:
    if architecture == "mobilenet_v3_small":
        weights = MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
        model = mobilenet_v3_small(weights=weights)
        model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, num_classes)
        return model
    if architecture == "resnet18":
        weights = ResNet18_Weights.DEFAULT if pretrained else None
        model = resnet18(weights=weights)
        model.fc = nn.Linear(model.fc.in_features, num_classes)
        return model
    raise ValueError(f"unsupported architecture: {architecture}")


def freeze_backbone(model: nn.Module) -> None:
    for parameter in model.parameters():
        parameter.requires_grad = False
    head = model.classifier if hasattr(model, "classifier") else model.fc
    for parameter in head.parameters():
        parameter.requires_grad = True


def unfreeze_last_backbone_block(model: nn.Module) -> None:
    freeze_backbone(model)
    block = model.features[-1] if hasattr(model, "features") else model.layer4
    for parameter in block.parameters():
        parameter.requires_grad = True


def load_checkpoint(path, device: torch.device | str = "cpu") -> tuple[nn.Module, dict]:
    checkpoint = torch.load(path, map_location=device, weights_only=False)
    model = build_model(pretrained=False, num_classes=len(checkpoint["class_names"]),
                        architecture=checkpoint.get("architecture", "mobilenet_v3_small"))
    model.load_state_dict(checkpoint["state_dict"])
    model.to(device).eval()
    return model, checkpoint
