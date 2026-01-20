"""
X-ray Classification Model Wrapper
Uses TorchXRayVision pretrained models optimized for 8GB RAM
"""

import logging
from typing import Dict, List, Optional, Tuple
import numpy as np

# Lazy imports for memory efficiency
torch = None
xrv = None

from .config import (
    CHESTXRAY_LABELS,
    LABEL_TRANSLATIONS,
    LABEL_EXPLANATIONS,
    CONFIDENCE_THRESHOLD,
    IMAGE_SIZE,
)

logger = logging.getLogger(__name__)


class ModelNotLoadedError(Exception):
    """Raised when model is accessed before loading"""
    pass


class XRayClassifier:
    """
    Chest X-ray classifier using TorchXRayVision
    Singleton pattern for memory efficiency
    """

    _instance = None
    _model = None
    _device = None
    _is_loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Only initialize once
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._model = None
            self._device = None
            self._is_loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    @property
    def device(self) -> str:
        return str(self._device) if self._device else "not loaded"

    def load_model(self, force_cpu: bool = True) -> bool:
        """
        Load the pretrained model (lazy loading)
        Optimized for 8GB RAM Macs

        Args:
            force_cpu: Force CPU usage (default True for stability on low RAM)

        Returns:
            True if loaded successfully
        """
        global torch, xrv

        if self._is_loaded:
            logger.info("Model already loaded, skipping")
            return True

        try:
            import gc
            gc.collect()  # Free memory before loading

            # Lazy import torch
            import torch as _torch
            torch = _torch

            # For 8GB RAM Macs, always use CPU to avoid MPS memory issues
            # MPS can cause memory spikes during model loading
            self._device = torch.device("cpu")
            logger.info("Using CPU (optimized for low RAM)")

            # Import torchxrayvision
            import torchxrayvision as _xrv
            xrv = _xrv

            # Load pretrained model - use smaller "chex" model instead of "all"
            # "chex" = ChestX-ray14 only (~30MB)
            # "all" = multiple datasets (~50MB) - more memory hungry
            logger.info("Loading TorchXRayVision DenseNet model (chex)...")
            self._model = xrv.models.DenseNet(weights="densenet121-res224-chex")

            # Set to evaluation mode (no gradients needed)
            self._model.eval()

            # Disable gradient computation globally for inference
            for param in self._model.parameters():
                param.requires_grad = False

            self._is_loaded = True
            logger.info(f"Model loaded successfully on {self._device}")

            gc.collect()  # Clean up after loading
            return True

        except ImportError as e:
            logger.error(f"Failed to import required libraries: {e}")
            logger.error("Please install: pip install torch torchvision torchxrayvision")
            raise ImportError(
                "Gerekli kütüphaneler yüklü değil. "
                "Lütfen 'pip install torch torchvision torchxrayvision' komutunu çalıştırın."
            )
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise RuntimeError(f"Model yüklenemedi: {str(e)}")

    def unload_model(self):
        """Unload model to free memory"""
        if self._model is not None:
            del self._model
            self._model = None

        if torch is not None and torch.cuda.is_available():
            torch.cuda.empty_cache()

        self._is_loaded = False
        logger.info("Model unloaded")

    def predict(
        self,
        image_array: np.ndarray,
        top_k: int = 5
    ) -> List[Dict]:
        """
        Run inference on preprocessed image
        Memory-optimized for 8GB RAM

        Args:
            image_array: Preprocessed image array (1, 1, H, W)
            top_k: Number of top predictions to return

        Returns:
            List of prediction dicts with label, confidence, translation, explanation
        """
        import gc

        if not self._is_loaded:
            raise ModelNotLoadedError("Model yüklenmedi. Önce load_model() çağırın.")

        try:
            # Convert to tensor
            img_tensor = torch.from_numpy(image_array).float()

            # Run inference with no gradient tracking
            with torch.inference_mode():
                outputs = self._model(img_tensor)

                # TorchXRayVision outputs raw scores, apply sigmoid for probabilities
                probabilities = torch.sigmoid(outputs)
                probs = probabilities.numpy()[0]

            # Get model's pathology list
            pathologies = self._model.pathologies

            # Build results
            results = []
            for i, (label, prob) in enumerate(zip(pathologies, probs)):
                # Skip labels not in our target list
                if label not in CHESTXRAY_LABELS:
                    continue

                results.append({
                    "label": label,
                    "label_tr": LABEL_TRANSLATIONS.get(label, label),
                    "confidence": float(prob),
                    "confidence_pct": f"{prob * 100:.1f}%",
                    "explanation": LABEL_EXPLANATIONS.get(label, ""),
                    "is_positive": prob >= CONFIDENCE_THRESHOLD,
                })

            # Sort by confidence
            results.sort(key=lambda x: x["confidence"], reverse=True)

            return results[:top_k]

        finally:
            # Clean up tensors
            del img_tensor
            gc.collect()

    def predict_with_features(
        self,
        image_array: np.ndarray
    ) -> Tuple[List[Dict], np.ndarray]:
        """
        Run inference and return feature maps for Grad-CAM

        Args:
            image_array: Preprocessed image array

        Returns:
            Tuple of (predictions, feature_tensor)
        """
        if not self._is_loaded:
            raise ModelNotLoadedError("Model yüklenmedi.")

        img_tensor = torch.from_numpy(image_array).float()
        img_tensor = img_tensor.to(self._device)
        img_tensor.requires_grad = True

        # Get predictions
        predictions = self.predict(image_array)

        return predictions, img_tensor

    def get_model_info(self) -> Dict:
        """Get information about the loaded model"""
        return {
            "name": "DenseNet121",
            "version": "torchxrayvision-all",
            "dataset": "ChestX-ray14 + CheXpert + MIMIC-CXR + NIH + PadChest",
            "input_size": IMAGE_SIZE,
            "num_classes": len(CHESTXRAY_LABELS),
            "device": str(self._device) if self._device else "not loaded",
            "is_loaded": self._is_loaded,
            "labels": CHESTXRAY_LABELS,
        }

    def get_target_layer(self):
        """Get the target layer for Grad-CAM"""
        if not self._is_loaded or self._model is None:
            return None

        # For DenseNet, we target the last dense block
        # TorchXRayVision DenseNet structure: features -> denseblock4 -> norm5
        return self._model.features.denseblock4


# Singleton instance
_classifier: Optional[XRayClassifier] = None


def get_classifier() -> XRayClassifier:
    """Get or create the classifier singleton"""
    global _classifier
    if _classifier is None:
        _classifier = XRayClassifier()
    return _classifier


async def ensure_model_loaded() -> XRayClassifier:
    """Ensure model is loaded (async wrapper)"""
    classifier = get_classifier()
    if not classifier.is_loaded:
        classifier.load_model()
    return classifier
