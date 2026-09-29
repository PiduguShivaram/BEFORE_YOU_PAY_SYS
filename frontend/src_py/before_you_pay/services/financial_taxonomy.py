"""Semantic taxonomy and classification engine for financial document components.

Understands what a financial charge or deduction represents in quotations,
bills, invoices, and contracts. Handles OCR noise, abbreviations, and aliases.
"""

import difflib
import re
from dataclasses import dataclass

from before_you_pay.models.document import ChargeNature, ComponentCategory


@dataclass(frozen=True)
class SemanticCategoryDefinition:
    """Taxonomy definition for a financial component category."""

    category: ComponentCategory
    normalized_name: str
    default_nature: ChargeNature
    optionality_status: str  # "mandatory", "optional", "recommended"
    explanation: str
    canonical_keywords: tuple[str, ...]
    regex_patterns: tuple[re.Pattern, ...]


def _compile_patterns(patterns: list[str]) -> tuple[re.Pattern, ...]:
    return tuple(re.compile(p, re.IGNORECASE) for p in patterns)


TAXONOMY_DEFINITIONS: dict[ComponentCategory, SemanticCategoryDefinition] = {
    ComponentCategory.EX_SHOWROOM_PRICE: SemanticCategoryDefinition(
        category=ComponentCategory.EX_SHOWROOM_PRICE,
        normalized_name="Ex-showroom price",
        default_nature=ChargeNature.CHARGE,
        optionality_status="mandatory",
        explanation="Vehicle manufacturer base price before statutory taxes, registration, and dealer fees.",
        canonical_keywords=(
            "ex showroom",
            "ex-showroom",
            "exshowroom",
            "exshorum",
            "ex showroom price",
            "ex factory",
            "base vehicle price",
            "vehicle price",
            "showroom price",
        ),
        regex_patterns=_compile_patterns(
            [
                r"\bex[\s\.\-_]*sho?w?ru?o?m\b",
                r"\bex[\s\.\-_]*showr[o0]{2}m\b",
                r"\bex[\s\.\-_]*showroom\b",
                r"\bex[\s\.\-_]*factory\b",
                r"\bbase\s+vehicle\s+(?:price|amount|cost)\b",
                r"\bvehicle\s+base\s+(?:price|amount)\b",
                r"\bshowroom\s+price\b",
            ]
        ),
    ),
    ComponentCategory.BASE_PRICE: SemanticCategoryDefinition(
        category=ComponentCategory.BASE_PRICE,
        normalized_name="Base price",
        default_nature=ChargeNature.CHARGE,
        optionality_status="mandatory",
        explanation="Stated baseline price for an item, unit, or service prior to taxes and surcharges.",
        canonical_keywords=(
            "base price",
            "basic price",
            "basic amount",
            "base amount",
            "base rate",
            "unit price",
            "item rate",
        ),
        regex_patterns=_compile_patterns(
            [
                r"\bbase\s+(?:price|rate|amount|cost)\b",
                r"\bbasic\s+(?:price|amount|rate|value)\b",
                r"\bunit\s+(?:price|rate)\b",
            ]
        ),
    ),
    ComponentCategory.TCS: SemanticCategoryDefinition(
        category=ComponentCategory.TCS,
        normalized_name="TCS",
        default_nature=ChargeNature.CHARGE,
        optionality_status="mandatory",
        explanation="Statutory Tax Collected at Source mandated under section 206C of the Income Tax Act.",
        canonical_keywords=("tcs", "t.c.s.", "tax collected at source", "tcs @ 1%", "tcs 1%"),
        regex_patterns=_compile_patterns(
            [
                r"\bt[\s\.]*c[\s\.]*s\b",
                r"\btax\s+collected\s+at\s+source\b",
            ]
        ),
    ),
    ComponentCategory.GST: SemanticCategoryDefinition(
        category=ComponentCategory.GST,
        normalized_name="GST",
        default_nature=ChargeNature.CHARGE,
        optionality_status="mandatory",
        explanation="Goods and Services Tax levied on supply of goods and services.",
        canonical_keywords=("gst", "cgst", "sgst", "igst", "utgst", "goods and services tax"),
        regex_patterns=_compile_patterns(
            [
                r"\b(?:c|s|i|ut)?gst\b",
                r"\bgoods\s+(?:and|&)\s+services\s+tax\b",
            ]
        ),
    ),
    ComponentCategory.ROAD_TAX: SemanticCategoryDefinition(
        category=ComponentCategory.ROAD_TAX,
        normalized_name="Road tax",
        default_nature=ChargeNature.CHARGE,
        optionality_status="mandatory",
        explanation="Statutory state road tax / motor vehicle tax for vehicular road usage permit.",
        canonical_keywords=(
            "road tax",
            "roadtax",
            "rd tax",
            "rto tax",
            "mv tax",
            "m.v. tax",
            "motor vehicle tax",
            "one time tax",
            "life time tax",
        ),
        regex_patterns=_compile_patterns(
            [
                r"\broad\s*tax\b",
                r"\brd[\s\.]*tax\b",
                r"\bm[\s\.]*v[\s\.]*\s*tax\b",
                r"\bmotor\s+vehicle\s+tax\b",
                r"\b(?:one|life)\s*time\s*tax\b",
                r"\brto\s+tax\b",
            ]
        ),
    ),
    ComponentCategory.RC: SemanticCategoryDefinition(
        category=ComponentCategory.RC,
        normalized_name="Registration / R.C.",
        default_nature=ChargeNature.CHARGE,
        optionality_status="mandatory",
        explanation="Official vehicle registration certificate and smart card fee issued by the RTO.",
        canonical_keywords=(
            "rc",
            "r.c.",
            "r.c",
            "rc charges",
            "smart card rc",
            "rc card",
            "rc book",
        ),
        regex_patterns=_compile_patterns(
            [
                r"\br[\s\.]*c\b(?!\s*charges?\s*&\s*road\s*tax)",
                r"\br[\s\.]*c[\s\.]*(?:book|card|smart\s*card)\b",
                r"\bsmart\s*card\s*(?:rc|fee|charges?)?\b",
            ]
        ),
    ),
    ComponentCategory.REGISTRATION: SemanticCategoryDefinition(
        category=ComponentCategory.REGISTRATION,
        normalized_name="Registration",
        default_nature=ChargeNature.CHARGE,
        optionality_status="mandatory",
        explanation="Official governmental charges and statutory fees for registering vehicle ownership.",
        canonical_keywords=(
            "registration",
            "registration charges",
            "regn.",
            "regn",
            "reg charges",
            "rto registration",
            "rto fee",
            "rto charges",
        ),
        regex_patterns=_compile_patterns(
            [
                r"\bregn?[\s\.]*(?:charges?|fees?|fee)?\b",
                r"\bregistration\s*(?:charges?|fees?|amount)?\b",
                r"\brto\s*(?:registration|charges?|fees?|fee)?\b",
            ]
        ),
    ),
    ComponentCategory.HSRP: SemanticCategoryDefinition(
        category=ComponentCategory.HSRP,
        normalized_name="Temporary registration / HSRP",
        default_nature=ChargeNature.CHARGE,
        optionality_status="mandatory",
        explanation="High Security Registration Plate and tamper-proof snap-lock fitment required by transport authorities.",
        canonical_keywords=(
            "hsrp",
            "h.s.r.p.",
            "high security registration plate",
            "number plate",
            "temp + msrp",
            "msrp/hsrp",
            "temp + hsrp",
            "temp hsrp",
            "temporary + hsrp",
            "plate charges",
        ),
        regex_patterns=_compile_patterns(
            [
                r"\bh[\s\.]*s[\s\.]*r[\s\.]*p\b",
                r"\bhigh\s+security\s+registration\s+plate\b",
                r"\b(?:temp|temporary)?\s*(?:\+|\/|&)?\s*(?:m|h)srp\b",
                r"\bnumber\s+plate\b",
            ]
        ),
    ),
    ComponentCategory.TAX: SemanticCategoryDefinition(
        category=ComponentCategory.TAX,
        normalized_name="Tax",
        default_nature=ChargeNature.CHARGE,
        optionality_status="mandatory",
        explanation="General statutory taxation, VAT, or local governmental levy.",
        canonical_keywords=("tax", "taxes", "vat", "v.a.t.", "sales tax", "cess", "service tax"),
        regex_patterns=_compile_patterns(
            [
                r"\bv[\s\.]*a[\s\.]*t\b",
                r"\bsales\s+tax\b",
                r"\bcess\b",
                r"\btax(?:es)?\b",
            ]
        ),
    ),
    ComponentCategory.INSURANCE: SemanticCategoryDefinition(
        category=ComponentCategory.INSURANCE,
        normalized_name="Insurance",
        default_nature=ChargeNature.CHARGE,
        optionality_status="mandatory",
        explanation="Motor vehicle insurance policy (own damage + mandatory third-party liability cover).",
        canonical_keywords=(
            "ins.",
            "ins",
            "insurance",
            "vehicle insurance",
            "motor insurance",
            "insurance premium",
            "comprehensive insurance",
            "zero dep insurance",
            "b2b insurance",
        ),
        regex_patterns=_compile_patterns(
            [
                r"\bins[\s\.]*(?:premium|charges?|amount)?\b",
                r"\bins[ou]ranc[ef]\b",
                r"\binsur\.\b",
                r"\binsurance\b",
                r"\bmotor\s+insurance\b",
                r"\bvehicle\s+insurance\b",
                r"\bzero[\s\-_]*dep(?:reciation)?\b",
                r"\b(?:1|3|5)\s*(?:yr|year|years)\s*(?:od|tp)\b",
                r"\bcomprehensive\s+insurance\b",
                r"\bb2b\s+insurance\b",
            ]
        ),
    ),
    ComponentCategory.EXTENDED_WARRANTY: SemanticCategoryDefinition(
        category=ComponentCategory.EXTENDED_WARRANTY,
        normalized_name="Extended warranty",
        default_nature=ChargeNature.CHARGE,
        optionality_status="optional",
        explanation="Optional manufacturer or dealer warranty prolonging mechanical coverage beyond standard term.",
        canonical_keywords=(
            "extended warranty",
            "ext warranty",
            "ext. warranty",
            "additional warranty",
            "ew",
            "e.w.",
            "shield warranty",
            "warranty extension",
        ),
        regex_patterns=_compile_patterns(
            [
                r"\bext(?:ended)?[\s\.\-_]*warranty\b",
                r"\bext[\s\.\-_]*warranty\b",
                r"\badd(?:itional)?[\s\.\-_]*warranty\b",
                r"\bshield\s+warranty\b",
                r"\be[\s\.]*w[\s\.]*(?:charges?|fee)?\b",
                r"\bwarranty\s+extension\b",
            ]
        ),
    ),
    ComponentCategory.WARRANTY: SemanticCategoryDefinition(
        category=ComponentCategory.WARRANTY,
        normalized_name="Warranty",
        default_nature=ChargeNature.CHARGE,
        optionality_status="recommended",
        explanation="Manufacturer standard factory warranty coverage against manufacturing defects.",
        canonical_keywords=(
            "warranty",
            "std warranty",
            "standard warranty",
            "factory warranty",
            "oem warranty",
            "basic warranty",
        ),
        regex_patterns=_compile_patterns(
            [
                r"\bstd[\s\.\-_]*warranty\b",
                r"\bstandard\s+warranty\b",
                r"\bfactory\s+warranty\b",
                r"\boem\s+warranty\b",
                r"\bwarranty\b",
            ]
        ),
    ),
    ComponentCategory.ACCESSORY_PACKAGE: SemanticCategoryDefinition(
        category=ComponentCategory.ACCESSORY_PACKAGE,
        normalized_name="Accessories package",
        default_nature=ChargeNature.CHARGE,
        optionality_status="optional",
        explanation="Bundled package of vehicle accessories offered by the dealership.",
        canonical_keywords=(
            "accessories package",
            "accessory package",
            "dealer accessories",
            "accessory kit",
            "essential kit",
            "basic accessories kit",
            "accessories combo",
        ),
        regex_patterns=_compile_patterns(
            [
                r"\baccessor(?:y|ies)\s*(?:package|kit|combo|pack|bundle)\b",
                r"\bdealer\s+accessor(?:y|ies)\b",
                r"\bessential\s+kit\b",
                r"\bbasic\s+kit\b",
            ]
        ),
    ),
    ComponentCategory.ACCESSORY: SemanticCategoryDefinition(
        category=ComponentCategory.ACCESSORY,
        normalized_name="Accessories",
        default_nature=ChargeNature.CHARGE,
        optionality_status="optional",
        explanation="Individual aftermarket or cosmetic accessory items.",
        canonical_keywords=(
            "accessories",
            "accessory",
            "acc.",
            "acc",
            "accs",
            "accs.",
            "seat cover",
            "floor mats",
            "mud flaps",
            "body cover",
            "sun film",
            "door visor",
        ),
        regex_patterns=_compile_patterns(
            [
                r"\baccessor(?:y|ies)\b",
                r"\bacc(?:s)?[\s\.]*(?:kit|package|charges?|items?)?\b",
                r"\bseat\s+covers?\b",
                r"\bfloor\s+mats?\b",
                r"\bmud\s+flaps?\b",
                r"\bbody\s+cover\b",
            ]
        ),
    ),
    ComponentCategory.FASTAG: SemanticCategoryDefinition(
        category=ComponentCategory.FASTAG,
        normalized_name="FASTag",
        default_nature=ChargeNature.CHARGE,
        optionality_status="mandatory",
        explanation="Electronic toll collection RFID sticker mandatory for all motorized vehicles in India.",
        canonical_keywords=("fastag", "fast tag", "fas tag", "fast-tag", "toll tag", "etc tag"),
        regex_patterns=_compile_patterns(
            [
                r"\bfas[\s\-_]*tag\b",
                r"\btoll\s+tag\b",
            ]
        ),
    ),
    ComponentCategory.HANDLING_FEE: SemanticCategoryDefinition(
        category=ComponentCategory.HANDLING_FEE,
        normalized_name="Handling charges",
        default_nature=ChargeNature.CHARGE,
        optionality_status="optional",
        explanation="Dealer-levied vehicle handling or inspection fee (frequently disputed and ruled unlawful by consumer forums).",
        canonical_keywords=(
            "handling",
            "handling charges",
            "handling fee",
            "depot charges",
            "incidental charges",
            "pdi charges",
            "pdi",
            "p.d.i.",
        ),
        regex_patterns=_compile_patterns(
            [
                r"\bhandling\s*(?:charges?|fees?|fee)?\b",
                r"\bdepot\s*(?:charges?|fees?)?\b",
                r"\bincidental\s*(?:charges?|fees?)?\b",
                r"\bp[\s\.]*d[\s\.]*i[\s\.]*(?:charges?|fee)?\b",
            ]
        ),
    ),
    ComponentCategory.LOGISTICS_FEE: SemanticCategoryDefinition(
        category=ComponentCategory.LOGISTICS_FEE,
        normalized_name="Logistics charges",
        default_nature=ChargeNature.CHARGE,
        optionality_status="optional",
        explanation="Transportation or freight charges for moving goods from manufacturer warehouse to dealership.",
        canonical_keywords=(
            "logistics",
            "logistics charges",
            "logistics fee",
            "freight",
            "freight charges",
            "transportation charges",
        ),
        regex_patterns=_compile_patterns(
            [
                r"\blogistics?\s*(?:charges?|fees?|fee)?\b",
                r"\bfreight\s*(?:charges?|fees?|fee)?\b",
                r"\btransport(?:ation)?\s*(?:charges?|fee)?\b",
            ]
        ),
    ),
    ComponentCategory.PROCESSING_FEE: SemanticCategoryDefinition(
        category=ComponentCategory.PROCESSING_FEE,
        normalized_name="Processing / documentation fee",
        default_nature=ChargeNature.CHARGE,
        optionality_status="optional",
        explanation="Administrative processing, file opening, or paperwork facilitation fee.",
        canonical_keywords=(
            "processing",
            "processing fee",
            "processing charges",
            "documentation charges",
            "doc charges",
            "file charges",
        ),
        regex_patterns=_compile_patterns(
            [
                r"\bprocessing\s*(?:charges?|fees?|fee)?\b",
                r"\bdoc(?:umentation)?\s*(?:charges?|fees?|fee)?\b",
                r"\bfile\s*(?:charges?|fees?|fee)?\b",
            ]
        ),
    ),
    ComponentCategory.SERVICE_PACKAGE: SemanticCategoryDefinition(
        category=ComponentCategory.SERVICE_PACKAGE,
        normalized_name="Service package / AMC",
        default_nature=ChargeNature.CHARGE,
        optionality_status="optional",
        explanation="Periodic maintenance contract, annual service package, or roadside assistance agreement.",
        canonical_keywords=(
            "service package",
            "amc",
            "annual maintenance",
            "maintenance contract",
            "rsa",
            "roadside assistance",
        ),
        regex_patterns=_compile_patterns(
            [
                r"\bservice\s*(?:package|pack|contract)\b",
                r"\ba[\s\.]*m[\s\.]*c\b",
                r"\bannual\s+maintenance\s*(?:contract)?\b",
                r"\br[\s\.]*s[\s\.]*a\b",
                r"\broad[\s\-_]*side\s+assistance\b",
            ]
        ),
    ),
    ComponentCategory.DEALER_PACKAGE: SemanticCategoryDefinition(
        category=ComponentCategory.DEALER_PACKAGE,
        normalized_name="Dealer package",
        default_nature=ChargeNature.CHARGE,
        optionality_status="optional",
        explanation="Dealership-specific optional enhancement or delivery package.",
        canonical_keywords=("dealer package", "dealer kit", "showroom package", "delivery package"),
        regex_patterns=_compile_patterns(
            [
                r"\bdealer\s*(?:package|kit|pack)\b",
                r"\bshowroom\s*(?:package|kit|pack)\b",
                r"\bdelivery\s*(?:package|kit|pack)\b",
            ]
        ),
    ),
    ComponentCategory.OTHER_FEE: SemanticCategoryDefinition(
        category=ComponentCategory.OTHER_FEE,
        normalized_name="Other fee / charges",
        default_nature=ChargeNature.CHARGE,
        optionality_status="optional",
        explanation="Ancillary fee, convenience fee, or miscellaneous surcharge.",
        canonical_keywords=(
            "fee",
            "charges",
            "convenience fee",
            "service fee",
            "platform fee",
            "miscellaneous charges",
        ),
        regex_patterns=_compile_patterns(
            [
                r"\bconvenience\s*(?:fee|charges?)\b",
                r"\bplatform\s*(?:fee|charges?)\b",
                r"\bmisc(?:ellaneous)?\s*(?:charges?|fees?|fee)?\b",
                r"\bsurcharge\b",
                r"\bcharges?\b",
                r"\bfees?\b",
            ]
        ),
    ),
    ComponentCategory.OFFER: SemanticCategoryDefinition(
        category=ComponentCategory.OFFER,
        normalized_name="Dealer offer",
        default_nature=ChargeNature.DEDUCTION,
        optionality_status="recommended",
        explanation="Commercial dealer offer, extra promotional incentive, or festival trade bonus reducing payable total.",
        canonical_keywords=(
            "offer",
            "offers",
            "dealer offer",
            "extra offer",
            "special offer",
            "promotional offer",
            "consumer offer",
            "exchange bonus",
        ),
        regex_patterns=_compile_patterns(
            [
                r"\bextra\s+offer\b",
                r"\bdealer\s+offer\b",
                r"\bconsumer\s+offer\b",
                r"\bexchange\s+bonus\b",
                r"\bspecial\s+offer\b",
                r"\boffers?\b",
            ]
        ),
    ),
    ComponentCategory.DISCOUNT: SemanticCategoryDefinition(
        category=ComponentCategory.DISCOUNT,
        normalized_name="Discount",
        default_nature=ChargeNature.DEDUCTION,
        optionality_status="recommended",
        explanation="Contractual price concession, cash deduction, or promotional discount reducing gross charge.",
        canonical_keywords=(
            "discount",
            "discounts",
            "disc.",
            "disc",
            "total discount",
            "cash discount",
            "trade discount",
            "rebate",
            "concession",
            "deduction",
            "less",
            "minus",
        ),
        regex_patterns=_compile_patterns(
            [
                r"\btotal\s+discount\b",
                r"\bcash\s+discount\b",
                r"\btrade\s+discount\b",
                r"\bdisc[\s\.]*(?:amount|charges?)?\b",
                r"\bdiscounts?\b",
                r"\brebate\b",
                r"\bconcession\b",
                r"\bdeduction\b",
                r"\bless\b",
                r"\bminus\b",
            ]
        ),
    ),
    ComponentCategory.SUBTOTAL: SemanticCategoryDefinition(
        category=ComponentCategory.SUBTOTAL,
        normalized_name="Subtotal",
        default_nature=ChargeNature.CHARGE,
        optionality_status="mandatory",
        explanation="Aggregated sum of all constituent charges prior to deduction of trade discounts or offers.",
        canonical_keywords=(
            "subtotal",
            "sub-total",
            "sub total",
            "total before offers",
            "gross total",
            "total charges",
        ),
        regex_patterns=_compile_patterns(
            [
                r"\bsub[\s\.\-_]*total\b",
                r"\btotal\s+before\s+offers?\b",
                r"\bgross\s+total\b",
                r"\btotal\s+charges?\b",
            ]
        ),
    ),
    ComponentCategory.TOTAL: SemanticCategoryDefinition(
        category=ComponentCategory.TOTAL,
        normalized_name="Total amount",
        default_nature=ChargeNature.CHARGE,
        optionality_status="mandatory",
        explanation="Final on-road or net payable monetary commitment.",
        canonical_keywords=(
            "total",
            "on-road total",
            "on road price",
            "quoted total",
            "grand total",
            "net payable",
            "amount payable",
        ),
        regex_patterns=_compile_patterns(
            [
                r"\bon[\s\-_]*road\s*(?:total|price|cost)?\b",
                r"\bquoted\s+total\b",
                r"\bgrand\s+total\b",
                r"\bnet\s+(?:total|amount|payable)\b",
                r"\bamount\s+payable\b",
                r"\btotal\s+payable\b",
                r"\bfinal\s+amount\b",
                r"\btotal\b",
            ]
        ),
    ),
    ComponentCategory.AMOUNT_PAID: SemanticCategoryDefinition(
        category=ComponentCategory.AMOUNT_PAID,
        normalized_name="Amount paid",
        default_nature=ChargeNature.DEDUCTION,
        optionality_status="mandatory",
        explanation="Advance deposit, booking amount, or previous remittance already credited.",
        canonical_keywords=(
            "amount paid",
            "total paid",
            "paid",
            "advance",
            "advance paid",
            "booking amount",
            "token amount",
            "down payment",
        ),
        regex_patterns=_compile_patterns(
            [
                r"\bamount\s+paid\b",
                r"\btotal\s+paid\b",
                r"\badvance\s*(?:paid|amount)?\b",
                r"\bbooking\s+amount\b",
                r"\bdown\s+payment\b",
                r"\btoken\s+amount\b",
                r"\bpaid\b",
            ]
        ),
    ),
    ComponentCategory.BALANCE_DUE: SemanticCategoryDefinition(
        category=ComponentCategory.BALANCE_DUE,
        normalized_name="Balance due",
        default_nature=ChargeNature.CHARGE,
        optionality_status="mandatory",
        explanation="Remaining balance due payable by the user to complete the settlement.",
        canonical_keywords=(
            "balance due",
            "amount due",
            "net due",
            "balance payable",
            "remaining payable",
        ),
        regex_patterns=_compile_patterns(
            [
                r"\bbalance\s+(?:due|payable|amount)\b",
                r"\bamount\s+due\b",
                r"\bnet\s+due\b",
                r"\bremaining\s+(?:due|payable|amount)\b",
            ]
        ),
    ),
    ComponentCategory.UNKNOWN: SemanticCategoryDefinition(
        category=ComponentCategory.UNKNOWN,
        normalized_name="Unclassified component",
        default_nature=ChargeNature.CHARGE,
        optionality_status="optional",
        explanation="Unclassified or custom line charge requiring manual review.",
        canonical_keywords=(),
        regex_patterns=(),
    ),
    ComponentCategory.UNCLEAR: SemanticCategoryDefinition(
        category=ComponentCategory.UNCLEAR,
        normalized_name="Unclear",
        default_nature=ChargeNature.CHARGE,
        optionality_status="unknown",
        explanation="Unclear charge with insufficient contextual evidence to categorize.",
        canonical_keywords=(),
        regex_patterns=(),
    ),
    ComponentCategory.TAX_OR_STATUTORY: SemanticCategoryDefinition(
        category=ComponentCategory.TAX_OR_STATUTORY,
        normalized_name="Tax / Statutory",
        default_nature=ChargeNature.CHARGE,
        optionality_status="mandatory",
        explanation="Mandatory government tax, levy, cess, or statutory charge.",
        canonical_keywords=("statutory", "tax or statutory", "statutory charges", "govt levy"),
        regex_patterns=_compile_patterns(
            [
                r"\bstatutory\s*(?:charges?|tax|fees?)?\b",
                r"\btax\s*or\s*statutory\b",
            ]
        ),
    ),
    ComponentCategory.SERVICE: SemanticCategoryDefinition(
        category=ComponentCategory.SERVICE,
        normalized_name="Service",
        default_nature=ChargeNature.CHARGE,
        optionality_status="optional",
        explanation="Vehicle service package, labor, periodic maintenance, or roadside assistance.",
        canonical_keywords=("service", "service charges", "labor", "labour", "maintenance"),
        regex_patterns=_compile_patterns(
            [
                r"\bservice\s*(?:charges?|fees?|cost)?\b",
                r"\blabou?r\s*(?:charges?|cost)?\b",
            ]
        ),
    ),
    ComponentCategory.DEALER_CHARGE: SemanticCategoryDefinition(
        category=ComponentCategory.DEALER_CHARGE,
        normalized_name="Dealer charge",
        default_nature=ChargeNature.CHARGE,
        optionality_status="optional",
        explanation="Dealer-levied handling, documentation, processing, or logistics fee.",
        canonical_keywords=("dealer charge", "dealer charges", "dealer fee"),
        regex_patterns=_compile_patterns(
            [
                r"\bdealer\s*(?:charges?|fees?|fee)\b",
            ]
        ),
    ),
    ComponentCategory.FINANCING: SemanticCategoryDefinition(
        category=ComponentCategory.FINANCING,
        normalized_name="Financing",
        default_nature=ChargeNature.CHARGE,
        optionality_status="optional",
        explanation="Vehicle financing, loan origination, hypothecation, or EMI facilitation charge.",
        canonical_keywords=(
            "finance",
            "financing",
            "loan",
            "hypothecation",
            "hp charges",
            "h.p. charges",
            "emi",
            "processing fee loan",
            "documentation charges loan",
            "loan charges",
            "finance charge",
            "finance fee",
        ),
        regex_patterns=_compile_patterns(
            [
                r"\b(?:loan|finance|financing)\s*(?:charges?|fees?|cost)?\b",
                r"\bh[\s\.]*p[\s\.]*(?:charges?|fees?|fee)?\b",
                r"\bhypothecation\s*(?:charges?|fee)?\b",
                r"\bemi\s*(?:charges?|fee|processing)?\b",
                r"\bloan\s+origination\b",
            ]
        ),
    ),
}

# Add backward compatibility for ACCESSORY_OR_FEE and OTHER
TAXONOMY_DEFINITIONS[ComponentCategory.ACCESSORY_OR_FEE] = TAXONOMY_DEFINITIONS[
    ComponentCategory.OTHER_FEE
]
TAXONOMY_DEFINITIONS[ComponentCategory.OTHER] = TAXONOMY_DEFINITIONS[ComponentCategory.UNKNOWN]


# Precedence order when scanning rules
CATEGORY_PRECEDENCE = [
    # 1. Exact compound or distinct vehicle charges first
    ComponentCategory.EX_SHOWROOM_PRICE,
    ComponentCategory.EXTENDED_WARRANTY,
    ComponentCategory.ACCESSORY_PACKAGE,
    ComponentCategory.SERVICE_PACKAGE,
    ComponentCategory.DEALER_PACKAGE,
    ComponentCategory.HANDLING_FEE,
    ComponentCategory.LOGISTICS_FEE,
    ComponentCategory.PROCESSING_FEE,
    ComponentCategory.FINANCING,
    ComponentCategory.ROAD_TAX,
    ComponentCategory.HSRP,
    ComponentCategory.FASTAG,
    ComponentCategory.TCS,
    ComponentCategory.GST,
    ComponentCategory.RC,
    ComponentCategory.REGISTRATION,
    ComponentCategory.INSURANCE,
    ComponentCategory.WARRANTY,
    ComponentCategory.ACCESSORY,
    ComponentCategory.SUBTOTAL,
    ComponentCategory.OFFER,
    ComponentCategory.DISCOUNT,
    ComponentCategory.TOTAL,
    ComponentCategory.AMOUNT_PAID,
    ComponentCategory.BALANCE_DUE,
    ComponentCategory.BASE_PRICE,
    ComponentCategory.TAX,
    ComponentCategory.OTHER_FEE,
]


def get_canonical_category(category: ComponentCategory | str) -> ComponentCategory:
    """Map any fine-grained or string category to one of the 11 established canonical categories."""
    if isinstance(category, str):
        try:
            cat_enum = ComponentCategory(category)
        except ValueError:
            return ComponentCategory.OTHER
    else:
        cat_enum = category
    return cat_enum.to_canonical_category()


def clean_component_text(raw_text: str) -> str:
    """Normalize raw OCR string for matching without losing original text."""
    if not raw_text:
        return ""
    text = raw_text.strip()
    # Strip monetary symbols, figures, and colons at the end or beginning
    text = re.sub(
        r"^(?:item\s*\d+|s\.?no\.?\s*\d+|#\s*\d+)\s*[:\.\-_]?", "", text, flags=re.IGNORECASE
    )
    # Strip trailing numbers / currency / Indian /- notation: e.g. "Ex-Showroom: ₹11,49,900" or "XYZ ₹5,000/-"
    text = re.sub(
        r"(?:[:=]|\s+[-–—]\s+)?\s*(?:[₹$€£¥]|rs\.?|inr)?\s*[0-9]+(?:[,.][0-9]+)*(?:\s*\/\s*[-–—]?)?\s*$",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # Clean leading/trailing punctuation
    text = text.strip(" :;=–—-·•\t\r\n")
    return text


def fix_ocr_letter_digit_noise(text: str) -> str:
    """Repair common OCR letter-digit confusions and noise in financial labels.

    Examples:
    - 'SHOWR00M' -> 'SHOWROOM' (zeroes in letters)
    - 'INSURANCF' -> 'INSURANCE' (terminal F mistaken for E)
    - 'INSORANCE' -> 'INSURANCE' (vowel substitution O for U)
    - 'INSUR.' -> 'INSURANCE' (abbreviation)
    """
    if not text:
        return ""
    t = text
    # Replace zeroes between letters e.g. SHOWR00M -> SHOWROOM
    prev = None
    while prev != t:
        prev = t
        t = re.sub(r"([a-zA-Z])0([a-zA-Z0-9]*)", lambda m: m.group(1) + "O" + m.group(2), t)

    # Known OCR corruptions in financial terminology
    t = re.sub(r"\binsuranc[ef]\b", "INSURANCE", t, flags=re.IGNORECASE)
    t = re.sub(r"\binsorance\b", "INSURANCE", t, flags=re.IGNORECASE)
    return t


def normalize_financial_label(raw_text: str) -> str:
    """Produce a clean, normalized human-readable label from raw OCR text while preserving evidence.

    Deterministic aliases and semantic rules:
    - EX-SHOWR00M / EX SHOWROOM -> 'Ex-showroom'
    - INSORANCE / INSUR. / INSURANCF -> 'Insurance'
    - R.C. / REGN. -> 'Registration'
    - EXT WARRANTY -> 'Extended Warranty'
    - Normal spellings -> Canonical clean spelling
    - Unknown text -> Cleaned raw text (never invents a category without evidence)
    """
    if not raw_text:
        return ""

    cleaned = clean_component_text(raw_text)
    if not cleaned:
        return ""

    repaired = fix_ocr_letter_digit_noise(cleaned)
    rep_lower = repaired.lower().strip()

    # 1. Deterministic aliases for vehicle quotation components
    # Ex-showroom
    if re.search(r"\bex[\s\.\-_]*showr[o0]{2}m\b", rep_lower) or re.search(
        r"\bex[\s\.\-_]*showroom\b", rep_lower
    ):
        return "Ex-showroom"

    # Insurance
    if re.fullmatch(
        r"(ins[ou]ranc[ef]|insur\.?|insurance)(\s+(premium|charges?|cost|policy))?", rep_lower
    ):
        return "Insurance"
    if re.search(r"\b(ins[ou]ranc[ef]|insur\.)\b", rep_lower):
        return "Insurance"

    # Registration / R.C. / REGN.
    if re.fullmatch(
        r"(r[\s\.]*c[\s\.]*|regn[\s\.]*|registration)(\s+(charges?|fees?|cost))?", rep_lower
    ):
        return "Registration"
    if re.fullmatch(r"r[\s\.]*c[\s\.]*", rep_lower) or re.fullmatch(r"regn[\s\.]*", rep_lower):
        return "Registration"

    # Extended Warranty
    if re.fullmatch(r"(ext|extd|extended)[\s\.\-_]+warranty(\s+(charges?|cost))?", rep_lower):
        return "Extended Warranty"
    if re.search(r"\b(ext|extd|extended)[\s\.\-_]+warranty\b", rep_lower):
        return "Extended Warranty"

    # Standard Warranty
    if re.fullmatch(r"(std|standard|factory|basic)?\s*warranty(\s+(charges?|cost))?", rep_lower):
        return "Warranty"

    # TCS
    if re.fullmatch(r"t[\s\.]*c[\s\.]*s(\s*@?\s*1%?)?", rep_lower):
        return "TCS"

    # HSRP
    if re.fullmatch(r"(temp\s*\+?\s*)?h[\s\.]*s[\s\.]*r[\s\.]*p(\s+(charges?|fee))?", rep_lower):
        return "HSRP"

    # FASTag
    if re.fullmatch(r"fas[\s\-_]*tag", rep_lower):
        return "FASTag"

    # Accessories
    if re.fullmatch(
        r"(essential\s+kit|basic\s+kit|(dealer\s+)?accessor(?:y|ies)(\s+package|\s+kit)?)",
        rep_lower,
    ):
        return "Accessories"

    # Road Tax
    if re.fullmatch(r"(road\s*tax|rd[\s\.]*tax|motor\s+vehicle\s+tax)", rep_lower):
        return "Road Tax"

    # Offers / Discounts
    if re.fullmatch(r"extra\s+offer", rep_lower):
        return "Extra Offer"
    if re.fullmatch(r"(dealer\s+|special\s+)?offers?", rep_lower):
        return "Offer"
    if re.fullmatch(r"(cash\s+|trade\s+)?discounts?", rep_lower):
        return "Discount"

    # Financing / Loan / Hypothecation
    if re.fullmatch(
        r"(loan|finance|financing|hypothecation|h[\s\.]*p)(\s+(charges?|fees?|fee|cost|processing))?",
        rep_lower,
    ):
        return "Financing"

    # Base price / basic price
    if re.fullmatch(r"(base|basic|vehicle)(\s+(price|amount|cost|rate))", rep_lower):
        return "Base Price"

    # Fallback to taxonomy classification for other known components
    cat, norm_name, _, _, _ = classify_component_name(repaired)
    if cat not in (ComponentCategory.UNKNOWN, ComponentCategory.UNCLEAR, ComponentCategory.OTHER):
        return norm_name

    # If uncertain, preserve original cleaned text without guessing
    return cleaned


def classify_component_name(raw_name: str) -> tuple[ComponentCategory, str, ChargeNature, str, str]:
    """Classify a component string into (category, normalized_name, charge_nature, optionality, explanation).

    Never relies on exact string equality alone; uses clean canonical token matching,
    regex expressions, OCR noise correction, and fuzzy edit-distance fallback.
    """
    cleaned = clean_component_text(raw_name)
    if not cleaned:
        defn = TAXONOMY_DEFINITIONS[ComponentCategory.UNCLEAR]
        return (
            defn.category,
            defn.normalized_name,
            defn.default_nature,
            defn.optionality_status,
            defn.explanation,
        )

    # Pre-process with OCR noise correction for robust matching
    repaired = fix_ocr_letter_digit_noise(cleaned)
    cleaned_lower = repaired.lower()

    # 1. Regex rule matching with precedence
    for cat in CATEGORY_PRECEDENCE:
        defn = TAXONOMY_DEFINITIONS[cat]
        for pattern in defn.regex_patterns:
            if pattern.search(cleaned_lower):
                # Contextual disambiguation:
                # E.g. "R.C." vs "R.C. & Road Tax": if both road tax and rc mentioned, categorize as ROAD_TAX or REGISTRATION
                if cat == ComponentCategory.RC and (
                    "road tax" in cleaned_lower or "tax" in cleaned_lower
                ):
                    road_defn = TAXONOMY_DEFINITIONS[ComponentCategory.ROAD_TAX]
                    return (
                        road_defn.category,
                        road_defn.normalized_name,
                        road_defn.default_nature,
                        road_defn.optionality_status,
                        road_defn.explanation,
                    )
                if cat == ComponentCategory.WARRANTY and any(
                    w in cleaned_lower for w in ["ext", "extended", "additional", "ew"]
                ):
                    ext_defn = TAXONOMY_DEFINITIONS[ComponentCategory.EXTENDED_WARRANTY]
                    return (
                        ext_defn.category,
                        ext_defn.normalized_name,
                        ext_defn.default_nature,
                        ext_defn.optionality_status,
                        ext_defn.explanation,
                    )
                return (
                    defn.category,
                    defn.normalized_name,
                    defn.default_nature,
                    defn.optionality_status,
                    defn.explanation,
                )

    # 2. Canonical keyword substring check
    for cat in CATEGORY_PRECEDENCE:
        defn = TAXONOMY_DEFINITIONS[cat]
        for kw in defn.canonical_keywords:
            if kw in cleaned_lower:
                return (
                    defn.category,
                    defn.normalized_name,
                    defn.default_nature,
                    defn.optionality_status,
                    defn.explanation,
                )

    # 3. Fuzzy similarity fallback (SequenceMatcher) for OCR typos (e.g. "Exshowrom", "Insuranse", "Accesorries")
    best_match_cat = None
    best_score = 0.0

    # Strip all non-alphanumeric for distance check
    clean_alpha = re.sub(r"[^a-z0-9]", "", cleaned_lower)

    for cat in CATEGORY_PRECEDENCE:
        defn = TAXONOMY_DEFINITIONS[cat]
        for kw in defn.canonical_keywords:
            kw_alpha = re.sub(r"[^a-z0-9]", "", kw)
            ratio = difflib.SequenceMatcher(None, clean_alpha, kw_alpha).ratio()
            if ratio > best_score:
                best_score = ratio
                best_match_cat = cat

    # Acceptance threshold for fuzzy match
    if best_match_cat and best_score >= 0.78:
        defn = TAXONOMY_DEFINITIONS[best_match_cat]
        return (
            defn.category,
            defn.normalized_name,
            defn.default_nature,
            defn.optionality_status,
            defn.explanation,
        )

    # 4. Strict guardrail: Do not infer or invent a category when evidence is insufficient
    # Check if raw_name explicitly denotes an accounting deduction / negative adjustment (minus sign or parens)
    is_explicit_deduction = bool(
        re.search(r"[-–—]\s*(?:[₹$€£¥]|rs\.?|inr)?\s*[0-9]+", raw_name)
        or re.search(r"\(\s*(?:[₹$€£¥]|rs\.?|inr)?\s*[0-9]+(?:[,.][0-9]+)*\s*\)", raw_name)
    )
    if is_explicit_deduction:
        offer_defn = TAXONOMY_DEFINITIONS[ComponentCategory.OFFER]
        return (
            offer_defn.category,
            offer_defn.normalized_name,
            ChargeNature.DEDUCTION,
            offer_defn.optionality_status,
            offer_defn.explanation,
        )

    defn = TAXONOMY_DEFINITIONS[ComponentCategory.UNCLEAR]
    return (
        defn.category,
        cleaned,
        defn.default_nature,
        defn.optionality_status,
        "Unrecognized line component requiring verification.",
    )
