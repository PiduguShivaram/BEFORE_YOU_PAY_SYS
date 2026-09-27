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
  | "ex_showroom_price"
  | "tax"
  | "tcs"
  | "gst"
  | "insurance"
  | "registration"
  | "road_tax"
  | "rc"
  | "hsrp"
  | "warranty"
  | "extended_warranty"
  | "accessory"
  | "accessory_package"
  | "handling_fee"
  | "logistics_fee"
  | "processing_fee"
  | "fastag"
  | "dealer_package"
  | "service_package"
  | "other_fee"
  | "discount"
  | "offer"
  | "subtotal"
  | "total"
  | "amount_paid"
  | "balance_due"
  | "unknown"
  | "unclear"
  | "accessory_or_fee"
  | "other";

export type ChargeNature = "charge" | "deduction";

export type OptionalityStatus =
  | "confirmed_mandatory"
  | "confirmed_optional"
  | "potentially_optional"
  | "unclear"
  | "not_applicable"
  | "mandatory"
  | "optional";

export interface FinancialComponent {
  component_id: string;
  name: string;
  raw_name?: string;
  raw_label?: string;
  normalized_name?: string;
  normalized_label?: string;
  amount: ExtractedField;
  category: ComponentCategory;
  charge_nature: ChargeNature;
  charge_or_deduction?: "charge" | "deduction";
  optionality_status?: OptionalityStatus | string;
  optionality_display?: string | null;
  charge_status?: string | null;
  charge_status_display?: string | null;
  requires_verification?: boolean;
  document_states?: string | null;
  system_knows?: string | null;
  requires_confirmation?: string | null;
  is_optional: boolean;
  confidence?: number;
  evidence?: string;
  source_ocr_line?: string | null;
  bounding_box?: BoundingBox | null;
  page?: number | null;
  explanation?: string | null;
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
  extra_cost_analysis?: ExtraCostAnalysisResult | null;
  smart_questions?: SmartCostReductionQuestion[];
  cost_reduction_summary?: PotentialCostReductionSummary | null;
  plain_language_explanation?: PlainLanguageExplanation | null;
  raw_ocr_lines?: string[];
  ocr_lines?: OcrLine[];
  analysis_state?: AnalysisState;
  ocr_quality?: OCRQualityResult | null;
  generated_at: string;
}

export interface PlainLanguageExplanation {
  quoted_amount_sentence: string;
  base_price_sentence: string;
  charge_breakdown_sentences: string[];
  offers_sentence?: string | null;
  discrepancy_sentence?: string | null;
  clarification_heading: string;
  clarification_items: string[];
  full_explanation: string;
}

export interface ReductionTierItem {
  component_id: string;
  name: string;
  amount: number;
  category: string;
  status_label: string;
  evidence: string;
}

export interface PotentialCostReductionSummary {
  confirmed_optional_amount: number;
  confirmed_optional_items: ReductionTierItem[];
  potentially_optional_amount: number;
  potentially_optional_items: ReductionTierItem[];
  unclear_confirmation_amount: number;
  unclear_confirmation_items: ReductionTierItem[];
  min_potential_reduction: number;
  max_potential_reduction: number;
  potential_range_display: string;
  review_message: string;
  is_range_valid: boolean;
  total_charges_reviewed: number;
}

export interface SmartCostReductionQuestion {
  question_id: string;
  question: string;
  reason: string;
  related_charge: string;
  amount_involved?: number | null;
  potential_impact: string;
  evidence_source: string;
  confidence: number;
  category?: string | null;
  priority_score: number;
  ranking_factors?: Record<string, number>;
}

export type ExtraCostFlagType =
  | "potentially_optional"
  | "additional_charge"
  | "dealer_added"
  | "bundled_package"
  | "unclear_charge"
  | "possible_duplicate"
  | "requires_verification";

export interface ExtraCostFlag {
  component_id: string;
  flag_type: ExtraCostFlagType;
  flag_label: string;
  what: string;
  normalized_name: string;
  category: string;
  amount: number;
  why_flagged: string;
  what_to_verify: string;
  potential_saving: number | null;
  saving_language: string | null;
  bundled_questions: string[];
  evidence: string | null;
  optionality_status: string | null;
}

export interface ExtraCostAnalysisResult {
  flagged_costs: ExtraCostFlag[];
  total_potential_reduction: number;
  total_flagged_count: number;
  total_charges_analyzed: number;
  reduction_summary: string;
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

