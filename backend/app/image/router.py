"""
FastAPI Router for Image Analysis
Provides endpoints for X-ray classification and explanation
Uses only inference.py for model management (single source of truth)
"""

import logging
import math
import time
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from .config import (
    DISCLAIMER_TR,
    DISCLAIMER_EN,
    CONFIDENCE_THRESHOLD,
    LABEL_TRANSLATIONS,
    LABEL_EXPLANATIONS,
    DEMO_MODE,
    IMAGE_SIZE,
    TEMP_FILE_TTL_SECONDS,
)
from .preprocessing import (
    validate_image_file,
    load_image,
    cleanup_old_temp_files,
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/image", tags=["Image Analysis"])


# Response models
class PredictionItem(BaseModel):
    label: str = Field(..., description="English label")
    label_tr: str = Field(..., description="Turkish label")
    confidence: float = Field(..., ge=0, le=1, description="Model confidence score (not calibrated probability)")
    confidence_pct: str = Field(..., description="Confidence as percentage")
    explanation: str = Field("", description="Simple explanation in Turkish")
    is_positive: bool = Field(..., description="Above threshold")


class ModelInfo(BaseModel):
    name: str
    version: str
    dataset: str
    device: str
    input_size: int


class AnalysisResponse(BaseModel):
    success: bool = True
    predictions: list[PredictionItem]
    top_finding: Optional[str] = None
    top_finding_tr: Optional[str] = None
    has_positive_findings: bool = False
    heatmap_base64: Optional[str] = None
    overlay_base64: Optional[str] = None
    original_base64: Optional[str] = None
    model_info: ModelInfo
    processing_time_ms: int
    disclaimer: str = DISCLAIMER_TR
    disclaimer_en: str = DISCLAIMER_EN
    timestamp: str


class PredictResponse(BaseModel):
    success: bool = True
    predictions: list[PredictionItem]
    processing_time_ms: int
    disclaimer: str = DISCLAIMER_TR


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    device: str
    message: str


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    error_code: str


def stable_sigmoid(x: float) -> float:
    """Numerically stable sigmoid function to avoid overflow"""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    else:
        exp_x = math.exp(x)
        return exp_x / (1.0 + exp_x)


@router.get("/health", response_model=HealthResponse)
async def image_health():
    """Check image analysis service health"""
    from . import inference

    is_loaded = inference.is_model_loaded()
    device = inference.get_device() if is_loaded else "not loaded"

    return HealthResponse(
        status="healthy" if is_loaded else "model_not_loaded",
        model_loaded=is_loaded,
        device=device,
        message="Model yüklü ve hazır" if is_loaded else "Model henüz yüklenmedi"
    )


@router.post("/load-model")
async def load_model_endpoint():
    """
    Explicitly load the model
    Useful for pre-warming before first request
    """
    from . import inference

    try:
        start_time = time.time()

        if inference.is_model_loaded():
            return {
                "success": True,
                "message": "Model zaten yüklü",
                "device": inference.get_device(),
                "load_time_ms": 0
            }

        success = inference.load_model()
        load_time = int((time.time() - start_time) * 1000)

        if success:
            return {
                "success": True,
                "message": "Model başarıyla yüklendi",
                "device": inference.get_device(),
                "load_time_ms": load_time
            }
        else:
            raise HTTPException(
                status_code=503,
                detail="Model yüklenemedi"
            )
    except Exception as e:
        logger.error(f"Model load failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Model yüklenemedi: {str(e)}"
        )


def get_demo_predictions():
    """Generate mock predictions for demo mode"""
    import random
    random.seed(42)  # Reproducible for testing

    demo_labels = ["Cardiomegaly", "Effusion", "Atelectasis", "Pneumonia", "Nodule"]
    predictions = []

    for i, label in enumerate(demo_labels):
        conf = max(0.3, 0.75 - (i * 0.1) + random.uniform(-0.05, 0.05))
        predictions.append({
            "label": label,
            "label_tr": LABEL_TRANSLATIONS.get(label, label),
            "confidence": conf,
            "confidence_pct": f"{conf * 100:.1f}%",
            "explanation": LABEL_EXPLANATIONS.get(label, ""),
            "is_positive": conf >= CONFIDENCE_THRESHOLD,
        })

    return predictions


@router.post("/analyze", response_model=AnalysisResponse)
def analyze_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="X-ray image (JPEG/PNG, max 10MB)"),
    include_explanation: bool = False
):
    """
    Analyze chest X-ray image

    - Validates and preprocesses the image
    - Runs classification model (or returns demo data if DEMO_MODE=true)
    - Returns predictions with confidence scores
    - Optionally returns Grad-CAM heatmap if include_explanation=true

    **Important**: This is for informational purposes only, not medical diagnosis.
    """
    import gc

    start_time = time.time()

    # Schedule cleanup of old temp files (use config TTL)
    background_tasks.add_task(cleanup_old_temp_files, TEMP_FILE_TTL_SECONDS)

    # Read file content
    try:
        file_content = file.file.read()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Dosya okunamadı: {str(e)}"
        )

    # Validate image
    is_valid, error_msg = validate_image_file(file_content, file.filename)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail=error_msg
        )

    try:
        # DEMO MODE - return mock predictions without loading model
        if DEMO_MODE:
            logger.info("Running in DEMO MODE - returning mock predictions")

            predictions = get_demo_predictions()

            # Determine top finding
            top_finding = predictions[0]["label"] if predictions[0]["is_positive"] else None
            top_finding_tr = predictions[0]["label_tr"] if predictions[0]["is_positive"] else None
            has_positive = predictions[0]["is_positive"]

            processing_time = int((time.time() - start_time) * 1000)

            return AnalysisResponse(
                success=True,
                predictions=[PredictionItem(**p) for p in predictions],
                top_finding=top_finding,
                top_finding_tr=top_finding_tr,
                has_positive_findings=has_positive,
                heatmap_base64=None,
                overlay_base64=None,
                original_base64=None,
                model_info=ModelInfo(
                    name="DenseNet121 (DEMO)",
                    version="demo-mode",
                    dataset="Simulated",
                    device="none (demo)",
                    input_size=IMAGE_SIZE
                ),
                processing_time_ms=processing_time,
                disclaimer=DISCLAIMER_TR + "\n\n🔶 DEMO MODU: Bu sonuçlar gerçek model yerine simülasyon verileridir.",
                disclaimer_en=DISCLAIMER_EN + "\n\n🔶 DEMO MODE: These results are simulated, not from actual model.",
                timestamp=datetime.now().isoformat()
            )

        # REAL MODE - use official TorchXRayVision pipeline (single source: inference.py)
        from . import inference

        # Ensure model is loaded
        if not inference.is_model_loaded():
            logger.info("Loading model on first request...")
            if not inference.load_model():
                raise HTTPException(
                    status_code=503,
                    detail="Model yüklenemedi. Sistem kaynakları yetersiz olabilir."
                )

        # Load image with PIL
        original_image = load_image(file_content)

        # Run prediction using official TorchXRayVision pipeline
        result = inference.predict(original_image)
        raw_scores = result["raw_scores"]
        pathologies = result["pathologies"]

        # Build predictions list with translations
        # Use ALL pathologies from the model (no filtering)
        predictions = []
        for label in pathologies:
            if label not in raw_scores:
                continue
            if not label:  # Skip empty labels
                continue

            score = raw_scores[label]
            # Use stable sigmoid to avoid overflow
            prob = stable_sigmoid(score)

            predictions.append({
                "label": label,
                "label_tr": LABEL_TRANSLATIONS.get(label, label),
                "confidence": prob,
                "confidence_pct": f"{prob * 100:.1f}%",
                "explanation": LABEL_EXPLANATIONS.get(label, ""),
                "is_positive": prob >= CONFIDENCE_THRESHOLD,
            })

        # Sort by confidence
        predictions.sort(key=lambda x: x["confidence"], reverse=True)
        predictions = predictions[:5]  # Top 5

        # Determine top finding
        top_finding = None
        top_finding_tr = None
        has_positive = False

        if predictions and predictions[0]["is_positive"]:
            top_finding = predictions[0]["label"]
            top_finding_tr = predictions[0]["label_tr"]
            has_positive = True

        # Generate Grad-CAM explanation if requested
        heatmap_b64 = None
        overlay_b64 = None
        original_b64 = None

        if include_explanation and predictions:
            try:
                from .gradcam import generate_explanation

                model = inference.get_model()
                input_tensor = inference.preprocess_image(original_image)

                # Find target class index (top prediction)
                top_label = predictions[0]["label"]
                target_class = pathologies.index(top_label) if top_label in pathologies else None

                # Generate explanation (sync function)
                explanation = generate_explanation(
                    model=model,
                    input_tensor=input_tensor,
                    original_image=original_image,
                    target_class=target_class
                )

                heatmap_b64 = explanation.get("heatmap_base64")
                overlay_b64 = explanation.get("overlay_base64")
                original_b64 = explanation.get("original_base64")

                logger.info("Grad-CAM explanation generated successfully")

            except Exception as e:
                logger.warning(f"Grad-CAM generation failed: {e}")
                # Continue without explanation - don't fail the whole request

        processing_time = int((time.time() - start_time) * 1000)

        # Clean up
        del file_content
        gc.collect()

        return AnalysisResponse(
            success=True,
            predictions=[PredictionItem(**p) for p in predictions],
            top_finding=top_finding,
            top_finding_tr=top_finding_tr,
            has_positive_findings=has_positive,
            heatmap_base64=heatmap_b64,
            overlay_base64=overlay_b64,
            original_base64=original_b64,
            model_info=ModelInfo(
                name="DenseNet121",
                version="densenet121-res224-chex",
                dataset="ChestX-ray14",
                device=inference.get_device(),
                input_size=IMAGE_SIZE
            ),
            processing_time_ms=processing_time,
            disclaimer=DISCLAIMER_TR,
            disclaimer_en=DISCLAIMER_EN,
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Analiz sırasında hata oluştu: {str(e)}"
        )


@router.post("/predict", response_model=PredictResponse)
def predict_only(
    file: UploadFile = File(...),
    top_k: int = 5
):
    """
    Quick prediction without Grad-CAM explanation
    Uses the same inference.py module as /analyze
    """
    from . import inference
    import gc

    start_time = time.time()

    # Read and validate
    file_content = file.file.read()
    is_valid, error_msg = validate_image_file(file_content, file.filename)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    try:
        # Ensure model is loaded
        if not inference.is_model_loaded():
            if not inference.load_model():
                raise HTTPException(status_code=503, detail="Model yüklenemedi")

        # Load and predict
        original_image = load_image(file_content)
        result = inference.predict(original_image)

        # Build predictions with stable sigmoid
        predictions = []
        for label in result["pathologies"]:
            if not label or label not in result["raw_scores"]:
                continue
            score = result["raw_scores"][label]
            prob = stable_sigmoid(score)
            predictions.append({
                "label": label,
                "label_tr": LABEL_TRANSLATIONS.get(label, label),
                "confidence": prob,
                "confidence_pct": f"{prob * 100:.1f}%",
                "explanation": LABEL_EXPLANATIONS.get(label, ""),
                "is_positive": prob >= CONFIDENCE_THRESHOLD,
            })

        predictions.sort(key=lambda x: x["confidence"], reverse=True)
        processing_time = int((time.time() - start_time) * 1000)

        del file_content
        gc.collect()

        return PredictResponse(
            success=True,
            predictions=[PredictionItem(**p) for p in predictions[:top_k]],
            processing_time_ms=processing_time,
            disclaimer=DISCLAIMER_TR
        )

    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/labels")
async def get_labels():
    """Get list of supported labels with translations"""
    from . import inference

    # Use model's pathologies directly (no dummy prediction needed)
    model = inference.get_model()
    if model is not None:
        labels_list = [l for l in model.pathologies if l]
    else:
        from .config import CHESTXRAY_LABELS
        labels_list = CHESTXRAY_LABELS

    labels = []
    for label in labels_list:
        labels.append({
            "label": label,
            "label_tr": LABEL_TRANSLATIONS.get(label, label),
            "explanation": LABEL_EXPLANATIONS.get(label, "")
        })

    return {
        "labels": labels,
        "count": len(labels),
        "threshold": CONFIDENCE_THRESHOLD
    }


@router.get("/model-info")
async def get_model_info():
    """Get information about the loaded model"""
    from . import inference

    is_loaded = inference.is_model_loaded()
    model = inference.get_model()

    # Dynamic pathology count from actual model
    num_pathologies = len(model.pathologies) if model else 0

    return {
        "name": "DenseNet121",
        "version": "densenet121-res224-chex",
        "dataset": "ChestX-ray14",
        "device": inference.get_device() if is_loaded else "not loaded",
        "is_loaded": is_loaded,
        "input_size": IMAGE_SIZE,
        "num_pathologies": num_pathologies,
    }
