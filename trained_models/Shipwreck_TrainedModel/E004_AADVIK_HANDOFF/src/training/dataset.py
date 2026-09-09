
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset


class ShipwreckDataset(Dataset):
    """
    AI4Shipwrecks tiled segmentation dataset.

    Images are grayscale (1 channel).
    Masks are binary (0 = background, 1 = shipwreck).

    Only valid 1024x1024 image/mask pairs are used.
    Malformed tiles are skipped during dataset construction.
    """

    EXPECTED_SIZE = (1024, 1024)

    def __init__(self, root, split):
        self.root = Path(root)
        self.split = split

        self.image_dir = self.root / split / "images"
        self.label_dir = self.root / split / "labels"

        if not self.image_dir.exists():
            raise FileNotFoundError(
                f"Image directory does not exist: {self.image_dir}"
            )

        if not self.label_dir.exists():
            raise FileNotFoundError(
                f"Label directory does not exist: {self.label_dir}"
            )

        all_images = sorted(self.image_dir.glob("*.png"))

        if not all_images:
            raise RuntimeError(
                f"No PNG images found in {self.image_dir}"
            )

        self.images = []
        self.skipped = []

        for image_path in all_images:

            label_path = self.label_dir / image_path.name

            if not label_path.exists():
                raise RuntimeError(
                    f"Missing label for image: {image_path.name}"
                )

            try:
                with Image.open(image_path) as image:
                    image_size = image.size

                with Image.open(label_path) as mask:
                    mask_size = mask.size

            except Exception as exc:
                raise RuntimeError(
                    f"Could not read image/mask pair "
                    f"{image_path.name}: {exc}"
                ) from exc

            if (
                image_size != self.EXPECTED_SIZE
                or mask_size != self.EXPECTED_SIZE
            ):
                self.skipped.append(
                    {
                        "name": image_path.name,
                        "image_size": image_size,
                        "mask_size": mask_size,
                    }
                )
                continue

            if image_size != mask_size:
                raise RuntimeError(
                    f"Image/mask size mismatch for "
                    f"{image_path.name}: "
                    f"{image_size} vs {mask_size}"
                )

            self.images.append(image_path)

        if not self.images:
            raise RuntimeError(
                f"No valid 1024x1024 image/mask pairs "
                f"found in {self.split}"
            )

        print(
            f"{split}: "
            f"{len(self.images)} valid image/mask pairs found"
        )

        if self.skipped:
            print(
                f"{split}: "
                f"{len(self.skipped)} malformed pairs skipped"
            )

            for item in self.skipped:
                print(
                    f"  SKIPPED: {item['name']} "
                    f"image={item['image_size']} "
                    f"mask={item['mask_size']}"
                )

    def __len__(self):
        return len(self.images)

    def __getitem__(self, index):

        image_path = self.images[index]
        label_path = self.label_dir / image_path.name

        image = np.array(
            Image.open(image_path)
        )

        mask = np.array(
            Image.open(label_path)
        )

        if image.ndim != 2:
            raise ValueError(
                f"Expected grayscale image, "
                f"got shape {image.shape} "
                f"for {image_path.name}"
            )

        if image.shape != mask.shape:
            raise ValueError(
                f"Image/mask size mismatch for "
                f"{image_path.name}: "
                f"{image.shape} vs {mask.shape}"
            )

        expected_shape = (1024, 1024)

        if image.shape != expected_shape:
            raise ValueError(
                f"Expected 1024x1024 sample, "
                f"got {image.shape} "
                f"for {image_path.name}"
            )

        image = torch.from_numpy(
            image.copy()
        ).unsqueeze(0).float() / 255.0

        mask = torch.from_numpy(
            (mask > 0).astype(np.float32)
        ).unsqueeze(0)

        return {
            "image": image,
            "mask": mask,
            "name": image_path.name,
        }
