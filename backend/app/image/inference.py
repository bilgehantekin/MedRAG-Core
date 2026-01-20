"""
X-ray Inference Module
Uses TorchXRayVision's official preprocessing pipeline
"""

import logging
from typing import Dict, List, Optional
from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)

# Global model instance - loaded once at startup
_model = None
_device = "cpu"

def load_model():
    """Load model at startup"""
    global _model, _device

    if _model is not None:
        logger.info("Model already loaded")
        return True

    try:
        import torch
        import torchxrayvision as xrv

        logger.info("Loading TorchXRayVision DenseNet model (densenet121-res224-chex)...")
        _device = "cpu"  # Mac M3 8GB için en stabil

        _model = xrv.models.DenseNet(weights="densenet121-res224-chex")
        _model = _model.to(_device)
        _model.eval()

        # NOTE: We don't disable requires_grad here because Grad-CAM needs gradients
        # Inference uses torch.inference_mode() which is sufficient for performance
        # Grad-CAM will work correctly with gradients enabled

        logger.info(f"Model loaded successfully on {_device}")
        return True

    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        return False


def preprocess_image(pil_img: Image.Image) -> 'torch.Tensor':
    """
    Preprocess image using TorchXRayVision's official pipeline
    """
    import torch
    import torchvision
    import torchxrayvision as xrv

    # Convert to RGB
    img = pil_img.convert("RGB")
    img = np.array(img)  # H, W, 3 uint8

    # TorchXRayVision normalization: scales to [-1024, 1024]
    img = xrv.datasets.normalize(img, 255)

    # Convert to grayscale (single channel)
    img = img.mean(2)[None, ...]  # Shape: (1, H, W)

    # Apply transforms
    transform = torchvision.transforms.Compose([
        xrv.datasets.XRayCenterCrop(),
        xrv.datasets.XRayResizer(224),
    ])
    img = transform(img)  # Shape: (1, 224, 224)

    # Convert to tensor
    img_tensor = torch.from_numpy(img).float()

    # Add batch dimension: (1, 1, 224, 224)
    return img_tensor[None, ...]


def predict(pil_img: Image.Image) -> Dict:
    """
    Run prediction on image

    Returns:
        Dict with predictions and metadata
    """
    import torch

    if _model is None:
        raise RuntimeError("Model not loaded. Call load_model() first.")

    # Preprocess
    x = preprocess_image(pil_img).to(_device)

    # Inference
    with torch.inference_mode():
        outputs = _model(x)
        scores = outputs[0].detach().cpu().numpy()

    # Build predictions dict
    predictions = {}
    for label, score in zip(_model.pathologies, scores):
        predictions[label] = float(score)

    return {
        "raw_scores": predictions,
        "pathologies": list(_model.pathologies),
    }


def is_model_loaded() -> bool:
    """Check if model is loaded"""
    return _model is not None


def get_device() -> str:
    """Get the device the model is running on"""
    return _device if _model is not None else "not loaded"


def get_model():
    """Get the loaded model instance (for Grad-CAM etc.)"""
    return _model
