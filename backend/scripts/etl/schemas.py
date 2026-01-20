"""
Pydantic Schemas for Medical Knowledge Data Validation
Matches the existing JSON schema used in the project
"""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator
from datetime import date


class SymptomDiseaseEntry(BaseModel):
    """Schema for symptoms_diseases.json entries"""

    id: str = Field(..., description="Unique identifier")
    title: str = Field(..., description="English title")
    title_tr: str = Field(default="", description="Turkish title")
    category: str = Field(..., description="Category: symptoms, diseases, mental_health")
    source_name: str = Field(..., description="Source name (e.g., MedlinePlus - NIH)")
    source_url: str = Field(default="", description="Source URL")
    retrieved_date: str = Field(..., description="Date retrieved (YYYY-MM-DD)")
    content: str = Field(..., description="Main content/description")

    # Optional structured fields
    symptoms: List[str] = Field(default_factory=list)
    causes: List[str] = Field(default_factory=list)
    what_to_do: List[str] = Field(default_factory=list)
    do_not: List[str] = Field(default_factory=list)
    red_flags: List[str] = Field(default_factory=list)
    when_to_see_doctor: str = Field(default="")

    # Keywords
    keywords_en: List[str] = Field(default_factory=list)
    keywords_tr: List[str] = Field(default_factory=list)
    typos_tr: List[str] = Field(default_factory=list)

    # Metadata
    jurisdiction: str = Field(default="TR")
    safety_level: str = Field(default="general")

    # Optional crisis info for mental health
    crisis_info: Optional[str] = None

    @field_validator('category')
    @classmethod
    def validate_category(cls, v):
        allowed = {'symptoms', 'diseases', 'mental_health', 'emergency', 'general'}
        if v not in allowed:
            raise ValueError(f'category must be one of {allowed}')
        return v

    @field_validator('safety_level')
    @classmethod
    def validate_safety_level(cls, v):
        allowed = {'general', 'sensitive', 'emergency', 'medication'}
        if v not in allowed:
            raise ValueError(f'safety_level must be one of {allowed}')
        return v

    class Config:
        extra = 'allow'  # Allow extra fields for forward compatibility


class DosageInfo(BaseModel):
    """Dosage information schema"""
    adults: Optional[str] = None
    children: Optional[str] = None
    max_daily: Optional[str] = None
    min_interval: Optional[str] = None
    note: Optional[str] = None

    class Config:
        extra = 'allow'


class MedicationEntry(BaseModel):
    """Schema for medications.json entries"""

    id: str = Field(..., description="Unique identifier")
    title: str = Field(..., description="Generic name (English)")
    title_tr: str = Field(default="", description="Turkish name")
    category: str = Field(default="medications")
    drug_class: str = Field(default="", description="Drug classification")
    source_name: str = Field(..., description="Source name")
    source_url: str = Field(default="", description="Source URL or reference")
    retrieved_date: str = Field(..., description="Date retrieved")
    content: str = Field(..., description="Summary/indications")

    # Drug-specific fields
    uses: List[str] = Field(default_factory=list)
    dosage_info: Optional[Union[DosageInfo, Dict[str, Any], str]] = None
    side_effects: List[str] = Field(default_factory=list)
    contraindications: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    drug_interactions: List[str] = Field(default_factory=list)
    overdose_warning: str = Field(default="")

    # Keywords
    keywords_en: List[str] = Field(default_factory=list)
    keywords_tr: List[str] = Field(default_factory=list)
    typos_tr: List[str] = Field(default_factory=list)
    brand_examples_tr: List[str] = Field(default_factory=list)

    # Safety
    safety_disclaimer: str = Field(
        default="Bu bilgiler yalnızca genel bilgilendirme amaçlıdır. İlaç kullanmadan önce mutlaka doktorunuza veya eczacınıza danışın."
    )
    jurisdiction: str = Field(default="TR")
    safety_level: str = Field(default="medication")

    # Additional metadata
    source_jurisdiction: Optional[str] = Field(
        default=None,
        description="Jurisdiction of source data (e.g., US for FDA)"
    )

    @field_validator('category')
    @classmethod
    def validate_category(cls, v):
        if v != 'medications':
            raise ValueError('category must be "medications"')
        return v

    class Config:
        extra = 'allow'


class ETLResult(BaseModel):
    """Result of ETL processing"""
    source: str
    total_records: int
    successful: int
    failed: int
    duplicates_removed: int
    output_file: Optional[str] = None
    errors: List[str] = Field(default_factory=list)


def validate_symptom_disease_entry(data: dict) -> tuple[bool, Optional[SymptomDiseaseEntry], Optional[str]]:
    """
    Validate a symptom/disease entry
    Returns: (is_valid, validated_entry, error_message)
    """
    try:
        entry = SymptomDiseaseEntry(**data)
        return True, entry, None
    except Exception as e:
        return False, None, str(e)


def validate_medication_entry(data: dict) -> tuple[bool, Optional[MedicationEntry], Optional[str]]:
    """
    Validate a medication entry
    Returns: (is_valid, validated_entry, error_message)
    """
    try:
        entry = MedicationEntry(**data)
        return True, entry, None
    except Exception as e:
        return False, None, str(e)
