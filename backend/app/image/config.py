"""
Image Analysis Configuration
Optimized for Mac M3 Air 8GB RAM
"""

import os
from pathlib import Path

# CRITICAL: Set thread limits BEFORE importing PyTorch to prevent segfaults on Apple Silicon
# These must be set at the very start, before any torch import
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")

# Demo mode - returns mock predictions without loading model
# Default: "false" - real model works with thread limits set above
# Set to "true" if you still experience crashes
DEMO_MODE = os.getenv("IMAGE_DEMO_MODE", "false").lower() == "true"

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
TEMP_DIR = BASE_DIR / "temp" / "images"
MODEL_DIR = BASE_DIR / "models"

# Ensure directories exist
TEMP_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Image settings
IMAGE_SIZE = 224  # Standard for most pretrained models
MAX_FILE_SIZE_MB = 10
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png"}

# Model settings - optimized for 8GB RAM
MODEL_NAME = "densenet121-res224-chex"  # TorchXRayVision pretrained
BATCH_SIZE = 1  # Single image inference for memory efficiency
USE_FP16 = False  # FP16 can cause issues on some MPS setups

# ChestX-ray14 labels (14 pathologies)
CHESTXRAY_LABELS = [
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Edema",
    "Effusion",
    "Emphysema",
    "Fibrosis",
    "Hernia",
    "Infiltration",
    "Mass",
    "Nodule",
    "Pleural_Thickening",
    "Pneumonia",
    "Pneumothorax",
]

# Turkish translations (includes all 18 TorchXRayVision pathologies)
LABEL_TRANSLATIONS = {
    # ChestX-ray14 original labels
    "Atelectasis": "Atelektazi",
    "Cardiomegaly": "Kardiyomegali (Kalp Büyümesi)",
    "Consolidation": "Konsolidasyon",
    "Edema": "Ödem",
    "Effusion": "Plevral Efüzyon",
    "Emphysema": "Amfizem",
    "Fibrosis": "Fibrozis",
    "Hernia": "Herni (Fıtık)",
    "Infiltration": "İnfiltrasyon",
    "Mass": "Kitle",
    "Nodule": "Nodül",
    "Pleural_Thickening": "Plevral Kalınlaşma",
    "Pneumonia": "Pnömoni (Zatürre)",
    "Pneumothorax": "Pnömotoraks",
    "No Finding": "Normal Bulgu",
    # Additional TorchXRayVision labels
    "Lung Opacity": "Akciğer Opasitesi",
    "Lung Lesion": "Akciğer Lezyonu",
    "Enlarged Cardiomediastinum": "Genişlemiş Kardiyomediastinum",
    "Fracture": "Kırık",
    "Support Devices": "Destek Cihazları",
}

# Simple explanations for patients (Turkish)
LABEL_EXPLANATIONS = {
    # ChestX-ray14 original labels
    "Atelectasis": "Akciğerin bir kısmının çökmesi veya hava alamaması durumu.",
    "Cardiomegaly": "Kalbin normalden büyük görünmesi. Çeşitli kalp hastalıklarının işareti olabilir.",
    "Consolidation": "Akciğer dokusunun sıvı veya iltihabi materyal ile dolması.",
    "Edema": "Akciğerlerde sıvı birikmesi. Kalp yetmezliği işareti olabilir.",
    "Effusion": "Akciğer zarları arasında sıvı birikmesi.",
    "Emphysema": "Akciğer hava keseciklerinin hasar görmesi. Genellikle KOAH ile ilişkili.",
    "Fibrosis": "Akciğer dokusunda skarlaşma veya kalınlaşma.",
    "Hernia": "Bir organın normal yerinden başka bir boşluğa kayması.",
    "Infiltration": "Akciğer dokusuna anormal madde birikimi.",
    "Mass": "Akciğerde kitle veya şişlik. İleri tetkik gerektirebilir.",
    "Nodule": "Akciğerde küçük yuvarlak lezyon. Takip gerektirebilir.",
    "Pleural_Thickening": "Akciğer zarının kalınlaşması.",
    "Pneumonia": "Akciğer iltihabı, genellikle enfeksiyon kaynaklı.",
    "Pneumothorax": "Akciğer zarları arasına hava kaçması, acil müdahale gerektirebilir.",
    # Additional TorchXRayVision labels
    "Lung Opacity": "Akciğerde görülen bulanıklık veya yoğunluk artışı. Çeşitli nedenleri olabilir.",
    "Lung Lesion": "Akciğer dokusunda anormal alan. İleri inceleme gerektirebilir.",
    "Enlarged Cardiomediastinum": "Kalp ve büyük damarların bulunduğu orta göğüs bölgesinin genişlemesi.",
    "Fracture": "Kemik kırığı bulgusu.",
    "Support Devices": "Tıbbi destek cihazı görüntüsü (tüp, kateter vb.).",
}

# Grad-CAM settings
GRADCAM_LAYER = "features.denseblock4"  # Target layer for DenseNet
HEATMAP_ALPHA = 0.4  # Overlay transparency
HEATMAP_COLORMAP = "jet"  # Color scheme for heatmap

# Temp file settings
TEMP_FILE_TTL_SECONDS = 300  # 5 minutes

# Threshold for "positive" finding
CONFIDENCE_THRESHOLD = 0.5

# Disclaimer text
DISCLAIMER_TR = """⚠️ ÖNEMLİ UYARI: Bu analiz sadece bilgilendirme amaçlıdır ve kesinlikle tıbbi teşhis yerine geçmez.
Görüntü analizi yapay zeka tarafından gerçekleştirilmiştir ve hata payı içerebilir.
Sağlık durumunuz hakkında kesin bilgi için mutlaka bir sağlık profesyoneline başvurunuz."""

DISCLAIMER_EN = """⚠️ IMPORTANT: This analysis is for informational purposes only and does not replace medical diagnosis.
Image analysis is performed by AI and may contain errors.
Please consult a healthcare professional for definitive information about your health."""
