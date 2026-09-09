import torch
import torch.nn as nn


class BCEDiceLoss(nn.Module):
    """
    Combined Binary Cross Entropy + Dice loss.

    BCE handles pixel-wise classification.
    Dice helps with the strong foreground/background imbalance
    present in shipwreck segmentation.
    """

    def __init__(self, bce_weight=0.5, dice_weight=0.5):
        super().__init__()

        self.bce_weight = bce_weight
        self.dice_weight = dice_weight

        self.bce = nn.BCEWithLogitsLoss()

    def forward(self, logits, targets):
        bce_loss = self.bce(logits, targets)

        probabilities = torch.sigmoid(logits)

        probabilities = probabilities.flatten()
        targets = targets.flatten()

        intersection = (
            probabilities * targets
        ).sum()

        dice = (
            (2.0 * intersection + 1e-7)
            /
            (
                probabilities.sum()
                + targets.sum()
                + 1e-7
            )
        )

        dice_loss = 1.0 - dice

        return (
            self.bce_weight * bce_loss
            + self.dice_weight * dice_loss
        )
