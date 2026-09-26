export type CoordinateUnit = "normalized_percentage" | "pixels";

export type AnalysisState =
  | "FINANCIAL_DATA_FOUND"
  | "NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR"
  | "OCR_UNRELIABLE"
  | "DOCUMENT_UNREADABLE"
  | "EXTRACTION_INCONCLUSIVE";

export type OCRQualityStatus = "GOOD" | "MODERATE" | "DEGRADED" | "UNRELIABLE";

export interface OCRQualityResult {
  status: OCRQualityStatus;
  score: number;
  reasons: string[];
  line_count: number;
  character_count: number;
  word_count: number;
  alphanumeric_ratio: number;
  garbage_token_ratio: number;
}

export interface OcrLine {
  line_id: string;
  page_id: string;
  document_id: string;
  line_number: number;
  text: string;
  raw_text?: string | null;
  bounding_box: BoundingBox;
  confidence?: number | null;
  is_unreliable?: boolean;
}

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
  coordinate_unit: CoordinateUnit;
}

export type DocumentClassification =
  | "quotation"
  | "cost_breakdown"
  | "bill"
  | "contract"
  | "subscription"
  | "warranty"
  | "invoice"
  | "other";

export type ValidationStatus = "PASS" | "FAIL" | "INCONCLUSIVE";
export type ValidationSeverity = "CRITICAL" | "WARNING" | "INFO";

export interface ValidationCheck {
  validation_id: string;
  check_code: string;
  status: ValidationStatus;
  input_field_ids: string[];
  expected_value: string | number | null;
  calculated_value: string | number | null;
  absolute_delta: number | null;
  severity: ValidationSeverity;
  message: string;
}

export type ClaimType =
  | "potential_issue"
  | "potential_overlap"
  | "requires_verification"
  | "additional_charge_detected"
  | "term_requiring_attention";

export type DecisionStatus =
  | "CLEAR"
  | "REQUIRES_ATTENTION"
  | "DISCREPANCY_DETECTED"
  | "CRITICAL_WARNING";

export interface DecisionFlag {
  flag_id: string;
  claim_type: ClaimType;
  label: string;
  message: string;
  severity: ValidationSeverity;
  associated_claim_id?: string | null;
  associated_validation_id?: string | null;
  field_ids: string[];
  bounding_boxes: BoundingBox[];
}

export interface ResultSummary {
  headline: string;
  overall_status: DecisionStatus;
  total_flags: number;
  requires_human_verification: boolean;
  analysis_state?: AnalysisState;
  ocr_quality?: OCRQualityResult | null;
}

export interface ReasoningClaim {
  claim_id: string;
  type: ClaimType;
  title: string;
  description: string;
  field_references: string[];
  rag_evidence_references: string[];
  okf_rule_references: string[];
  confidence: number;
}

export interface FieldProvenance {
  document_id: string;
  page_id: string;
  ocr_line_ids: string[];
  bounding_box?: BoundingBox | null;
  raw_text: string;
}

export interface ExtractedField {
  field_id: string;
  field_key: string;
  normalized_value: any;
  unit_or_currency?: string | null;
  confidence: number;
  provenance?: FieldProvenance | null;
}

export type ComponentCategory =
  | "base_price"
  | "tax"
  | "insurance"
  | "registration"
  | "warranty"
  | "accessory_or_fee"
  | "discount"
  | "subtotal"
  | "total"
  | "other";

export type ChargeNature = "charge" | "deduction";

export interface FinancialComponent {
  component_id: string;
  name: string;
  amount: ExtractedField;
  category: ComponentCategory;
  charge_nature: ChargeNature;
  is_optional: boolean;
}

export interface LineItem {
  item_id: string;
  description: ExtractedField;
  quantity?: ExtractedField | null;
  unit_price?: ExtractedField | null;
  total_price: ExtractedField;
  mrp?: ExtractedField | null;
  discount?: ExtractedField | null;
  discounts?: ExtractedField[];
}

export interface StructuredFinancialDocument {
  document_id: string;
  user_id: string;
  document_type: DocumentClassification;
  currency?: string | null;
  vendor_name?: ExtractedField | null;
  issued_date?: ExtractedField | null;
  due_date?: ExtractedField | null;
  subtotal?: ExtractedField | null;
  tax_amount?: ExtractedField | null;
  shipping_amount?: ExtractedField | null;
  discount_amount?: ExtractedField | null;
  amount_paid?: ExtractedField | null;
  balance_due?: ExtractedField | null;
  payment_status?: ExtractedField | null;
  fees?: ExtractedField[];
  taxes?: ExtractedField[];
  total_amount: ExtractedField;
  line_items: LineItem[];
  cost_breakdown?: FinancialComponent[];
  clauses_and_notes: ExtractedField[];
}

export interface FinalDecisionSupportResult {
  result_id: string;
  document_id: string;
  user_id: string;
  summary: ResultSummary;
  flags: DecisionFlag[];
  reasoning_claims: ReasoningClaim[];
  validation_checks: ValidationCheck[];
  document?: StructuredFinancialDocument | null;
  raw_ocr_lines?: string[];
  ocr_lines?: OcrLine[];
  analysis_state?: AnalysisState;
  ocr_quality?: OCRQualityResult | null;
  generated_at: string;
}

export interface RagRecord {
  id: string;
  type: DocumentClassification;
  content: string;
  indexedAt?: string;
}

export interface OkfRule {
  rule_id: string;
  rule_name: string;
  category: string;
  summary: string;
  source_reference: string;
  version: string;
  guidance: string;
}
