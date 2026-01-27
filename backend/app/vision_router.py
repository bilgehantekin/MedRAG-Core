"""
Vision Router - Drug Image Analysis Endpoint

Simplified approach:
1. OCR with Tesseract to extract text from drug image
2. Match drug name from drugs.json database
3. Send to Groq LLM for intelligent response
"""

import base64
import io
import json
import logging
import re
from pathlib import Path
from typing import Optional, List
from difflib import SequenceMatcher

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from PIL import Image

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vision", tags=["Vision"])

# Paths
VISION_DIR = Path(__file__).parent / "vision"
DATA_DIR = VISION_DIR / "data"
DRUGS_JSON_PATH = DATA_DIR / "drug_knowledge_base" / "drugs.json"

# Load drugs database
_drugs_db: List[dict] = []


def load_drugs_db():
    """Load drugs database from JSON file."""
    global _drugs_db
    if not _drugs_db and DRUGS_JSON_PATH.exists():
        try:
            with open(DRUGS_JSON_PATH, "r", encoding="utf-8") as f:
                _drugs_db = json.load(f)
            logger.info(f"Loaded {len(_drugs_db)} drugs from database")
        except Exception as e:
            logger.error(f"Failed to load drugs database: {e}")
    return _drugs_db


class ImageAnalysisRequest(BaseModel):
    """Request model for base64 image analysis."""
    image_base64: str
    format: Optional[str] = "jpeg"
    user_question: Optional[str] = None  # Optional user question about the drug


class ImageAnalysisResponse(BaseModel):
    """Response model for image analysis."""
    success: bool
    drug_name: Optional[str] = None
    active_ingredients: List[str] = []
    dosage_form: Optional[str] = None
    strength: Optional[str] = None
    manufacturer: Optional[str] = None
    explanation: Optional[str] = None
    confidence: Optional[str] = None
    warnings: List[str] = []
    extracted_text: Optional[str] = None  # OCR result for debugging
    disclaimer: str = "⚠️ Bu bilgiler eğitim amaçlıdır, tıbbi tavsiye değildir. İlaç kullanmadan önce mutlaka doktorunuza veya eczacınıza danışın."
    error: Optional[str] = None
    processing_time_ms: Optional[float] = None


def preprocess_image_for_ocr(image: Image.Image) -> list:
    """
    Preprocess image for better OCR results.
    Returns multiple processed versions to try.
    """
    import numpy as np

    processed_images = []

    # Convert to numpy array
    img_array = np.array(image)

    # 1. Original image
    processed_images.append(image)

    try:
        import cv2

        # 2. Grayscale
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        processed_images.append(Image.fromarray(gray))

        # 3. Increase contrast with CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        processed_images.append(Image.fromarray(enhanced))

        # 4. Binary threshold (Otsu's method)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        processed_images.append(Image.fromarray(binary))

        # 5. Adaptive threshold
        adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                         cv2.THRESH_BINARY, 11, 2)
        processed_images.append(Image.fromarray(adaptive))

        # 6. Denoise + threshold
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        _, denoised_binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        processed_images.append(Image.fromarray(denoised_binary))

        logger.info(f"Created {len(processed_images)} preprocessed image variants")

    except ImportError:
        logger.warning("OpenCV not available, using original image only")
    except Exception as e:
        logger.warning(f"Preprocessing error: {e}")

    return processed_images


def extract_text_from_image(image_bytes: bytes) -> str:
    """
    Extract text from image using Tesseract OCR.
    Uses multiple preprocessing techniques and PSM modes for better results.
    """
    try:
        import pytesseract

        # Open image
        image = Image.open(io.BytesIO(image_bytes))

        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Get preprocessed versions
        processed_images = preprocess_image_for_ocr(image)

        all_text = set()  # Use set to avoid duplicates

        # PSM modes to try
        # PSM 6: Assume a single uniform block of text
        # PSM 11: Sparse text. Find as much text as possible
        # PSM 3: Fully automatic page segmentation (default)
        # PSM 4: Single column of text
        psm_modes = [6, 11, 3, 4]

        for proc_img in processed_images:
            for psm in psm_modes:
                try:
                    # Try with Turkish + English
                    config = f'--psm {psm} --oem 3'
                    text = pytesseract.image_to_string(proc_img, lang='tur+eng', config=config)
                    if text.strip():
                        # Clean and add words
                        words = text.strip().split()
                        for word in words:
                            # Filter out garbage (non-alphanumeric short strings)
                            cleaned = re.sub(r'[^A-Za-zÇçĞğİıÖöŞşÜü0-9]', '', word)
                            if len(cleaned) >= 3:  # Keep words with 3+ characters
                                all_text.add(cleaned)
                except Exception:
                    continue

        # Also try to find specific drug-related patterns
        drug_patterns = [
            r'\b(PAROL|PARACETAMOL|PARASETAMOL)\b',
            r'\b(NUROFEN|IBUPROFEN|İBUPROFEN)\b',
            r'\b(AUGMENTIN|AMOXİSİLİN|AMOXICILLIN)\b',
            r'\b(ASPIRIN|ASPİRİN)\b',
            r'\b(MAJEZIK|MAJEZİK)\b',
            r'\b(GRIPIN|GRİPİN)\b',
            r'\b(TYLOL|TALCID)\b',
            r'\b(\d+\s*MG|\d+\s*ML)\b',
            r'\b(TABLET|KAPSÜL|ŞURUP|DAMLA|JEL|KREM)\b',
        ]

        # Try pattern matching on original OCR
        for proc_img in processed_images[:3]:  # First 3 variants
            try:
                config = '--psm 11 --oem 3'
                raw_text = pytesseract.image_to_string(proc_img, lang='tur+eng', config=config)
                raw_upper = raw_text.upper()

                for pattern in drug_patterns:
                    matches = re.findall(pattern, raw_upper, re.IGNORECASE)
                    for match in matches:
                        if isinstance(match, tuple):
                            match = match[0]
                        all_text.add(match)
            except Exception:
                continue

        # Combine all results
        combined_text = ' '.join(all_text)

        logger.info(f"OCR extracted {len(all_text)} unique words: {combined_text[:300]}...")
        return combined_text

    except ImportError:
        logger.warning("pytesseract not installed, trying without OCR")
        return ""
    except Exception as e:
        logger.error(f"OCR error: {e}")
        return ""


def normalize_ocr_errors(text: str) -> str:
    """
    Normalize common OCR errors.
    """
    # Common OCR confusions
    replacements = {
        '0': 'O',  # zero -> O
        '1': 'I',  # one -> I
        '|': 'I',  # pipe -> I
        '!': 'I',  # exclamation -> I
        '$': 'S',  # dollar -> S
        '5': 'S',  # five -> S (sometimes)
        '8': 'B',  # eight -> B
        '@': 'A',  # at -> A
        '3': 'E',  # three -> E
        '6': 'G',  # six -> G
    }

    result = text.upper()
    for old, new in replacements.items():
        result = result.replace(old, new)

    return result


def find_drug_in_text(text: str, drugs_db: List[dict]) -> Optional[dict]:
    """
    Find matching drug from extracted text using multiple strategies.
    Priority: Drug name > Manufacturer+Ingredient > Ingredient only > Fuzzy
    """
    if not text or not drugs_db:
        return None

    text_upper = text.upper()
    text_normalized = normalize_ocr_errors(text_upper)  # Also try with OCR error corrections
    text_clean = re.sub(r'[^A-Za-zÇçĞğİıÖöŞşÜü0-9\s]', ' ', text_upper)
    text_clean_normalized = re.sub(r'[^A-Za-zÇçĞğİıÖöŞşÜü\s]', ' ', text_normalized)
    words = set(text_clean.split())
    words_normalized = set(text_clean_normalized.split())
    all_words = words | words_normalized

    logger.info(f"Searching for drug in text. Words found: {list(all_words)[:30]}")

    # Candidates with scores
    candidates = []

    for drug in drugs_db:
        drug_name = drug.get("drug_name", "")
        drug_name_upper = drug_name.upper()
        manufacturer = drug.get("manufacturer", "").upper()
        ingredients = [i.upper() for i in drug.get("active_ingredients", [])]

        score = 0

        # Strategy 1: Exact drug name match (highest priority)
        if drug_name_upper in text_upper or drug_name_upper in text_normalized:
            logger.info(f"Exact match found: {drug_name}")
            return drug

        # Strategy 2: Drug name as a word
        if drug_name_upper in all_words:
            logger.info(f"Word match found: {drug_name}")
            return drug

        # Check for ingredient match
        ingredient_match = False
        matched_ingredient = None
        for ingredient in ingredients:
            if ingredient in text_upper or ingredient in text_normalized:
                ingredient_match = True
                matched_ingredient = ingredient
                score += 50
                break
            # Partial match - ingredient contains word or vice versa
            for word in all_words:
                if len(word) >= 5:
                    if word in ingredient or ingredient in word:
                        ingredient_match = True
                        matched_ingredient = ingredient
                        score += 40
                        break
                    # Fuzzy ingredient match
                    ratio = SequenceMatcher(None, word, ingredient).ratio()
                    if ratio > 0.75:
                        ingredient_match = True
                        matched_ingredient = ingredient
                        score += int(ratio * 45)
                        break
            if ingredient_match:
                break

        # Check manufacturer match
        manufacturer_match = False
        if manufacturer:
            if manufacturer in text_upper or manufacturer in text_normalized:
                manufacturer_match = True
                score += 30
            else:
                # Partial manufacturer match (e.g., "ATAB" -> "ATABAY")
                for word in all_words:
                    if len(word) >= 3:
                        if word in manufacturer or manufacturer.startswith(word):
                            manufacturer_match = True
                            score += 25
                            break
                        # Fuzzy manufacturer match
                        ratio = SequenceMatcher(None, word, manufacturer).ratio()
                        if ratio > 0.6:
                            manufacturer_match = True
                            score += int(ratio * 20)
                            break

        # Strategy 3: Both manufacturer and ingredient match = high confidence
        if manufacturer_match and ingredient_match:
            score += 30  # Bonus for both matching
            logger.info(f"Manufacturer+Ingredient match: {manufacturer} + {matched_ingredient} -> {drug_name} (score: {score})")

        # Fuzzy match on drug name (more aggressive)
        for word in all_words:
            if len(word) >= 3:
                ratio = SequenceMatcher(None, word, drug_name_upper).ratio()
                if ratio > 0.6:  # Lower threshold
                    score += int(ratio * 40)
                # Also check if drug name is a substring
                if len(drug_name_upper) >= 4 and drug_name_upper[:4] in word:
                    score += 20

        if score > 0:
            candidates.append((drug, score))

    # Sort by score and return best match
    if candidates:
        candidates.sort(key=lambda x: x[1], reverse=True)
        best_drug, best_score = candidates[0]
        logger.info(f"Best match: {best_drug['drug_name']} (score: {best_score})")
        return best_drug

    return None


def generate_drug_response(drug_info: dict, user_question: Optional[str] = None) -> str:
    """
    Generate response about the drug using Groq LLM.
    """
    import os
    from groq import Groq

    groq_api_key = os.getenv("GROQ_API_KEY", "")
    if not groq_api_key:
        # Fallback to simple response if no API key
        return generate_simple_response(drug_info)

    try:
        client = Groq(api_key=groq_api_key)

        # Build context about the drug
        drug_context = f"""
İlaç Bilgisi:
- İlaç Adı: {drug_info.get('drug_name', 'Bilinmiyor')}
- Etken Madde: {', '.join(drug_info.get('active_ingredients', []))}
- Form: {drug_info.get('dosage_form', 'Bilinmiyor')}
- Dozaj: {', '.join(drug_info.get('strengths', []))}
- Üretici: {drug_info.get('manufacturer', 'Bilinmiyor')}
- Kullanım Alanı: {drug_info.get('indications', '')}
- Kullanım Şekli: {drug_info.get('usage', '')}
- Uyarılar: {', '.join(drug_info.get('warnings', []))}
- Yan Etkiler: {', '.join(drug_info.get('side_effects', []))}
- İlaç Etkileşimleri: {', '.join(drug_info.get('interactions', []))}
- Saklama: {drug_info.get('storage', '')}
- Reçete Durumu: {drug_info.get('prescription_status', '')}
"""

        # Build prompt
        if user_question:
            prompt = f"""Kullanıcı bir ilaç görseli yükledi ve şu soruyu sordu: "{user_question}"

{drug_context}

Lütfen kullanıcının sorusuna bu ilaç bilgilerini kullanarak Türkçe yanıt ver.
Yanıtın bilgilendirici, güvenli ve anlaşılır olsun.
Kesinlikle tıbbi tavsiye verme, sadece genel bilgi sun.
"""
        else:
            prompt = f"""Kullanıcı bir ilaç görseli yükledi. Tespit edilen ilaç hakkında bilgi ver.

{drug_context}

Lütfen bu ilaç hakkında Türkçe, kullanıcı dostu bir özet hazırla:
1. İlacın ne olduğunu ve ne için kullanıldığını açıkla
2. Önemli uyarıları belirt
3. Yaygın yan etkileri listele
4. Kullanım önerilerini paylaş

Yanıtın bilgilendirici ve anlaşılır olsun. Kesinlikle tıbbi tavsiye verme.
"""

        response = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            messages=[
                {
                    "role": "system",
                    "content": "Sen bir sağlık bilgi asistanısın. İlaçlar hakkında genel bilgi verirsin ama kesinlikle tıbbi tavsiye vermezsin. Her zaman kullanıcıyı doktora veya eczacıya yönlendirirsin."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1024
        )

        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return generate_simple_response(drug_info)


def generate_simple_response(drug_info: dict) -> str:
    """
    Generate a simple response without LLM.
    """
    response = f"**{drug_info.get('drug_name', 'İlaç')}** hakkında bilgiler:\n\n"

    if drug_info.get('indications'):
        response += f"**Kullanım Alanı:** {drug_info['indications']}\n\n"

    if drug_info.get('usage'):
        response += f"**Kullanım Şekli:** {drug_info['usage']}\n\n"

    if drug_info.get('warnings'):
        response += "**Uyarılar:**\n"
        for warning in drug_info['warnings']:
            response += f"• {warning}\n"
        response += "\n"

    if drug_info.get('side_effects'):
        response += "**Olası Yan Etkiler:**\n"
        for effect in drug_info['side_effects'][:5]:
            response += f"• {effect}\n"

    return response


@router.post("/analyze-image", response_model=ImageAnalysisResponse)
async def analyze_image_base64(request: ImageAnalysisRequest):
    """
    Analyze a drug image from base64 encoded string.

    Pipeline:
    1. Decode base64 image
    2. Extract text with OCR
    3. Match drug from database
    4. Generate response with Groq LLM
    """
    import time
    start_time = time.time()

    try:
        # Load drugs database
        drugs_db = load_drugs_db()
        if not drugs_db:
            return ImageAnalysisResponse(
                success=False,
                error="İlaç veritabanı yüklenemedi"
            )

        # Decode base64 image
        try:
            image_bytes = base64.b64decode(request.image_base64)
        except Exception as e:
            return ImageAnalysisResponse(
                success=False,
                error=f"Görsel çözümlenemedi: {str(e)}"
            )

        # Extract text with OCR
        extracted_text = extract_text_from_image(image_bytes)

        if not extracted_text:
            return ImageAnalysisResponse(
                success=False,
                error="Görselden metin okunamadı. Lütfen daha net bir görsel deneyin.",
                extracted_text=""
            )

        # Find matching drug
        drug_info = find_drug_in_text(extracted_text, drugs_db)

        if not drug_info:
            return ImageAnalysisResponse(
                success=False,
                error=f"İlaç tespit edilemedi. Okunan metin: {extracted_text[:100]}...",
                extracted_text=extracted_text
            )

        # Generate response with Groq
        explanation = generate_drug_response(drug_info, request.user_question)

        processing_time = (time.time() - start_time) * 1000

        return ImageAnalysisResponse(
            success=True,
            drug_name=drug_info.get("drug_name"),
            active_ingredients=drug_info.get("active_ingredients", []),
            dosage_form=drug_info.get("dosage_form"),
            strength=", ".join(drug_info.get("strengths", [])),
            manufacturer=drug_info.get("manufacturer"),
            explanation=explanation,
            confidence="Yüksek" if drug_info.get("drug_name", "").upper() in extracted_text.upper() else "Orta",
            warnings=drug_info.get("warnings", []),
            extracted_text=extracted_text[:200],
            processing_time_ms=processing_time
        )

    except Exception as e:
        logger.error(f"Image analysis error: {e}")
        return ImageAnalysisResponse(
            success=False,
            error=f"Görüntü analizi sırasında hata: {str(e)}"
        )


@router.post("/analyze-upload", response_model=ImageAnalysisResponse)
async def analyze_image_upload(
    file: UploadFile = File(...),
    user_question: Optional[str] = None
):
    """
    Analyze a drug image from file upload.
    """
    import time
    start_time = time.time()

    try:
        # Validate file type
        valid_types = {"image/jpeg", "image/png", "image/jpg", "image/webp"}
        if file.content_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Geçersiz dosya türü: {file.content_type}"
            )

        # Read file
        image_bytes = await file.read()

        if not image_bytes:
            raise HTTPException(status_code=400, detail="Boş dosya")

        # Convert to base64 and use the same logic
        image_base64 = base64.b64encode(image_bytes).decode()

        request = ImageAnalysisRequest(
            image_base64=image_base64,
            user_question=user_question
        )

        return await analyze_image_base64(request)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload analysis error: {e}")
        return ImageAnalysisResponse(
            success=False,
            error=f"Görüntü analizi sırasında hata: {str(e)}"
        )


@router.get("/health")
async def vision_health():
    """Check if vision service is ready."""
    drugs_db = load_drugs_db()

    # Check pytesseract
    tesseract_ok = False
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        tesseract_ok = True
    except:
        pass

    return {
        "status": "healthy" if drugs_db and tesseract_ok else "degraded",
        "drugs_loaded": len(drugs_db),
        "tesseract_available": tesseract_ok,
        "drugs_json_path": str(DRUGS_JSON_PATH),
        "drugs_json_exists": DRUGS_JSON_PATH.exists()
    }


@router.get("/drugs")
async def list_drugs():
    """List all drugs in the database."""
    drugs_db = load_drugs_db()
    return {
        "count": len(drugs_db),
        "drugs": [{"name": d["drug_name"], "ingredients": d.get("active_ingredients", [])} for d in drugs_db]
    }
