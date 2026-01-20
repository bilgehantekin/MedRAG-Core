"""
Image Preprocessing Module
Handles image loading, validation, and preprocessing for X-ray analysis
"""

import io
import hashlib
from pathlib import Path
from typing import Tuple, Optional
from datetime import datetime
import numpy as np

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from .config import (
    IMAGE_SIZE,
    MAX_FILE_SIZE_MB,
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    TEMP_DIR,
)


class ImageValidationError(Exception):
    """Custom exception for image validation errors"""
    pass


def validate_image_file(
    file_content: bytes,
    filename: str,
    max_size_mb: float = MAX_FILE_SIZE_MB
) -> Tuple[bool, str]:
    """
    Validate uploaded image file

    Args:
        file_content: Raw file bytes
        filename: Original filename
        max_size_mb: Maximum file size in MB

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check file size
    file_size_mb = len(file_content) / (1024 * 1024)
    if file_size_mb > max_size_mb:
        return False, f"Dosya boyutu çok büyük: {file_size_mb:.1f}MB (max: {max_size_mb}MB)"

    # Check extension
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Desteklenmeyen dosya formatı: {ext}. Desteklenen: {', '.join(ALLOWED_EXTENSIONS)}"

    # Check magic bytes (file signature)
    if not _check_magic_bytes(file_content):
        return False, "Geçersiz dosya formatı. Lütfen gerçek bir JPEG veya PNG dosyası yükleyin."

    # Try to open with PIL
    if PIL_AVAILABLE:
        try:
            img = Image.open(io.BytesIO(file_content))
            img.verify()  # Verify it's a valid image
        except Exception as e:
            return False, f"Görüntü dosyası bozuk veya okunamıyor: {str(e)}"

    return True, ""


def _check_magic_bytes(content: bytes) -> bool:
    """Check file magic bytes to verify actual format"""
    if len(content) < 8:
        return False

    # JPEG magic bytes
    if content[:2] == b'\xff\xd8':
        return True

    # PNG magic bytes
    if content[:8] == b'\x89PNG\r\n\x1a\n':
        return True

    return False


def load_image(file_content: bytes) -> Image.Image:
    """
    Load image from bytes

    Args:
        file_content: Raw image bytes

    Returns:
        PIL Image object
    """
    if not PIL_AVAILABLE:
        raise ImportError("PIL/Pillow is required for image processing")

    img = Image.open(io.BytesIO(file_content))

    # Convert to RGB if necessary (handles RGBA, grayscale, etc.)
    if img.mode != 'RGB':
        # For X-rays (grayscale), convert to RGB by repeating channels
        if img.mode == 'L':
            img = img.convert('RGB')
        elif img.mode == 'RGBA':
            # Create white background and paste
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
        else:
            img = img.convert('RGB')

    return img


# NOTE: Preprocessing for model inference is handled by inference.py using
# TorchXRayVision's official pipeline (xrv.datasets.normalize, XRayCenterCrop, XRayResizer).
# The functions below (preprocess_for_model, preprocess_xray) were removed because they
# used incorrect normalization ranges. Always use inference.preprocess_image() instead.


def generate_temp_filename(original_filename: str) -> str:
    """
    Generate a unique temporary filename

    Args:
        original_filename: Original file name

    Returns:
        Unique filename with timestamp hash
    """
    timestamp = datetime.now().isoformat()
    ext = Path(original_filename).suffix.lower()

    # Create hash from timestamp + original name
    hash_input = f"{timestamp}_{original_filename}".encode()
    file_hash = hashlib.md5(hash_input).hexdigest()[:12]

    return f"xray_{file_hash}{ext}"


def save_temp_image(img: Image.Image, filename: str) -> Path:
    """
    Save image to temp directory

    Args:
        img: PIL Image
        filename: Filename to use

    Returns:
        Path to saved file
    """
    filepath = TEMP_DIR / filename
    img.save(filepath)
    return filepath


def cleanup_old_temp_files(max_age_seconds: int = 300):
    """
    Remove temp files older than max_age_seconds

    Args:
        max_age_seconds: Maximum file age in seconds
    """
    import time

    current_time = time.time()

    for filepath in TEMP_DIR.glob("*"):
        if filepath.is_file():
            file_age = current_time - filepath.stat().st_mtime
            if file_age > max_age_seconds:
                try:
                    filepath.unlink()
                except Exception:
                    pass  # Ignore deletion errors


def image_to_base64(img: Image.Image, format: str = "PNG") -> str:
    """
    Convert PIL Image to base64 string

    Args:
        img: PIL Image
        format: Output format (PNG, JPEG)

    Returns:
        Base64 encoded string with data URI prefix
    """
    import base64

    buffer = io.BytesIO()
    img.save(buffer, format=format)
    buffer.seek(0)

    b64_string = base64.b64encode(buffer.getvalue()).decode('utf-8')
    mime_type = "image/png" if format.upper() == "PNG" else "image/jpeg"

    return f"data:{mime_type};base64,{b64_string}"
