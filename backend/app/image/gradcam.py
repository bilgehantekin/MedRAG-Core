"""
Grad-CAM (Gradient-weighted Class Activation Mapping) Module
Provides visual explanations for X-ray predictions
"""

import logging
from typing import Optional, Tuple
import numpy as np

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Lazy imports
torch = None
cv2 = None

from .config import HEATMAP_ALPHA, HEATMAP_COLORMAP, IMAGE_SIZE
from .preprocessing import image_to_base64

logger = logging.getLogger(__name__)


class GradCAM:
    """
    Grad-CAM implementation for visual explanations
    Memory-efficient implementation for 8GB RAM systems
    """

    def __init__(self, model, target_layer):
        """
        Initialize Grad-CAM

        Args:
            model: PyTorch model
            target_layer: Target layer for computing gradients
        """
        global torch
        import torch as _torch
        torch = _torch

        self.model = model
        self.target_layer = target_layer

        # Storage for gradients and activations
        self.gradients = None
        self.activations = None

        # Register hooks
        self._register_hooks()

    def _register_hooks(self):
        """Register forward and backward hooks on target layer"""

        def forward_hook(module, input, output):
            self.activations = output.detach()

        def backward_hook(module, grad_input, grad_output):
            self.gradients = grad_output[0].detach()

        self.target_layer.register_forward_hook(forward_hook)
        self.target_layer.register_full_backward_hook(backward_hook)

    def generate(
        self,
        input_tensor: 'torch.Tensor',
        target_class: Optional[int] = None
    ) -> np.ndarray:
        """
        Generate Grad-CAM heatmap

        Args:
            input_tensor: Input image tensor (1, C, H, W)
            target_class: Target class index (None for highest scoring class)

        Returns:
            Heatmap as numpy array (H, W) with values in [0, 1]
        """
        self.model.eval()

        # Forward pass
        output = self.model(input_tensor)
        probs = torch.sigmoid(output)

        # If no target class specified, use the highest scoring one
        if target_class is None:
            target_class = probs.argmax(dim=1).item()

        # Zero gradients
        self.model.zero_grad()

        # Backward pass for target class
        target_score = output[0, target_class]
        target_score.backward(retain_graph=True)

        # Get gradients and activations
        gradients = self.gradients  # (1, C, H, W)
        activations = self.activations  # (1, C, H, W)

        # Global average pooling of gradients
        weights = torch.mean(gradients, dim=(2, 3), keepdim=True)  # (1, C, 1, 1)

        # Weighted combination of activations
        cam = torch.sum(weights * activations, dim=1, keepdim=True)  # (1, 1, H, W)

        # ReLU to keep only positive influences
        cam = torch.relu(cam)

        # Normalize to [0, 1]
        cam = cam - cam.min()
        cam_max = cam.max()
        if cam_max > 0:
            cam = cam / cam_max

        # Convert to numpy
        heatmap = cam.squeeze().cpu().numpy()

        return heatmap

    def cleanup(self):
        """Clean up stored tensors to free memory"""
        self.gradients = None
        self.activations = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def generate_heatmap_overlay(
    original_image: Image.Image,
    heatmap: np.ndarray,
    alpha: float = HEATMAP_ALPHA,
    colormap: str = HEATMAP_COLORMAP
) -> Tuple[Image.Image, Image.Image, Image.Image]:
    """
    Generate heatmap overlay on original image

    Args:
        original_image: Original PIL Image
        heatmap: Grad-CAM heatmap (H, W) in [0, 1]
        alpha: Overlay transparency
        colormap: Matplotlib colormap name

    Returns:
        Tuple of (heatmap_image, overlay_image, original_resized)
    """
    global cv2

    # Try to use OpenCV for better color mapping
    try:
        import cv2 as _cv2
        cv2 = _cv2
        USE_CV2 = True
    except ImportError:
        USE_CV2 = False
        logger.warning("OpenCV not available, using PIL-based heatmap")

    # Resize original image to match heatmap size (or vice versa)
    target_size = (IMAGE_SIZE, IMAGE_SIZE)
    original_resized = original_image.resize(target_size, Image.Resampling.LANCZOS)

    # Ensure original is RGB
    if original_resized.mode != 'RGB':
        original_resized = original_resized.convert('RGB')

    # Resize heatmap to match image
    if heatmap.shape[0] != IMAGE_SIZE or heatmap.shape[1] != IMAGE_SIZE:
        if USE_CV2:
            heatmap_resized = cv2.resize(heatmap, target_size)
        else:
            heatmap_pil = Image.fromarray((heatmap * 255).astype(np.uint8))
            heatmap_pil = heatmap_pil.resize(target_size, Image.Resampling.BILINEAR)
            heatmap_resized = np.array(heatmap_pil) / 255.0
    else:
        heatmap_resized = heatmap

    # Apply colormap
    if USE_CV2:
        # Convert to 0-255 range
        heatmap_uint8 = (heatmap_resized * 255).astype(np.uint8)

        # Apply JET colormap
        heatmap_colored = cv2.applyColorMap(heatmap_uint8, cv2.COLORMAP_JET)

        # Convert BGR to RGB
        heatmap_colored = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)

        # Create PIL Image
        heatmap_image = Image.fromarray(heatmap_colored)
    else:
        # PIL-based colormap (simple red-yellow-green)
        heatmap_image = _apply_colormap_pil(heatmap_resized)

    # Create overlay
    original_array = np.array(original_resized)
    heatmap_array = np.array(heatmap_image)

    # Blend images
    overlay_array = (
        (1 - alpha) * original_array + alpha * heatmap_array
    ).astype(np.uint8)

    overlay_image = Image.fromarray(overlay_array)

    return heatmap_image, overlay_image, original_resized


def _apply_colormap_pil(heatmap: np.ndarray) -> Image.Image:
    """
    Apply a simple colormap using PIL (fallback when OpenCV not available)

    Args:
        heatmap: Normalized heatmap (H, W) in [0, 1]

    Returns:
        Colored heatmap as PIL Image
    """
    # Simple jet-like colormap
    h, w = heatmap.shape
    colored = np.zeros((h, w, 3), dtype=np.uint8)

    for i in range(h):
        for j in range(w):
            v = heatmap[i, j]

            # Simple jet colormap approximation
            if v < 0.25:
                r, g, b = 0, int(v * 4 * 255), 255
            elif v < 0.5:
                r, g, b = 0, 255, int((0.5 - v) * 4 * 255)
            elif v < 0.75:
                r, g, b = int((v - 0.5) * 4 * 255), 255, 0
            else:
                r, g, b = 255, int((1 - v) * 4 * 255), 0

            colored[i, j] = [r, g, b]

    return Image.fromarray(colored)


def create_comparison_image(
    original: Image.Image,
    heatmap: Image.Image,
    overlay: Image.Image,
    labels: list = None
) -> Image.Image:
    """
    Create a side-by-side comparison image

    Args:
        original: Original image
        heatmap: Heatmap image
        overlay: Overlay image
        labels: Optional list of labels to display

    Returns:
        Combined comparison image
    """
    # Get dimensions
    w, h = original.size

    # Create canvas for 3 images side by side
    canvas_width = w * 3 + 20  # 10px padding between images
    canvas_height = h + 30 if labels else h  # Space for labels

    canvas = Image.new('RGB', (canvas_width, canvas_height), (255, 255, 255))

    # Paste images
    canvas.paste(original, (0, 0))
    canvas.paste(heatmap, (w + 10, 0))
    canvas.paste(overlay, (w * 2 + 20, 0))

    return canvas


def generate_explanation(
    model,
    input_tensor,
    original_image: Image.Image,
    target_class: Optional[int] = None
) -> dict:
    """
    Generate complete explanation with Grad-CAM

    Args:
        model: Loaded model
        input_tensor: Preprocessed input tensor
        original_image: Original PIL Image
        target_class: Target class for explanation

    Returns:
        Dict with heatmap, overlay, and comparison images as base64
    """
    global torch
    import torch as _torch
    torch = _torch

    # Get target layer for Grad-CAM
    target_layer = model.features.denseblock4

    # Create Grad-CAM instance
    gradcam = GradCAM(model, target_layer)

    try:
        # Get model device - ALWAYS match tensor device to model device
        model_device = next(model.parameters()).device

        # Convert numpy to tensor if needed
        if isinstance(input_tensor, np.ndarray):
            input_tensor = torch.from_numpy(input_tensor).float()

        # Move tensor to same device as model (avoid mismatch)
        input_tensor = input_tensor.to(model_device)
        input_tensor.requires_grad = True

        # Generate heatmap
        heatmap = gradcam.generate(input_tensor, target_class)

        # Generate overlay images
        heatmap_img, overlay_img, original_resized = generate_heatmap_overlay(
            original_image, heatmap
        )

        # Convert to base64
        result = {
            "heatmap_base64": image_to_base64(heatmap_img),
            "overlay_base64": image_to_base64(overlay_img),
            "original_base64": image_to_base64(original_resized),
        }

        return result

    finally:
        # Cleanup
        gradcam.cleanup()
