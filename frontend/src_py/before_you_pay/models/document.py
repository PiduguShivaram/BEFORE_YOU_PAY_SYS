"""Document, OCR, and financial extraction domain models."""

import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CoordinateUnit(StrEnum):
    """Unit representation for bounding box coordinates."""

    NORMALIZED_PERCENTAGE = "normalized_percentage"
    PIXELS = "pixels"


class BoundingBox(BaseModel):
    """Normalized spatial bounding box on a document page (0.0 to 1.0)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)
    width: float = Field(..., gt=0.0, le=1.0)
    height: float = Field(..., gt=0.0, le=1.0)
    coordinate_unit: CoordinateUnit = Field(default=CoordinateUnit.NORMALIZED_PERCENTAGE)

    @model_validator(mode="after")
    def validate_spatial_bounds(self) -> "BoundingBox":
        if self.coordinate_unit == CoordinateUnit.NORMALIZED_PERCENTAGE:
            if (self.x + self.width) > 1.0001:
                raise ValueError(
                    f"Bounding box exceeds horizontal boundary: x ({self.x}) + width ({self.width}) > 1.0"
                )
            if (self.y + self.height) > 1.0001:
                raise ValueError(
                    f"Bounding box exceeds vertical boundary: y ({self.y}) + height ({self.height}) > 1.0"
                )
        return self


class DocumentClassification(StrEnum):
    """Supported financial document categories."""

    QUOTATION = "quotation"
    COST_BREAKDOWN = "cost_breakdown"
    BILL = "bill"
    CONTRACT = "contract"
    SUBSCRIPTION = "subscription"
    WARRANTY = "warranty"
    INVOICE = "invoice"
    OTHER = "other"


class ComponentCategory(StrEnum):
    """Categorization of individual components in quotations and breakdowns."""

    BASE_PRICE = "base_price"              # Ex-showroom, vehicle base price, base unit price
    TAX = "tax"                            # TCS, GST, VAT, cess
    INSURANCE = "insurance"                # Vehicle insurance, comprehensive insurance
    REGISTRATION = "registration"          # R.C., road tax, registration fees
    WARRANTY = "warranty"                  # Extended warranty, guarantee
    ACCESSORY_OR_FEE = "accessory_or_fee"  # Temp + MSRP/HSRP, handling, logistics, accessories
    DISCOUNT = "discount"                  # Offer, extra offer, dealer discount, rebate
    SUBTOTAL = "subtotal"                  # Stated subtotal / total before offers
    TOTAL = "total"                        # Quoted total / on-road total
    OTHER = "other"


class ChargeNature(StrEnum):
    """Nature of the financial component: positive charge vs negative deduction."""

    CHARGE = "charge"
    DEDUCTION = "deduction"


class DocumentMetadata(BaseModel):
    """Metadata representing an ingested physical document."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document_id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    file_name: str = Field(..., min_length=1)
    mime_type: str = Field(..., min_length=3)
    sha256_hash: str = Field(..., min_length=64, max_length=64)
    total_pages: int = Field(..., ge=1)
    file_size_bytes: int = Field(..., ge=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    document_classification: DocumentClassification = Field(default=DocumentClassification.OTHER)

    @field_validator("sha256_hash")
    @classmethod
    def validate_sha256_hex(cls, v: str) -> str:
        if not re.fullmatch(r"[a-fA-F0-9]{64}", v):
            raise ValueError("sha256_hash must be a valid 64-character hexadecimal string")
        return v.lower()


class OcrLine(BaseModel):
    """Recognized line of text on a page."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    line_id: UUID = Field(default_factory=uuid4)
    page_id: UUID
    document_id: UUID
    line_number: int = Field(..., ge=1)
    text: str = Field(..., min_length=1)
    raw_text: str | None = None
    bounding_box: BoundingBox
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    is_unreliable: bool = False


class OcrPage(BaseModel):
    """Single page containing physical dimensions and recognized lines."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    page_id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    page_number: int = Field(..., ge=1)
    width: int = Field(..., ge=1)
    height: int = Field(..., ge=1)
    dpi: int | None = Field(default=None, ge=1)
    lines: list[OcrLine] = Field(default_factory=list)


class OcrResult(BaseModel):
    """Complete multi-page OCR extraction payload for a document."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document_id: UUID
    pages: list[OcrPage] = Field(..., min_length=1)
    engine_name: str
    engine_version: str | None = None
    processed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    recovery_attempted: bool = False
    recovery_pass: int = 1
    quality: Any | None = None


class FieldProvenance(BaseModel):
    """Traceability pointer linking an extracted financial field back to raw OCR text."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document_id: UUID
    page_id: UUID
    ocr_line_ids: list[UUID] = Field(..., min_length=1)
    bounding_box: BoundingBox | None = None
    raw_text: str = Field(..., min_length=1)


class ExtractedField(BaseModel):
    """Individual typed financial field with value normalization and source provenance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    field_id: UUID = Field(default_factory=uuid4)
    field_key: str = Field(..., min_length=1)
    normalized_value: Any
    unit_or_currency: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    provenance: FieldProvenance


class LineItem(BaseModel):
    """Itemized transaction line item with component-level field provenance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    item_id: UUID = Field(default_factory=uuid4)
    description: ExtractedField
    quantity: ExtractedField | None = None
    unit_price: ExtractedField | None = None
    total_price: ExtractedField
    mrp: ExtractedField | None = None
    discount: ExtractedField | None = None
    discounts: list[ExtractedField] = Field(default_factory=list)
    taxes: list[ExtractedField] = Field(default_factory=list)


class FinancialComponent(BaseModel):
    """Generic financial component representing a charge, fee, tax, or deduction in quotations and breakdowns."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    component_id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=1)
    amount: ExtractedField
    category: ComponentCategory = Field(default=ComponentCategory.OTHER)
    charge_nature: ChargeNature = Field(default=ChargeNature.CHARGE)
    is_optional: bool = Field(default=False)


class StructuredFinancialDocument(BaseModel):
    """Normalized structured representation of a financial document."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document_id: UUID
    user_id: UUID
    document_type: DocumentClassification = Field(default=DocumentClassification.OTHER)
    currency: str | None = None
    vendor_name: ExtractedField | None = None
    vendor_tax_id: ExtractedField | None = None
    issued_date: ExtractedField | None = None
    due_date: ExtractedField | None = None
    period_start: ExtractedField | None = None
    period_end: ExtractedField | None = None
    line_items: list[LineItem] = Field(default_factory=list)
    cost_breakdown: list[FinancialComponent] = Field(default_factory=list)
    subtotal: ExtractedField | None = None
    tax_amount: ExtractedField | None = None
    taxes: list[ExtractedField] = Field(default_factory=list)
    shipping_amount: ExtractedField | None = None
    discount_amount: ExtractedField | None = None
    fees: list[ExtractedField] = Field(default_factory=list)
    amount_paid: ExtractedField | None = None
    balance_due: ExtractedField | None = None
    payment_status: ExtractedField | None = None
    total_amount: ExtractedField
    clauses_and_notes: list[ExtractedField] = Field(default_factory=list)
