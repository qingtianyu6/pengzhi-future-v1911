from __future__ import annotations

import csv
from pathlib import Path
from typing import Callable

from PIL import Image
import torch
from torch.utils.data import Dataset
from torchvision import transforms

from app.ml.disease.config import (CLASS_INDEX, IMAGENET_MEAN, IMAGENET_STD, INPUT_SIZE,
                                   PROJECT_DIR)


def training_transform(input_size: int = INPUT_SIZE) -> transforms.Compose:
    return transforms.Compose([
        transforms.RandomResizedCrop(input_size, scale=(0.85, 1.0), ratio=(0.9, 1.1)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(12),
        transforms.ColorJitter(brightness=0.12, contrast=0.12, saturation=0.08, hue=0.02),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])


def evaluation_transform(input_size: int = INPUT_SIZE) -> transforms.Compose:
    resize_size = round(input_size * 256 / 224)
    return transforms.Compose([
        transforms.Resize(resize_size), transforms.CenterCrop(input_size), transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])


def read_manifest(path: Path, *, stage: str | None = None) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))
    return [row for row in rows if stage is None or row.get("stage") == stage]


class ManifestImageDataset(Dataset[tuple[torch.Tensor, int]]):
    def __init__(self, rows: list[dict[str, str]], transform: Callable | None = None):
        self.rows = rows
        self.transform = transform or evaluation_transform()

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, int]:
        row = self.rows[index]
        with Image.open(PROJECT_DIR / row["path"]) as image:
            rgb = image.convert("RGB")
            tensor = self.transform(rgb)
        return tensor, CLASS_INDEX[row["class_name"]]
