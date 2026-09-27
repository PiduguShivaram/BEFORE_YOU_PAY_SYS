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

    # 11 Core Vehicle Categories (Phase 1)
    BASE_PRICE = "base_price"
    TAX_OR_STATUTORY = "tax_or_statutory"
    REGISTRATION = "registration"
    INSURANCE = "insurance"
    WARRANTY = "warranty"
    SERVICE = "service"
    ACCESSORY = "accessory"
    DEALER_CHARGE = "dealer_charge"
    FINANCING = "financing"
    DISCOUNT = "discount"
    OTHER = "other"

    # Fine-grained / Sub-categories for specialized breakdown & backward compatibility
    EX_SHOWROOM_PRICE = "ex_showroom_price"
    TAX = "tax"
    TCS = "tcs"
    GST = "gst"
    ROAD_TAX = "road_tax"
    RC = "rc"
    HSRP = "hsrp"
    EXTENDED_WARRANTY = "extended_warranty"
    ACCESSORY_PACKAGE = "accessory_package"
    HANDLING_FEE = "handling_fee"
    LOGISTICS_FEE = "logistics_fee"
    PROCESSING_FEE = "processing_fee"
    FASTAG = "fastag"
    DEALER_PACKAGE = "dealer_package"
    SERVICE_PACKAGE = "service_package"
    OTHER_FEE = "other_fee"
    OFFER = "offer"
    SUBTOTAL = "subtotal"
    TOTAL = "total"
    AMOUNT_PAID = "amount_paid"
    BALANCE_DUE = "balance_due"
    UNKNOWN = "unknown"
    UNCLEAR = "unclear"

    # Legacy / backward-compatible aliases
    ACCESSORY_OR_FEE = "accessory_or_fee"

    @classmethod
    def _missing_(cls, value: object) -> Any:
        if isinstance(value, str):
            val_norm = value.strip().lower()
            for member in cls:
                if member.value == val_norm or member.name.lower() == val_norm:
                    return member
        return None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            other_norm = other.strip().lower()
            return self.value == other_norm or self.name.lower() == other_norm
        return super().__eq__(other)

    def __hash__(self) -> int:
        return hash(self.value)

    def to_vehicle_category(self) -> "ComponentCategory":
        """Map any fine-grained category to one of the 11 core vehicle categories."""
        if self in (ComponentCategory.BASE_PRICE, ComponentCategory.EX_SHOWROOM_PRICE):
            return ComponentCategory.BASE_PRICE
        if self in (ComponentCategory.TAX_OR_STATUTORY, ComponentCategory.TAX, ComponentCategory.TCS, ComponentCategory.GST, ComponentCategory.ROAD_TAX):
            return ComponentCategory.TAX_OR_STATUTORY
        if self in (ComponentCategory.REGISTRATION, ComponentCategory.RC, ComponentCategory.HSRP):
            return ComponentCategory.REGISTRATION
        if self == ComponentCategory.INSURANCE:
            return ComponentCategory.INSURANCE
        if self in (ComponentCategory.WARRANTY, ComponentCategory.EXTENDED_WARRANTY):
            return ComponentCategory.WARRANTY
        if self in (ComponentCategory.SERVICE, ComponentCategory.SERVICE_PACKAGE):
            return ComponentCategory.SERVICE
        if self in (ComponentCategory.ACCESSORY, ComponentCategory.ACCESSORY_PACKAGE):
            return ComponentCategory.ACCESSORY
        if self in (ComponentCategory.DEALER_CHARGE, ComponentCategory.HANDLING_FEE, ComponentCategory.LOGISTICS_FEE, ComponentCategory.PROCESSING_FEE, ComponentCategory.DEALER_PACKAGE, ComponentCategory.FASTAG, ComponentCategory.OTHER_FEE):
            return ComponentCategory.DEALER_CHARGE
        if self == ComponentCategory.FINANCING:
            return ComponentCategory.FINANCING
        if self in (ComponentCategory.DISCOUNT, ComponentCategory.OFFER):
            return ComponentCategory.DISCOUNT
        if self in (ComponentCategory.UNKNOWN, ComponentCategory.UNCLEAR):
            return ComponentCategory.UNKNOWN
        return ComponentCategory.OTHER


class ChargeNature(StrEnum):
    """Nature of the financial component: positive charge vs negative deduction."""

    CHARGE = "charge"
    DEDUCTION = "deduction"


class OptionalityStatus(StrEnum):
    """Semantic optionality status of a financial charge or deduction (Phase 3)."""

    CONFIRMED_MANDATORY = "confirmed_mandatory"
    CONFIRMED_OPTIONAL = "confirmed_optional"
    POTENTIALLY_OPTIONAL = "potentially_optional"
    UNCLEAR = "unclear"
    NOT_APPLICABLE = "not_applicable"

    @classmethod
    def _missing_(cls, value: object) -> Any:
        if isinstance(value, str):
            val_norm = value.strip().lower()
            if val_norm in ("mandatory", "confirmed_mandatory"):
                return cls.CONFIRMED_MANDATORY
            if val_norm in ("optional", "confirmed_optional"):
                return cls.CONFIRMED_OPTIONAL
            if val_norm in ("potentially_optional", "potential_optional"):
                return cls.POTENTIALLY_OPTIONAL
            if val_norm in ("unclear", "unknown"):
                return cls.UNCLEAR
            if val_norm in ("not_applicable", "na", "n/a"):
                return cls.NOT_APPLICABLE
            for member in cls:
                if member.value == val_norm or member.name.lower() == val_norm:
                    return member
        return None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, OptionalityStatus):
            return self.value == other.value
        if isinstance(other, str):
            other_norm = other.strip().lower()
            if self.value == other_norm or self.name.lower() == other_norm:
                return True
            if self.value == "confirmed_mandatory" and other_norm in ("mandatory", "confirmed_mandatory"):
                return True
            if self.value == "confirmed_optional" and other_norm in ("optional", "confirmed_optional"):
                return True
            if self.value == "potentially_optional" and other_norm in ("optional", "potentially_optional", "potential_optional"):
                return True
            if self.value == "unclear" and other_norm in ("unclear", "unknown"):
                return True
            if self.value == "not_applicable" and other_norm in ("not_applicable", "na", "n/a"):
                return True
            return False
        return super().__eq__(other)

    def __hash__(self) -> int:
        return hash(self.value)


class ChargeStatus(StrEnum):
    """Phase 2 Charge Status classification."""

    MANDATORY_STATUTORY = "MANDATORY_STATUTORY"
    CONTRACTUAL_REQUIREMENT = "CONTRACTUAL_REQUIREMENT"
    OPTIONAL = "OPTIONAL"
    POTENTIALLY_OPTIONAL = "POTENTIALLY_OPTIONAL"
    NEGOTIABLE = "NEGOTIABLE"
    INCLUDED_ELSEWHERE = "INCLUDED_ELSEWHERE"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def _missing_(cls, value: object) -> Any:
        if isinstance(value, str):
            val_norm = value.strip().upper().replace(" ", "_").replace("-", "_")
            for member in cls:
                if member.value == val_norm or member.name == val_norm:
                    return member
        return None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ChargeStatus):
            return self.value == other.value
        if isinstance(other, str):
            other_norm = other.strip().upper().replace(" ", "_").replace("-", "_")
            return self.value == other_norm or self.name == other_norm
        return super().__eq__(other)

    def __hash__(self) -> int:
        return hash(self.value)


CHARGE_STATUS_DISPLAY_LABELS: dict[ChargeStatus, str] = {
    ChargeStatus.MANDATORY_STATUTORY: "Mandatory by law",
    ChargeStatus.CONTRACTUAL_REQUIREMENT: "Required by seller/contract",
    ChargeStatus.OPTIONAL: "Optional",
    ChargeStatus.POTENTIALLY_OPTIONAL: "Potentially optional",
    ChargeStatus.NEGOTIABLE: "Potentially negotiable",
    ChargeStatus.INCLUDED_ELSEWHERE: "Included elsewhere",
    ChargeStatus.UNKNOWN: "Unknown",
}


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

    model_config = ConfigDict(frozen=True, extra="ignore")

    component_id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=1)
    raw_text: str | None = None
    raw_name: str | None = None
    raw_label: str | None = None
    normalized_name: str | None = None
    normalized_label: str | None = None
    amount: ExtractedField
    category: ComponentCategory = Field(default=ComponentCategory.UNKNOWN)
    vehicle_category: ComponentCategory = Field(default=ComponentCategory.UNKNOWN)
    charge_nature: ChargeNature = Field(default=ChargeNature.CHARGE)
    charge_or_deduction: str = Field(default="charge")
    optionality_status: OptionalityStatus = Field(default=OptionalityStatus.UNCLEAR)
    optionality_display: str | None = None
    document_states: str | None = None
    system_knows: str | None = None
    requires_confirmation: str | None = None
    is_optional: bool = Field(default=False)
    confidence: float = Field(default=0.95, ge=0.0, le=1.0)
    charge_status: ChargeStatus = Field(default=ChargeStatus.UNKNOWN)
    charge_status_display: str | None = None
    charge_status_reason: str | None = None
    requires_verification: bool = Field(default=False)
    evidence: str | None = None
    source_ocr_line: str | None = None
    bounding_box: BoundingBox | None = None
    page: int | None = Field(default=1, ge=1)
    explanation: str | None = None

    @model_validator(mode="before")
    @classmethod
    def populate_semantic_defaults(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # Determine raw_text, raw_name, raw_label and initial name
        raw_val = str(
            data.get("raw_text")
            or data.get("raw_label")
            or data.get("raw_name")
            or data.get("name")
            or "Component"
        ).strip()
        data["raw_text"] = raw_val
        data["raw_name"] = raw_val

        # Lazy import to avoid circular dependency
        from before_you_pay.services.financial_taxonomy import (
            classify_component_name,
            clean_component_text,
            normalize_financial_label,
        )

        cleaned_label = clean_component_text(raw_val)
        data["raw_label"] = (
            str(data.get("raw_label")).strip()
            if data.get("raw_label")
            else (cleaned_label or raw_val)
        )

        name_val = str(
            data.get("name")
            or data.get("normalized_label")
            or data.get("normalized_name")
            or data["raw_label"]
        ).strip()
        data["name"] = name_val

        inferred_cat, inferred_norm_name, inferred_nature, inferred_opt, inferred_exp = (
            classify_component_name(raw_val)
        )

        # Category: use provided if valid and not default OTHER/UNKNOWN, otherwise inferred
        user_cat = data.get("category")
        if user_cat is None or user_cat in [
            ComponentCategory.UNKNOWN,
            ComponentCategory.OTHER,
            "unknown",
            "other",
        ]:
            data["category"] = inferred_cat
        else:
            try:
                data["category"] = ComponentCategory(user_cat)
            except ValueError:
                data["category"] = inferred_cat

        # Vehicle Category (11 core vehicle categories)
        if isinstance(data["category"], ComponentCategory):
            data["vehicle_category"] = data["category"].to_vehicle_category()
        else:
            try:
                data["vehicle_category"] = ComponentCategory(data["category"]).to_vehicle_category()
            except ValueError:
                data["vehicle_category"] = ComponentCategory.UNKNOWN

        # Normalized name (taxonomy canonical name)
        norm_name = data.get("normalized_name") or inferred_norm_name
        data["normalized_name"] = norm_name

        # Normalized label (Phase 1 clean human-facing normalized OCR label)
        norm_label = data.get("normalized_label")
        if not norm_label:
            norm_label = normalize_financial_label(raw_val) or norm_name
        data["normalized_label"] = norm_label

        # Charge nature & charge_or_deduction
        user_nature = data.get("charge_nature")
        user_cod = data.get("charge_or_deduction")
        if user_cod:
            cod_norm = str(user_cod).lower().strip()
            nature = (
                ChargeNature.DEDUCTION
                if cod_norm in ["deduction", "discount", "offer"]
                else ChargeNature.CHARGE
            )
            data["charge_nature"] = nature
            data["charge_or_deduction"] = nature.value
        elif user_nature:
            nat = ChargeNature(user_nature)
            data["charge_nature"] = nat
            data["charge_or_deduction"] = nat.value
        else:
            data["charge_nature"] = inferred_nature
            data["charge_or_deduction"] = inferred_nature.value

        # Amount extraction provenance shortcuts
        amt = data.get("amount")
        if amt is not None:
            prov = getattr(amt, "provenance", None)
            amt_conf = getattr(amt, "confidence", 0.95)
            if isinstance(amt, dict):
                prov = amt.get("provenance")
                amt_conf = amt.get("confidence", 0.95)

            if data.get("confidence") is None and amt_conf is not None:
                data["confidence"] = amt_conf

            if prov:
                if not data.get("evidence"):
                    raw_t = (
                        prov.get("raw_text")
                        if isinstance(prov, dict)
                        else getattr(prov, "raw_text", None)
                    )
                    data["evidence"] = raw_t or raw_val
                if not data.get("bounding_box"):
                    bb = (
                        prov.get("bounding_box")
                        if isinstance(prov, dict)
                        else getattr(prov, "bounding_box", None)
                    )
                    data["bounding_box"] = bb
                if not data.get("source_ocr_line"):
                    line_ids = (
                        prov.get("ocr_line_ids")
                        if isinstance(prov, dict)
                        else getattr(prov, "ocr_line_ids", None)
                    )
                    if line_ids:
                        data["source_ocr_line"] = str(line_ids[0])

        if not data.get("explanation"):
            data["explanation"] = inferred_exp

        # Optionality analysis using multi-factor evidence (Phase 3)
        from before_you_pay.services.optionality import OptionalityAnalysisService

        raw_context_text = f"{raw_val} {data.get('evidence') or ''}".strip()
        opt_assessment = OptionalityAnalysisService.analyze(
            raw_text=raw_context_text,
            category=data["category"],
            charge_nature=data["charge_nature"],
            explicit_status=data.get("optionality_status"),
        )

        data["optionality_status"] = opt_assessment.status
        data["optionality_display"] = data.get("optionality_display") or opt_assessment.display_label
        data["document_states"] = data.get("document_states") or opt_assessment.document_states
        data["system_knows"] = data.get("system_knows") or opt_assessment.system_knows
        data["requires_confirmation"] = data.get("requires_confirmation") or opt_assessment.requires_confirmation

        # Optionality boolean flag
        # Optionality boolean flag
        user_is_opt = data.get("is_optional")
        if user_is_opt is not None:
            data["is_optional"] = bool(user_is_opt)
        else:
            data["is_optional"] = opt_assessment.status in (
                OptionalityStatus.CONFIRMED_OPTIONAL,
                OptionalityStatus.POTENTIALLY_OPTIONAL,
            )

        # Phase 2 Charge Status Classification
        from before_you_pay.services.charge_status import ChargeStatusClassifier

        amt_val = None
        if data.get("amount") is not None:
            amt_obj = data["amount"]
            amt_val = (
                getattr(amt_obj, "normalized_value", None)
                if hasattr(amt_obj, "normalized_value")
                else (amt_obj.get("normalized_value") if isinstance(amt_obj, dict) else None)
            )

        charge_assessment = ChargeStatusClassifier.classify(
            raw_text=raw_context_text,
            category=data["category"],
            amount=amt_val,
            charge_nature=data["charge_nature"],
            evidence=data.get("evidence"),
            confidence=data.get("confidence"),
            explicit_status=data.get("charge_status"),
        )
        data["charge_status"] = charge_assessment.status
        data["charge_status_display"] = data.get("charge_status_display") or charge_assessment.display_label
        data["charge_status_reason"] = data.get("charge_status_reason") or charge_assessment.reason
        data["requires_verification"] = bool(
            data.get("requires_verification")
            or charge_assessment.requires_verification
            or data.get("requires_confirmation")
        )

        return data

    def to_charge_payload(self) -> dict[str, Any]:
        """Return standardized Phase 1, 2 & Phase 3 recognized charge dictionary:
        {raw_text, raw_label, normalized_label, category, vehicle_category, charge_status, charge_status_display, reason, amount, confidence, page, bounding_box, evidence, requires_verification, ...}
        """
        cat_str = (
            "Unclear"
            if self.category in (ComponentCategory.UNCLEAR, ComponentCategory.UNKNOWN)
            else self.category.value
        )
        amt_val = (
            self.amount.normalized_value
            if hasattr(self.amount, "normalized_value")
            else float(self.amount)
        )
        ev_text = self.evidence or self.source_ocr_line
        if not ev_text and hasattr(self.amount, "provenance") and self.amount.provenance:
            ev_text = self.amount.provenance.raw_text
        if not ev_text:
            ev_text = f"{self.raw_text or self.raw_label or self.raw_name or self.name}: {amt_val}"

        opt_status_str = (
            self.optionality_status.value
            if hasattr(self.optionality_status, "value")
            else str(self.optionality_status)
        )

        chg_status_str = (
            self.charge_status.value
            if hasattr(self.charge_status, "value")
            else str(self.charge_status)
        )

        return {
            "raw_text": self.raw_text or self.raw_label or self.raw_name or self.name,
            "raw_label": self.raw_label or self.raw_name or self.name,
            "normalized_label": self.normalized_label or self.normalized_name or self.name,
            "category": cat_str,
            "vehicle_category": (
                self.vehicle_category.value
                if hasattr(self.vehicle_category, "value")
                else (self.category.to_vehicle_category().value if hasattr(self.category, "to_vehicle_category") else cat_str)
            ),
            "amount": float(amt_val),
            "confidence": float(self.confidence),
            "charge_status": chg_status_str,
            "charge_status_display": self.charge_status_display or CHARGE_STATUS_DISPLAY_LABELS.get(self.charge_status, "Unknown"),
            "charge_status_reason": self.charge_status_reason or self.explanation or "",
            "reason": self.charge_status_reason or self.explanation or "",
            "requires_verification": bool(self.requires_verification),
            "page": self.page or 1,
            "bounding_box": self.bounding_box.model_dump() if self.bounding_box else None,
            "evidence": str(ev_text),
            "optionality_status": opt_status_str,
            "optionality_display": self.optionality_display,
            "document_states": self.document_states,
            "system_knows": self.system_knows,
            "requires_confirmation": self.requires_confirmation,
        }


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
