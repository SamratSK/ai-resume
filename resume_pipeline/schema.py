"""Pydantic models for the Stage 1 extraction output.

Every scalar field is either `null` (field not found in the resume) or a
`FieldValue` object carrying the verbatim value plus its evidence. Never
merge parse_quality (document-level) with confidence (field-level) — they
are intentionally separate axes.
"""
from __future__ import annotations

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field

Confidence = Literal["high", "medium", "low"]
ParseQuality = Literal["Clean", "Partial", "Failed"]
ParseMethod = Literal["docling", "text", "xml", "unsupported"]

# Keywords (checked case-insensitively) that mark a candidate additional
# field as a protected attribute. Any additional field whose field_name or
# evidence hints at these MUST be skipped silently, never extracted.
PROTECTED_ATTRIBUTE_KEYWORDS = (
    "age",
    "date of birth",
    "dob",
    "gender",
    "sex",
    "marital status",
    "married",
    "single",
    "religion",
    "caste",
    "category",  # caste/reservation category
    "nationality",
    "photo",
    "photograph",
    "appearance",
    "disability",
)


class FieldValue(BaseModel):
    raw_value: Optional[str] = None
    normalized_value: Optional[Any] = None
    scale: Optional[str] = None
    confidence: Optional[Confidence] = None
    evidence: Optional[str] = None
    assumption: Optional[str] = None


class ProjectEntry(BaseModel):
    title: Optional[str] = None
    one_liner: Optional[str] = None
    evidence: Optional[str] = None
    confidence: Optional[Confidence] = None


class ExperienceEntry(BaseModel):
    company: Optional[str] = None
    role: Optional[str] = None
    duration: Optional[str] = None
    evidence: Optional[str] = None
    confidence: Optional[Confidence] = None


class AdditionalField(BaseModel):
    field_name: str
    raw_value: Optional[str] = None
    normalized_value: Optional[Any] = None
    data_type: Optional[str] = None
    confidence: Optional[Confidence] = None
    evidence: Optional[str] = None


class ResumeRecord(BaseModel):
    file: str
    method: ParseMethod
    parse_quality: ParseQuality

    full_name: Optional[FieldValue] = None
    email: Optional[FieldValue] = None
    phone: Optional[FieldValue] = None
    college: Optional[FieldValue] = None
    degree: Optional[FieldValue] = None
    branch: Optional[FieldValue] = None
    graduation_year: Optional[FieldValue] = None
    cgpa: Optional[FieldValue] = None

    skills: List[FieldValue] = Field(default_factory=list)
    projects: List[ProjectEntry] = Field(default_factory=list)
    experience: List[ExperienceEntry] = Field(default_factory=list)
    certifications: List[FieldValue] = Field(default_factory=list)
    additional_fields: List[AdditionalField] = Field(default_factory=list)

    anomalies: List[str] = Field(default_factory=list)


SCALAR_FIELD_NAMES = (
    "full_name",
    "email",
    "phone",
    "college",
    "degree",
    "branch",
    "graduation_year",
    "cgpa",
)
