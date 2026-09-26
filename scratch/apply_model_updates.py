# Updates to document.py, analysis.py, and __init__.py

# 1. Update document.py
with open("src/before_you_pay/models/document.py", encoding="utf-8") as f_in:
    doc_content = f_in.read()

target_ocr_line = """class OcrLine(BaseModel):
    \"\"\"Recognized line of text on a page.\"\"\"

    model_config = ConfigDict(frozen=True, extra="forbid")

    line_id: UUID = Field(default_factory=uuid4)
    page_id: UUID
    document_id: UUID
    line_number: int = Field(..., ge=1)
    text: str = Field(..., min_length=1)
    bounding_box: BoundingBox
    confidence: float = Field(..., ge=0.0, le=1.0)"""

replacement_ocr_line = """class OcrLine(BaseModel):
    \"\"\"Recognized line of text on a page.\"\"\"

    model_config = ConfigDict(frozen=True, extra="forbid")

    line_id: UUID = Field(default_factory=uuid4)
    page_id: UUID
    document_id: UUID
    line_number: int = Field(..., ge=1)
    text: str = Field(..., min_length=1)
    raw_text: str | None = None
    bounding_box: BoundingBox
    confidence: float = Field(..., ge=0.0, le=1.0)
    is_unreliable: bool = False"""

assert target_ocr_line in doc_content, "target_ocr_line not found"
doc_content = doc_content.replace(target_ocr_line, replacement_ocr_line)

target_ocr_res = """class OcrResult(BaseModel):
    \"\"\"Complete multi-page OCR extraction payload for a document.\"\"\"

    model_config = ConfigDict(frozen=True, extra="forbid")

    document_id: UUID
    pages: list[OcrPage] = Field(..., min_length=1)
    engine_name: str
    engine_version: str | None = None
    processed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))"""

replacement_ocr_res = """class OcrResult(BaseModel):
    \"\"\"Complete multi-page OCR extraction payload for a document.\"\"\"

    model_config = ConfigDict(frozen=True, extra="forbid")

    document_id: UUID
    pages: list[OcrPage] = Field(..., min_length=1)
    engine_name: str
    engine_version: str | None = None
    processed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    recovery_attempted: bool = False
    recovery_pass: int = 1
    quality: Any | None = None"""

assert target_ocr_res in doc_content, "target_ocr_res not found"
doc_content = doc_content.replace(target_ocr_res, replacement_ocr_res)

with open("src/before_you_pay/models/document.py", "w", encoding="utf-8") as f_out:
    f_out.write(doc_content)
print("Updated document.py successfully")

# 2. Update analysis.py
with open("src/before_you_pay/models/analysis.py", encoding="utf-8") as f_in:
    analysis_content = f_in.read()

# Add OcrLine import if needed
if "OcrLine" not in analysis_content:
    analysis_content = analysis_content.replace(
        "from before_you_pay.models.document import (",
        "from before_you_pay.models.document import (\n    OcrLine,",
    )

new_enums = """class AnalysisState(StrEnum):
    \"\"\"Explicit lifecycle states separating extraction findings from OCR quality.\"\"\"

    FINANCIAL_DATA_FOUND = "FINANCIAL_DATA_FOUND"
    NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR = "NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR"
    OCR_UNRELIABLE = "OCR_UNRELIABLE"
    DOCUMENT_UNREADABLE = "DOCUMENT_UNREADABLE"
    EXTRACTION_INCONCLUSIVE = "EXTRACTION_INCONCLUSIVE"


class OCRQualityStatus(StrEnum):
    \"\"\"Deterministic OCR recognition quality status.\"\"\"

    GOOD = "GOOD"
    DEGRADED = "DEGRADED"
    UNRELIABLE = "UNRELIABLE"


class OCRQualityResult(BaseModel):
    \"\"\"Deterministic assessment of OCR line plausibility, density, and garbage ratios.\"\"\"

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: OCRQualityStatus
    score: float = Field(..., ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    line_count: int = Field(default=0, ge=0)
    character_count: int = Field(default=0, ge=0)
    word_count: int = Field(default=0, ge=0)
    alphanumeric_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    garbage_token_ratio: float = Field(default=0.0, ge=0.0, le=1.0)


class ValidationStatus(StrEnum):"""

assert "class ValidationStatus(StrEnum):" in analysis_content, "ValidationStatus not found"
analysis_content = analysis_content.replace("class ValidationStatus(StrEnum):", new_enums)

target_res_summary = """class ResultSummary(BaseModel):
    \"\"\"High-level summary of document analysis.\"\"\"

    model_config = ConfigDict(frozen=True, extra="forbid")

    headline: str = Field(..., min_length=1)
    overall_status: DecisionStatus
    total_flags: int = Field(..., ge=0)
    requires_human_verification: bool = Field(default=True)"""

replacement_res_summary = """class ResultSummary(BaseModel):
    \"\"\"High-level summary of document analysis.\"\"\"

    model_config = ConfigDict(frozen=True, extra="forbid")

    headline: str = Field(..., min_length=1)
    overall_status: DecisionStatus
    total_flags: int = Field(..., ge=0)
    requires_human_verification: bool = Field(default=True)
    analysis_state: AnalysisState = Field(default=AnalysisState.FINANCIAL_DATA_FOUND)
    ocr_quality: OCRQualityResult | None = None"""

assert target_res_summary in analysis_content, "ResultSummary not found"
analysis_content = analysis_content.replace(target_res_summary, replacement_res_summary)

target_final_res = """class FinalDecisionSupportResult(BaseModel):
    \"\"\"Complete, evidence-backed decision support payload returned to the user.\"\"\"

    model_config = ConfigDict(frozen=True, extra="forbid")

    result_id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    user_id: UUID
    summary: ResultSummary
    flags: list[DecisionFlag] = Field(default_factory=list)
    reasoning_claims: list[ReasoningClaim] = Field(default_factory=list)
    validation_checks: list[ValidationCheck] = Field(default_factory=list)
    document: StructuredFinancialDocument | None = None
    raw_ocr_lines: list[str] = Field(default_factory=list)
    disclaimer: str = Field(default=STANDARD_DISCLAIMER)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))"""

replacement_final_res = """class FinalDecisionSupportResult(BaseModel):
    \"\"\"Complete, evidence-backed decision support payload returned to the user.\"\"\"

    model_config = ConfigDict(frozen=True, extra="forbid")

    result_id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    user_id: UUID
    summary: ResultSummary
    flags: list[DecisionFlag] = Field(default_factory=list)
    reasoning_claims: list[ReasoningClaim] = Field(default_factory=list)
    validation_checks: list[ValidationCheck] = Field(default_factory=list)
    document: StructuredFinancialDocument | None = None
    raw_ocr_lines: list[str] = Field(default_factory=list)
    ocr_lines: list[OcrLine] = Field(default_factory=list)
    analysis_state: AnalysisState = Field(default=AnalysisState.FINANCIAL_DATA_FOUND)
    ocr_quality: OCRQualityResult | None = None
    disclaimer: str = Field(default=STANDARD_DISCLAIMER)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))"""

assert target_final_res in analysis_content, "FinalDecisionSupportResult not found"
analysis_content = analysis_content.replace(target_final_res, replacement_final_res)

with open("src/before_you_pay/models/analysis.py", "w", encoding="utf-8") as f_out:
    f_out.write(analysis_content)
print("Updated analysis.py successfully")

# 3. Update __init__.py
with open("src/before_you_pay/models/__init__.py", encoding="utf-8") as f_in:
    init_content = f_in.read()

target_init_import = """from before_you_pay.models.analysis import (
    ClaimType,"""

replacement_init_import = """from before_you_pay.models.analysis import (
    AnalysisState,
    OCRQualityStatus,
    OCRQualityResult,
    ClaimType,"""

assert target_init_import in init_content, "target_init_import not found"
init_content = init_content.replace(target_init_import, replacement_init_import)

target_init_all = """    # Analysis & Results
    "StandardError","""

replacement_init_all = """    # Analysis & Results
    "AnalysisState",
    "OCRQualityStatus",
    "OCRQualityResult",
    "StandardError","""

assert target_init_all in init_content, "target_init_all not found"
init_content = init_content.replace(target_init_all, replacement_init_all)

with open("src/before_you_pay/models/__init__.py", "w", encoding="utf-8") as f_out:
    f_out.write(init_content)
print("Updated __init__.py successfully")
