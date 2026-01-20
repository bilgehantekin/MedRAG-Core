"""
ETL Pipeline Configuration
"""

from pathlib import Path
from datetime import date

# Base paths
BASE_DIR = Path(__file__).parent
DOWNLOADS_DIR = BASE_DIR / "downloads"
OUTPUT_DIR = BASE_DIR.parent.parent / "data" / "medical_knowledge"

# Create directories if they don't exist
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Current date for retrieved_date field
RETRIEVED_DATE = date.today().isoformat()

# MedlinePlus XML sources
# Files are published daily (Tue-Sat) with date in filename
# Using a recent date - update if needed
MEDLINEPLUS_XML_URLS = {
    # Compressed version (smaller download)
    "topics_compressed": "https://medlineplus.gov/xml/mplus_topics_compressed_2026-01-17.zip",
    # Uncompressed version
    "topics_en": "https://medlineplus.gov/xml/mplus_topics_2026-01-17.xml",
    # Topic groups (categories)
    "topic_groups": "https://medlineplus.gov/xml/mplus_topic_groups_2026-01-17.xml",
    # Alias for main health topics
    "health_topics": "https://medlineplus.gov/xml/mplus_topics_2026-01-17.xml"
}

# openFDA bulk download URLs
# Note: These are large files (several GB)
OPENFDA_DRUG_LABEL_URL = "https://download.open.fda.gov/drug/label/drug-label-0001-of-0012.json.zip"

# Alternative: Smaller subset for testing
OPENFDA_DRUG_LABEL_URLS = [
    "https://download.open.fda.gov/drug/label/drug-label-0001-of-0012.json.zip",
    # Add more parts as needed
]

# Category classification rules (for MedlinePlus)
MENTAL_HEALTH_KEYWORDS = {
    "depression", "anxiety", "mental health", "psychiatric", "psychological",
    "bipolar", "schizophrenia", "ptsd", "ocd", "panic", "phobia", "eating disorder",
    "stress disorder", "mood disorder", "personality disorder", "adhd", "autism"
}

SYMPTOM_KEYWORDS = {
    "symptom", "pain", "ache", "discomfort", "nausea", "fatigue", "fever",
    "headache", "dizziness", "cough", "sore throat", "rash", "itching",
    "swelling", "bleeding", "numbness", "tingling"
}

EMERGENCY_KEYWORDS = {
    "emergency", "urgent", "critical", "life-threatening", "call 911", "call 112",
    "immediate", "sudden", "severe", "heart attack", "stroke", "choking"
}

# Safety level classification
SENSITIVE_KEYWORDS = {
    "suicide", "self-harm", "depression", "anxiety", "mental health",
    "eating disorder", "addiction", "substance abuse", "overdose"
}

EMERGENCY_SAFETY_KEYWORDS = {
    "emergency", "call 911", "call 112", "life-threatening", "cardiac arrest",
    "stroke", "anaphylaxis", "severe bleeding", "unconscious"
}

# Turkish character mappings for typo generation
TR_CHAR_MAP = {
    'ğ': 'g',
    'ü': 'u',
    'ş': 's',
    'ı': 'i',
    'ö': 'o',
    'ç': 'c',
    'Ğ': 'G',
    'Ü': 'U',
    'Ş': 'S',
    'İ': 'I',
    'Ö': 'O',
    'Ç': 'C'
}

# Common medical term translations (EN -> TR)
# This is a starter dictionary - can be expanded
MEDICAL_TERM_TRANSLATIONS = {
    "headache": "baş ağrısı",
    "fever": "ateş",
    "cough": "öksürük",
    "sore throat": "boğaz ağrısı",
    "nausea": "mide bulantısı",
    "vomiting": "kusma",
    "diarrhea": "ishal",
    "constipation": "kabızlık",
    "fatigue": "yorgunluk",
    "dizziness": "baş dönmesi",
    "chest pain": "göğüs ağrısı",
    "back pain": "bel ağrısı",
    "stomach pain": "karın ağrısı",
    "abdominal pain": "karın ağrısı",
    "shortness of breath": "nefes darlığı",
    "high blood pressure": "yüksek tansiyon",
    "diabetes": "diyabet",
    "heart attack": "kalp krizi",
    "stroke": "inme",
    "allergy": "alerji",
    "asthma": "astım",
    "cold": "soğuk algınlığı",
    "flu": "grip",
    "infection": "enfeksiyon",
    "inflammation": "iltihap",
    "pain": "ağrı",
    "swelling": "şişlik",
    "rash": "döküntü",
    "itching": "kaşıntı",
    "bleeding": "kanama",
    "anxiety": "anksiyete",
    "depression": "depresyon",
    "insomnia": "uykusuzluk",
    "medication": "ilaç",
    "drug": "ilaç",
    "treatment": "tedavi",
    "symptom": "belirti",
    "disease": "hastalık",
    "condition": "durum",
    "doctor": "doktor",
    "hospital": "hastane",
    "emergency": "acil"
}

# Output file names
OUTPUT_FILES = {
    "symptoms_diseases": "symptoms_diseases_medlineplus.json",
    "medications": "medications_openfda.json"
}

# Processing limits (for testing - set to None for full processing)
MAX_RECORDS_PER_SOURCE = None  # Set to e.g., 100 for testing
