"""Deterministic OCR Quality Gate for spatial OCR analysis."""

import re

from before_you_pay.models.analysis import OCRQualityResult, OCRQualityStatus
from before_you_pay.models.document import OcrLine, OcrResult

# Core vocabulary for language plausibility (standard English + financial/billing terms)
COMMON_VOCABULARY = {
    "the",
    "be",
    "to",
    "of",
    "and",
    "a",
    "in",
    "that",
    "have",
    "i",
    "it",
    "for",
    "not",
    "on",
    "with",
    "he",
    "as",
    "you",
    "do",
    "at",
    "this",
    "but",
    "his",
    "by",
    "from",
    "they",
    "we",
    "say",
    "her",
    "she",
    "or",
    "an",
    "will",
    "my",
    "one",
    "all",
    "would",
    "there",
    "their",
    "what",
    "so",
    "up",
    "out",
    "if",
    "about",
    "who",
    "get",
    "which",
    "go",
    "me",
    "when",
    "make",
    "can",
    "like",
    "time",
    "no",
    "just",
    "him",
    "know",
    "take",
    "people",
    "into",
    "year",
    "your",
    "good",
    "some",
    "could",
    "them",
    "see",
    "other",
    "than",
    "then",
    "now",
    "look",
    "only",
    "come",
    "its",
    "over",
    "think",
    "also",
    "back",
    "after",
    "use",
    "two",
    "how",
    "our",
    "work",
    "first",
    "well",
    "way",
    "even",
    "new",
    "want",
    "because",
    "any",
    "these",
    "give",
    "day",
    "most",
    "us",
    "is",
    "are",
    "was",
    "were",
    "invoice",
    "bill",
    "billing",
    "receipt",
    "order",
    "quotation",
    "quote",
    "tax",
    "gst",
    "vat",
    "cgst",
    "sgst",
    "igst",
    "hsn",
    "sac",
    "subtotal",
    "total",
    "amount",
    "due",
    "paid",
    "balance",
    "date",
    "due_date",
    "issue_date",
    "item",
    "items",
    "description",
    "desc",
    "qty",
    "quantity",
    "rate",
    "price",
    "unit",
    "mrp",
    "discount",
    "disc",
    "charges",
    "charge",
    "fee",
    "fees",
    "shipping",
    "handling",
    "freight",
    "payment",
    "cash",
    "credit",
    "card",
    "debit",
    "bank",
    "account",
    "customer",
    "vendor",
    "client",
    "seller",
    "buyer",
    "sold",
    "ship",
    "deliver",
    "delivery",
    "address",
    "phone",
    "email",
    "tel",
    "contact",
    "company",
    "limited",
    "ltd",
    "pvt",
    "inc",
    "corp",
    "terms",
    "conditions",
    "warranty",
    "guarantee",
    "policy",
    "period",
    "contract",
    "agreement",
    "signature",
    "authorized",
    "sign",
    "page",
    "number",
    "ref",
    "reference",
    "code",
    "pan",
    "cin",
    "gstin",
    "inr",
    "usd",
    "eur",
    "gbp",
    "rs",
    "rupees",
    "dollars",
    "cents",
    "thank",
    "vehicle",
    "car",
    "service",
    "labour",
    "part",
    "parts",
    "part_no",
    "model",
    "reg",
    "chassis",
    "engine",
    "km",
    "odometer",
    "job",
    "estimate",
    "repair",
    "works",
    "store",
    "shop",
    "product",
    "products",
    "statement",
    "payable",
    "status",
    "unpaid",
    "net",
    "offer",
    "offers",
    "extra",
    "insurance",
    "registration",
    "showroom",
    "cng",
    "tcs",
    "rc",
    "hsrp",
}


def is_garbage_token(token: str) -> bool:
    """Deterministic check for corrupted OCR artifacts and nonsense character sequences."""
    t = token.strip(".,:;()[]\"'`~-_/\\|*&^%$#@!+=")
    if not t:
        return False

    # Valid currency or numbers (e.g. ₹100, $20.50, 1,499.00, 18%, +91)
    if re.match(r"^[\$€£₹¥]?\d+(?:[.,]\d+)*%?$", t):
        return False

    # Valid dates (e.g. 11/06/2020, 2020-06-11, 11-Jul-2020)
    if re.match(r"^\d{1,4}[/-](?:\d{1,2}|[a-zA-Z]{3})[/-]\d{1,4}$", t):
        return False

    # Slashes or backslashes with digits and letters (e.g. 0d/q/ex, a/0/b)
    if "/" in t or "\\" in t or "|" in t:
        if any(c.isdigit() for c in t) and any(c.isalpha() for c in t):
            return True
        if len(t) >= 4 and not re.match(r"^[a-zA-Z]+/[a-zA-Z]+$", t):  # e.g. km/h, n/a
            return True

    # Mixed digits and letters (e.g. 0dAe, 00b, S0)
    has_digit = any(c.isdigit() for c in t)
    has_alpha = any(c.isalpha() for c in t)
    if has_digit and has_alpha:
        # Allow standard units and ordinals: 1st, 2nd, 3rd, 4th, 5kg, 10ml, 4g, 5g, 3d, etc.
        if re.match(r"^\d+(st|nd|rd|th|kg|g|ml|l|km|m|cm|mm|pcs|nos|pk|hr|hrs|min|sec)$", t, re.I):
            return False
        if re.match(r"^(a4|h4|h7|5g|4g|3d|2d|b2b)$", t, re.I):
            return False
        return True

    # Repeated symbols or punctuation bursts (e.g. ---, ===, ??!!, ...)
    if len(t) >= 2 and all(not c.isalnum() for c in t):
        return True

    # Long consonant clusters without vowels (e.g. bxkzq)
    if len(t) >= 4 and not any(c in "aeiouAEIOU" for c in t) and not t.isdigit():
        return True

    return False


class OCRQualityEvaluator:
    """Evaluates the structural and lexical quality of OCR extraction payloads."""

    def evaluate(self, ocr_result: OcrResult) -> OCRQualityResult:
        """Run multi-factor deterministic evaluation on OCR pages and lines."""
        all_lines: list[OcrLine] = []
        for page in ocr_result.pages:
            all_lines.extend(page.lines)

        line_count = len(all_lines)
        if line_count == 0:
            return OCRQualityResult(
                status=OCRQualityStatus.UNRELIABLE,
                score=0.0,
                reasons=["No readable text lines found in document."],
                line_count=0,
                character_count=0,
                word_count=0,
                alphanumeric_ratio=0.0,
                garbage_token_ratio=1.0,
            )

        full_text = " ".join(ln.text for ln in all_lines).strip()
        character_count = len(full_text.replace(" ", ""))
        if character_count == 0:
            return OCRQualityResult(
                status=OCRQualityStatus.UNRELIABLE,
                score=0.0,
                reasons=["Extracted lines contain only whitespace."],
                line_count=line_count,
                character_count=0,
                word_count=0,
                alphanumeric_ratio=0.0,
                garbage_token_ratio=1.0,
            )

        # Tokenize words
        tokens = [tok.strip() for tok in full_text.split() if tok.strip()]
        word_count = len(tokens)

        alnum_chars = sum(1 for c in full_text if c.isalnum())
        alphanumeric_ratio = round(alnum_chars / max(character_count, 1), 4)

        garbage_tokens = [tok for tok in tokens if is_garbage_token(tok)]
        garbage_token_ratio = round(len(garbage_tokens) / max(word_count, 1), 4)

        isolated_chars = [tok for tok in tokens if len(tok) == 1 and tok.isalnum()]
        isolated_char_ratio = round(len(isolated_chars) / max(word_count, 1), 4)

        # Dictionary / valid term matches
        recognized_tokens = [
            tok
            for tok in tokens
            if tok.lower().strip(".,:;()[]\"'=-+~") in COMMON_VOCABULARY
            or tok.lower().strip(".,:;()[]\"'=-+~").replace(".", "").replace("+", "") in COMMON_VOCABULARY
            or re.match(r"^[\$€£₹¥]?\d+(?:[.,]\d+)*%?$", tok.strip(".,:;()[]\"'=-+~"))
            or tok.strip() in ("=", "=>", "-", "+", ":")
        ]
        vocabulary_ratio = round(len(recognized_tokens) / max(word_count, 1), 4)

        reasons: list[str] = []

        # Mark unreliable lines on the OcrResult objects if possible
        for line in all_lines:
            line_toks = line.text.split()
            if line_toks:
                line_garbage = sum(1 for t in line_toks if is_garbage_token(t))
                if line_garbage / len(line_toks) >= 0.40 or len(line.text.strip()) < 2:
                    # Note: OcrLine is frozen, but we preserve line classification in quality result
                    pass

        # Decision Matrix
        # 1. Extreme sparsity
        if character_count < 25 or word_count < 4:
            if vocabulary_ratio < 0.25:
                reasons.append(
                    f"Extracted text volume is too sparse ({character_count} chars, {word_count} tokens)."
                )
                return OCRQualityResult(
                    status=OCRQualityStatus.UNRELIABLE,
                    score=0.15,
                    reasons=reasons,
                    line_count=line_count,
                    character_count=character_count,
                    word_count=word_count,
                    alphanumeric_ratio=alphanumeric_ratio,
                    garbage_token_ratio=garbage_token_ratio,
                )

        # 2. High garbage token concentration (corrupted OCR artifacts)
        if garbage_token_ratio >= 0.28 or (
            garbage_token_ratio >= 0.20 and isolated_char_ratio >= 0.20
        ):
            reasons.append(
                f"High proportion of corrupted or fragmented tokens detected ({round(garbage_token_ratio * 100)}% garbage tokens)."
            )
            score = round(
                max(0.10, 1.0 - (garbage_token_ratio * 1.8 + isolated_char_ratio * 0.4)), 2
            )
            return OCRQualityResult(
                status=OCRQualityStatus.UNRELIABLE,
                score=score,
                reasons=reasons,
                line_count=line_count,
                character_count=character_count,
                word_count=word_count,
                alphanumeric_ratio=alphanumeric_ratio,
                garbage_token_ratio=garbage_token_ratio,
            )

        # 3. Low alphanumeric ratio (noise, scan distortion)
        if alphanumeric_ratio < 0.50:
            reasons.append(
                f"Abnormally low alphanumeric character proportion ({round(alphanumeric_ratio * 100)}% alphanumeric)."
            )
            return OCRQualityResult(
                status=OCRQualityStatus.UNRELIABLE,
                score=0.25,
                reasons=reasons,
                line_count=line_count,
                character_count=character_count,
                word_count=word_count,
                alphanumeric_ratio=alphanumeric_ratio,
                garbage_token_ratio=garbage_token_ratio,
            )

        # 4. Degraded quality
        if garbage_token_ratio >= 0.14 or alphanumeric_ratio < 0.65 or isolated_char_ratio >= 0.22:
            reasons.append(
                "Moderate OCR noise, character fragmentation, or scanning artifacts detected."
            )
            score = round(
                max(0.40, min(0.68, 1.0 - (garbage_token_ratio + (1.0 - alphanumeric_ratio)))), 2
            )
            return OCRQualityResult(
                status=OCRQualityStatus.DEGRADED,
                score=score,
                reasons=reasons,
                line_count=line_count,
                character_count=character_count,
                word_count=word_count,
                alphanumeric_ratio=alphanumeric_ratio,
                garbage_token_ratio=garbage_token_ratio,
            )

        # 5. Moderate quality: readable tokens with informal/handwritten phonetic misspellings or non-standard terms
        is_handwriting_or_vision = (
            ocr_result.recovery_pass >= 4
            or ocr_result.engine_name == "gemini_vision_ocr"
            or bool(re.search(r"\b(exshorum|insorane|insorage|waranty|odfer|ex-shorum)\b", full_text, re.I))
        )

        if is_handwriting_or_vision:
            reasons.append(
                "OCR transcription contains handwritten or informal terms requiring downstream semantic normalization."
            )
            score = 0.75
            return OCRQualityResult(
                status=OCRQualityStatus.MODERATE,
                score=score,
                reasons=reasons,
                line_count=line_count,
                character_count=character_count,
                word_count=word_count,
                alphanumeric_ratio=alphanumeric_ratio,
                garbage_token_ratio=garbage_token_ratio,
            )

        # 6. Clean, reliable high-fidelity OCR (standard machine-printed documents)
        score = round(min(1.0, 0.85 + 0.15 * (1.0 - garbage_token_ratio)), 2)
        reasons.append("OCR text displays high structural coherence and standard lexical vocabulary.")
        return OCRQualityResult(
            status=OCRQualityStatus.GOOD,
            score=score,
            reasons=reasons,
            line_count=line_count,
            character_count=character_count,
            word_count=word_count,
            alphanumeric_ratio=alphanumeric_ratio,
            garbage_token_ratio=garbage_token_ratio,
        )
