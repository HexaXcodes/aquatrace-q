import torch


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(logits, targets, threshold=0.5):
    """
    Calculate Dice, IoU, precision and recall.

    logits:
        Raw model outputs.

    targets:
        Binary ground-truth masks.
    """

    probabilities = torch.sigmoid(logits)

    predictions = probabilities >= threshold
    targets = targets >= 0.5

    predictions = predictions.flatten()
    targets = targets.flatten()

    true_positive = (
        (predictions == 1) &
        (targets == 1)
    ).sum().float()

    false_positive = (
        (predictions == 1) &
        (targets == 0)
    ).sum().float()

    false_negative = (
        (predictions == 0) &
        (targets == 1)
    ).sum().float()

    intersection = true_positive

    dice = (
        (2 * intersection + 1e-7)
        /
        (
            predictions.sum()
            + targets.sum()
            + 1e-7
        )
    )

    union = (
        predictions.sum()
        + targets.sum()
        - intersection
    )

    iou = (
        (intersection + 1e-7)
        /
        (union + 1e-7)
    )

    precision = (
        (true_positive + 1e-7)
        /
        (
            true_positive
            + false_positive
            + 1e-7
        )
    )

    recall = (
        (true_positive + 1e-7)
        /
        (
            true_positive
            + false_negative
            + 1e-7
        )
    )

    return {
        "dice": dice.item(),
        "iou": iou.item(),
        "precision": precision.item(),
        "recall": recall.item(),
    }


# ============================================================
# TRAINING
# ============================================================

def train_one_epoch(
    model,
    loader,
    criterion,
    optimizer,
    device,
):
    """
    Train the model for one complete epoch.

    Returns:
        Average loss, Dice, IoU, precision and recall.
    """

    model.train()

    total_loss = 0.0

    metric_sums = {
        "dice": 0.0,
        "iou": 0.0,
        "precision": 0.0,
        "recall": 0.0,
    }

    batches = 0

    for batch in loader:

        images = batch["image"].to(device)
        masks = batch["mask"].to(device)

        optimizer.zero_grad()

        logits = model(images)

        loss = criterion(logits, masks)

        loss.backward()

        optimizer.step()

        total_loss += loss.item()

        metrics = calculate_metrics(
            logits.detach(),
            masks,
        )

        for key in metric_sums:
            metric_sums[key] += metrics[key]

        batches += 1

        # ----------------------------------------------------
        # Progress reporting
        # ----------------------------------------------------

        if batches % 100 == 0:
            print(
                f"    Batch {batches}/{len(loader)} "
                f"loss={loss.item():.4f}",
                flush=True,
            )

    if batches == 0:
        raise RuntimeError(
            "Training DataLoader produced zero batches."
        )

    return {
        "loss": total_loss / batches,
        "dice": metric_sums["dice"] / batches,
        "iou": metric_sums["iou"] / batches,
        "precision": metric_sums["precision"] / batches,
        "recall": metric_sums["recall"] / batches,
    }


# ============================================================
# VALIDATION
# ============================================================

@torch.no_grad()
def validate(
    model,
    loader,
    criterion,
    device,
):
    """
    Evaluate the model on the validation set.

    No gradients are calculated.
    """

    model.eval()

    total_loss = 0.0

    metric_sums = {
        "dice": 0.0,
        "iou": 0.0,
        "precision": 0.0,
        "recall": 0.0,
    }

    batches = 0

    for batch in loader:

        images = batch["image"].to(device)
        masks = batch["mask"].to(device)

        logits = model(images)

        loss = criterion(logits, masks)

        total_loss += loss.item()

        metrics = calculate_metrics(
            logits,
            masks,
        )

        for key in metric_sums:
            metric_sums[key] += metrics[key]

        batches += 1

        # ----------------------------------------------------
        # Validation progress reporting
        # ----------------------------------------------------

        if batches % 100 == 0:
            print(
                f"    Validation batch "
                f"{batches}/{len(loader)} "
                f"loss={loss.item():.4f}",
                flush=True,
            )

    if batches == 0:
        raise RuntimeError(
            "Validation DataLoader produced zero batches."
        )

    return {
        "loss": total_loss / batches,
        "dice": metric_sums["dice"] / batches,
        "iou": metric_sums["iou"] / batches,
        "precision": metric_sums["precision"] / batches,
        "recall": metric_sums["recall"] / batches,
    }