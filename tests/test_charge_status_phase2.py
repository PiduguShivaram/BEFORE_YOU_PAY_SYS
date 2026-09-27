"""Unit and regression tests for Phase 2 - Charge Status Classification.

Verifies:
1. Exact charge status classifications:
   - MANDATORY_STATUTORY
   - CONTRACTUAL_REQUIREMENT
   - OPTIONAL
   - POTENTIALLY_OPTIONAL
   - NEGOTIABLE
   - INCLUDED_ELSEWHERE
   - UNKNOWN
2. Returned payload fields:
   - confidence
   - reason
   - evidence
   - requires_verification
3. Specific domain requirements:
   - Insurance -> potentially optional / provider-dependent
   - Extended Warranty -> potentially optional
   - Accessories -> potentially optional
   - Dealer handling charge -> requires verification / potentially negotiable
   - Registration -> jurisdiction-dependent statutory
   - Ex-showroom -> base vehicle price (contractual requirement)
4. UI display distinctions:
   - "Mandatory by law"
   - "Required by seller/contract"
   - "Potentially optional"
   - "Unknown"
5. Phrasing safety:
   - Never says: "You don't need this", "You can definitely remove this", "You will save ₹X"
   - Uses: "Potentially optional — verify whether it is required."
"""

from uuid import uuid4
import pytest

from before_you_pay.models.document import (
    BoundingBox,
    ChargeNature,
    ChargeStatus,
    ComponentCategory,
    ExtractedField,
    FieldProvenance,
    FinancialComponent,
    CHARGE_STATUS_DISPLAY_LABELS,
)
from before_you_pay.services.charge_status import (
    ChargeStatusAssessment,
    ChargeStatusClassifier,
)


def _make_field(val: float, text: str) -> ExtractedField:
    doc_id = uuid4()
    page_id = uuid4()
    line_id = uuid4()
    return ExtractedField(
        field_id=uuid4(),
        field_key="charge_amount",
        normalized_value=val,
        unit_or_currency="₹",
        confidence=0.95,
        provenance=FieldProvenance(
            document_id=doc_id,
            page_id=page_id,
            ocr_line_ids=[line_id],
            bounding_box=BoundingBox(x=0.05, y=0.10, width=0.80, height=0.03),
            raw_text=text,
        ),
    )


class TestPhase2ChargeStatusClassifications:
    """Verifies that every charge is classified according to evidence without universal legal claims."""

    def test_ex_showroom_is_contractual_requirement(self):
        """Ex-showroom is classified as base vehicle price / contractual requirement."""
        text = "Ex-Showroom ₹11,49,900"
        res = ChargeStatusClassifier.classify(
            raw_text=text,
            category=ComponentCategory.EX_SHOWROOM_PRICE,
            amount=1149900.0,
            evidence=text,
        )

        assert res.status == ChargeStatus.CONTRACTUAL_REQUIREMENT
        assert res.display_label == "Required by seller/contract"
        assert "base vehicle price" in res.reason.lower()
        assert res.requires_verification is False
        assert res.confidence >= 0.90
        assert res.evidence == text

    def test_tcs_is_mandatory_statutory(self):
        """TCS is statutory tax mandated by law."""
        text = "TCS @ 1% ₹11,499"
        res = ChargeStatusClassifier.classify(
            raw_text=text,
            category=ComponentCategory.TCS,
            amount=11499.0,
            evidence=text,
        )

        assert res.status == ChargeStatus.MANDATORY_STATUTORY
        assert res.display_label == "Mandatory by law"
        assert "statutory" in res.reason.lower()
        assert res.requires_verification is False
        assert res.confidence >= 0.90

    def test_road_tax_is_mandatory_statutory(self):
        """Road tax is mandatory governmental levy."""
        text = "Road Tax ₹76,250"
        res = ChargeStatusClassifier.classify(
            raw_text=text,
            category=ComponentCategory.ROAD_TAX,
            amount=76250.0,
            evidence=text,
        )

        assert res.status == ChargeStatus.MANDATORY_STATUTORY
        assert res.display_label == "Mandatory by law"
        assert res.requires_verification is False

    def test_registration_is_jurisdiction_dependent(self):
        """Registration is statutory governmental fee but jurisdiction-dependent."""
        text = "Registration / R.C. ₹2,500"
        res = ChargeStatusClassifier.classify(
            raw_text=text,
            category=ComponentCategory.REGISTRATION,
            amount=2500.0,
            evidence=text,
        )

        assert res.status == ChargeStatus.MANDATORY_STATUTORY
        assert res.display_label == "Mandatory by law"
        assert "jurisdiction-dependent" in res.reason.lower()
        # Jurisdiction-dependent requires confirmation / verification of state RTO slab
        assert res.requires_verification is True

    def test_insurance_is_potentially_optional_provider_dependent(self):
        """Insurance -> potentially optional / provider-dependent."""
        text = "Comprehensive Insurance ₹34,500"
        res = ChargeStatusClassifier.classify(
            raw_text=text,
            category=ComponentCategory.INSURANCE,
            amount=34500.0,
            evidence=text,
        )

        assert res.status == ChargeStatus.POTENTIALLY_OPTIONAL
        assert res.display_label == "Potentially optional"
        assert "potentially optional" in res.reason.lower()
        assert "verify whether" in res.reason.lower()
        assert res.requires_verification is True

    def test_extended_warranty_is_potentially_optional(self):
        """Extended Warranty -> potentially optional."""
        text = "Extended Warranty ₹24,000"
        res = ChargeStatusClassifier.classify(
            raw_text=text,
            category=ComponentCategory.EXTENDED_WARRANTY,
            amount=24000.0,
            evidence=text,
        )

        assert res.status == ChargeStatus.POTENTIALLY_OPTIONAL
        assert res.display_label == "Potentially optional"
        assert "potentially optional" in res.reason.lower()
        assert "verify whether" in res.reason.lower()
        assert res.requires_verification is True

    def test_accessories_is_potentially_optional(self):
        """Accessories -> potentially optional."""
        text = "Essential Accessories Kit ₹35,000"
        res = ChargeStatusClassifier.classify(
            raw_text=text,
            category=ComponentCategory.ACCESSORY_PACKAGE,
            amount=35000.0,
            evidence=text,
        )

        assert res.status == ChargeStatus.POTENTIALLY_OPTIONAL
        assert res.display_label == "Potentially optional"
        assert "potentially optional" in res.reason.lower()
        assert "verify whether" in res.reason.lower()
        assert res.requires_verification is True

    def test_dealer_handling_charge_is_negotiable_requires_verification(self):
        """Dealer handling charge -> requires verification / potentially negotiable."""
        text = "Handling Charges ₹8,500"
        res = ChargeStatusClassifier.classify(
            raw_text=text,
            category=ComponentCategory.HANDLING_FEE,
            amount=8500.0,
            evidence=text,
        )

        assert res.status == ChargeStatus.NEGOTIABLE
        assert res.display_label == "Potentially negotiable"
        assert "requires verification" in res.reason.lower()
        assert "negotiable" in res.reason.lower()
        assert res.requires_verification is True

    def test_explicitly_optional_charge(self):
        """Charge explicitly marked as optional in document text."""
        text = "Optional Underbody Coating ₹6,000"
        res = ChargeStatusClassifier.classify(
            raw_text=text,
            category=ComponentCategory.OTHER_FEE,
            amount=6000.0,
            evidence=text,
        )

        assert res.status == ChargeStatus.OPTIONAL
        assert res.display_label == "Optional"
        assert "explicitly" in res.reason.lower()
        assert res.requires_verification is False

    def test_included_elsewhere_charge(self):
        """Charge indicated as included in vehicle price / zero-rated."""
        text = "Basic Tool Kit: Included"
        res = ChargeStatusClassifier.classify(
            raw_text=text,
            category=ComponentCategory.ACCESSORY,
            amount=0.0,
            evidence=text,
        )

        assert res.status == ChargeStatus.INCLUDED_ELSEWHERE
        assert res.display_label == "Included elsewhere"
        assert "included elsewhere" in res.reason.lower()
        assert res.requires_verification is True

    def test_unknown_charge_requires_verification(self):
        """Charge with unknown/unclear evidence."""
        text = "SPECIAL_LEVY_CODE_42 ₹3,500"
        res = ChargeStatusClassifier.classify(
            raw_text=text,
            category=ComponentCategory.UNKNOWN,
            amount=3500.0,
            evidence=text,
        )

        assert res.status == ChargeStatus.UNKNOWN
        assert res.display_label == "Unknown"
        assert "unknown" in res.reason.lower()
        assert res.requires_verification is True


class TestPhase2PhrasingSafetyAndGuardrails:
    """Verifies strict safety phrasing:
    - Never say: 'You don't need this', 'You can definitely remove this', 'You will save ₹X'
    - Uses: 'Potentially optional — verify whether it is required.'
    - Clear UI distinctions.
    """

    @pytest.mark.parametrize(
        "cat,raw_text",
        [
            (ComponentCategory.INSURANCE, "Insurance ₹34,500"),
            (ComponentCategory.EXTENDED_WARRANTY, "Ext Warranty ₹24,000"),
            (ComponentCategory.ACCESSORY_PACKAGE, "Accessories ₹35,000"),
            (ComponentCategory.HANDLING_FEE, "Handling ₹8,500"),
            (ComponentCategory.UNKNOWN, "XYZ ₹5,000"),
        ],
    )
    def test_no_prohibited_legal_claims_or_promises(self, cat: ComponentCategory, raw_text: str):
        res = ChargeStatusClassifier.classify(raw_text=raw_text, category=cat, evidence=raw_text)

        reason_lower = res.reason.lower()
        # Strictly forbidden phrasing
        assert "you don't need this" not in reason_lower
        assert "you dont need this" not in reason_lower
        assert "definitely remove" not in reason_lower
        assert "you will save" not in reason_lower

        # Recommended phrasing for potentially optional
        if res.status == ChargeStatus.POTENTIALLY_OPTIONAL:
            assert "potentially optional" in reason_lower
            assert "verify whether" in reason_lower

    def test_ui_display_labels_are_distinct(self):
        """The UI must clearly distinguish:
        'Mandatory by law' from 'Required by seller/contract' from 'Potentially optional' from 'Unknown'
        """
        assert CHARGE_STATUS_DISPLAY_LABELS[ChargeStatus.MANDATORY_STATUTORY] == "Mandatory by law"
        assert CHARGE_STATUS_DISPLAY_LABELS[ChargeStatus.CONTRACTUAL_REQUIREMENT] == "Required by seller/contract"
        assert CHARGE_STATUS_DISPLAY_LABELS[ChargeStatus.POTENTIALLY_OPTIONAL] == "Potentially optional"
        assert CHARGE_STATUS_DISPLAY_LABELS[ChargeStatus.UNKNOWN] == "Unknown"

        # Ensure all distinct
        distinct_labels = {
            CHARGE_STATUS_DISPLAY_LABELS[ChargeStatus.MANDATORY_STATUTORY],
            CHARGE_STATUS_DISPLAY_LABELS[ChargeStatus.CONTRACTUAL_REQUIREMENT],
            CHARGE_STATUS_DISPLAY_LABELS[ChargeStatus.POTENTIALLY_OPTIONAL],
            CHARGE_STATUS_DISPLAY_LABELS[ChargeStatus.UNKNOWN],
        }
        assert len(distinct_labels) == 4


class TestPhase2FinancialComponentIntegration:
    """Verifies FinancialComponent integrates charge_status, confidence, reason, evidence, requires_verification."""

    def test_financial_component_payload_contains_all_phase2_fields(self):
        amt_field = _make_field(24000.0, "EXT WARRANTY ₹24,000")
        comp = FinancialComponent(
            raw_text="EXT WARRANTY",
            name="EXT WARRANTY",
            amount=amt_field,
            category=ComponentCategory.EXTENDED_WARRANTY,
            evidence="EXT WARRANTY ₹24,000",
        )

        assert comp.charge_status == ChargeStatus.POTENTIALLY_OPTIONAL
        assert comp.charge_status_display == "Potentially optional"
        assert comp.requires_verification is True

        payload = comp.to_charge_payload()
        assert payload["charge_status"] == "POTENTIALLY_OPTIONAL"
        assert payload["charge_status_display"] == "Potentially optional"
        assert "charge_status_reason" in payload
        assert "reason" in payload
        assert payload["requires_verification"] is True
        assert payload["confidence"] >= 0.90
        assert payload["evidence"] == "EXT WARRANTY ₹24,000"
