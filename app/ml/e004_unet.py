"""
Compact U-Net architecture for the E004 shipwreck segmentation checkpoint.

Copied verbatim from the E004 handoff package
(`Shipwreck_TrainedModel/E004_AADVIK_HANDOFF/src/training/model.py`) so
`E004_best.pt`'s `model_state_dict` loads against an identical module
graph. Do not modify the layer shapes/ordering here without also
re-checking that the checkpoint still loads -- `load_state_dict` matches
by parameter name and will silently fail (or refuse to load) if this
drifts from the architecture the checkpoint was trained with.
"""

from __future__ import annotations

import torch
import torch.nn as nn


class DoubleConv(nn.Module):
    def __init__(self, in_channels, out_channels):
        super().__init__()

        self.block = nn.Sequential(
            nn.Conv2d(
                in_channels,
                out_channels,
                kernel_size=3,
                padding=1,
                bias=False,
            ),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(
                out_channels,
                out_channels,
                kernel_size=3,
                padding=1,
                bias=False,
            ),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.block(x)


class UNet(nn.Module):
    """
    Compact U-Net for 1024x1024 binary shipwreck segmentation.

    Channel progression:
        16 -> 32 -> 64 -> 128
                         bottleneck -> 256

    This is intentionally much smaller than the previous
    64 -> 128 -> 256 -> 512 -> 1024 architecture.
    """

    def __init__(self, in_channels=1, out_channels=1):
        super().__init__()

        # ----------------------------------------------------
        # Encoder
        # ----------------------------------------------------

        self.enc1 = DoubleConv(in_channels, 16)
        self.enc2 = DoubleConv(16, 32)
        self.enc3 = DoubleConv(32, 64)
        self.enc4 = DoubleConv(64, 128)

        self.pool = nn.MaxPool2d(kernel_size=2)

        # ----------------------------------------------------
        # Bottleneck
        # ----------------------------------------------------

        self.bottleneck = DoubleConv(128, 256)

        # ----------------------------------------------------
        # Decoder
        # ----------------------------------------------------

        self.up4 = nn.ConvTranspose2d(256, 128, kernel_size=2, stride=2)
        self.dec4 = DoubleConv(256, 128)

        self.up3 = nn.ConvTranspose2d(128, 64, kernel_size=2, stride=2)
        self.dec3 = DoubleConv(128, 64)

        self.up2 = nn.ConvTranspose2d(64, 32, kernel_size=2, stride=2)
        self.dec2 = DoubleConv(64, 32)

        self.up1 = nn.ConvTranspose2d(32, 16, kernel_size=2, stride=2)
        self.dec1 = DoubleConv(32, 16)

        # ----------------------------------------------------
        # Binary segmentation output
        # ----------------------------------------------------

        self.out = nn.Conv2d(16, out_channels, kernel_size=1)

    def forward(self, x):

        # ----------------------------------------------------
        # Encoder
        # ----------------------------------------------------

        e1 = self.enc1(x)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        e4 = self.enc4(self.pool(e3))

        # ----------------------------------------------------
        # Bottleneck
        # ----------------------------------------------------

        b = self.bottleneck(self.pool(e4))

        # ----------------------------------------------------
        # Decoder
        # ----------------------------------------------------

        d4 = self.up4(b)
        if d4.shape[2:] != e4.shape[2:]:
            d4 = nn.functional.interpolate(d4, size=e4.shape[2:], mode="bilinear", align_corners=False)
        d4 = torch.cat([d4, e4], dim=1)
        d4 = self.dec4(d4)

        d3 = self.up3(d4)
        if d3.shape[2:] != e3.shape[2:]:
            d3 = nn.functional.interpolate(d3, size=e3.shape[2:], mode="bilinear", align_corners=False)
        d3 = torch.cat([d3, e3], dim=1)
        d3 = self.dec3(d3)

        d2 = self.up2(d3)
        if d2.shape[2:] != e2.shape[2:]:
            d2 = nn.functional.interpolate(d2, size=e2.shape[2:], mode="bilinear", align_corners=False)
        d2 = torch.cat([d2, e2], dim=1)
        d2 = self.dec2(d2)

        d1 = self.up1(d2)
        if d1.shape[2:] != e1.shape[2:]:
            d1 = nn.functional.interpolate(d1, size=e1.shape[2:], mode="bilinear", align_corners=False)
        d1 = torch.cat([d1, e1], dim=1)
        d1 = self.dec1(d1)

        return self.out(d1)
