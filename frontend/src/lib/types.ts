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
  | "receipt"
  | "estimate"
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
  | "tax_or_statutory"
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
  | "service"
  | "dealer_charge"
  | "financing"
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

export type ChargeNature =
  | "charge"
  | "deduction"
  | "tax"
  | "statutory"
  | "discount"
  | "included"
  | "unknown";

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
  original_label?: string;
  raw_name?: string;
  raw_label?: string;
  normalized_name?: string;
  normalized_label?: string;
  amount: ExtractedField;
  amount_state?: string;
  category: ComponentCategory;
  canonical_category?: string;
  vehicle_category?: string;
  charge_nature: ChargeNature;
  charge_or_deduction?: "charge" | "deduction" | string;
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
  is_recurring?: boolean | null;
  billing_frequency?: string | null;
  effective_period?: string | null;
  period_start?: string | null;
  period_end?: string | null;
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
  suggested_negotiation_message?: string | null;
  supporting_document_context?: {
    supporting_document_id?: string;
    supporting_line_count?: number;
    chunks_indexed?: number;
    supporting_preview?: string;
    source_type?: string;
    filename?: string;
    evidence_count?: number;
    retrieved_snippets?: string[];
    potential_overlap_detected?: boolean;
    overlap_notes?: string;
  } | null;
  contextual_findings?: ContextualFinding[];
  supporting_document_analysis?: SupportingDocumentAnalysis | null;
  semantic_financial_structure?: {
    formula_type: string;
    formula_representation: string;
    relations: Array<{
      component_name: string;
      original_label: string;
      canonical_category: string;
      relation_type: string;
      amount: number | null;
      amount_state: string;
      confidence: number;
      evidence: string;
      is_recurring?: boolean | null;
      billing_frequency?: string | null;
    }>;
    calculated_sum?: number | null;
    stated_total?: number | null;
    discrepancy?: number | null;
    is_reconciled: boolean;
    currency?: string | null;
    summary_explanation: string;
  } | null;
  before_you_pay_summary?: BeforeYouPayFinalSummary | null;
  evidence_first_result?: EvidenceFirstResult | null;
  generated_at: string;
}

export type ContextualFindingType =
  | "POTENTIAL_OVERLAP"
  | "PRICE_VARIANCE"
  | "COVERAGE_COMPARISON"
  | "TERM_DIFFERENCE"
  | "NO_RELEVANT_CONTEXT";

export interface ContextualEvidence {
  document_role: "primary" | "supporting";
  document_id: string;
  source_document_type: string;
  raw_text: string;
  page_number: number;
  bounding_box?: BoundingBox | null;
  amount?: number | null;
  label?: string | null;
}

export interface ContextualFinding {
  finding_id: string;
  finding_type: ContextualFindingType;
  title: string;
  description: string;
  primary_evidence: ContextualEvidence[];
  supporting_evidence: ContextualEvidence[];
  what_to_verify: string[];
  questions_to_ask: string[];
  confidence: number;
  severity: "CRITICAL" | "WARNING" | "INFO";
  primary_amount?: number | null;
  supporting_amount?: number | null;
  delta_amount?: number | null;
}

export interface SupportingDocumentAnalysis {
  supporting_document_id: string;
  supporting_document_type: string;
  supporting_line_count: number;
  chunks_indexed: number;
  supporting_preview?: string | null;
  findings: ContextualFinding[];
  retrieved_chunks_count: number;
}



export interface PlainLanguageExplanation {
  quoted_amount_sentence: string;
  base_price_sentence: string;
  charge_breakdown_sentences: string[];
  offers_sentence?: string | null;
  discrepancy_sentence?: string | null;
  clarification_heading: string;
  clarification_items: string[];
  suggested_message?: string | null;
  suggested_negotiation_message?: string | null;
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
  classification?: string | null;
  suggested_action?: string | null;
  document_id?: string | null;
  page_number?: number | null;
  ocr_line?: string | null;
  bounding_box?: BoundingBox | null;
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

// ── Phase 6: Before You Pay Final Decision Summary ──

export type AmountState =
  | "PRESENT"
  | "ZERO"
  | "MISSING"
  | "UNREADABLE"
  | "NOT_APPLICABLE"
  | "UNKNOWN"
  | string;

export type PaymentReadinessState =
  | "READY_FOR_FINAL_VERIFICATION"
  | "REQUIRES_VERIFICATION"
  | "INCOMPLETE_INFORMATION";

export type ChecklistItemStatus =
  | "VERIFIED"
  | "REQUIRES_VERIFICATION"
  | "PENDING_USER_ACTION"
  | "NOT_APPLICABLE";

export interface BeforeYouPayChecklistItem {
  key: string;
  title: string;
  status: ChecklistItemStatus;
  detail: string;
  evidence?: string | null;
}

export interface BeforeYouPayChecklist {
  items: BeforeYouPayChecklistItem[];
  overall_status: ChecklistItemStatus;
  completed_count: number;
  total_count: number;
}

export interface InformationCompleteness {
  is_complete_to_calculate: boolean;
  is_complete_to_explain: boolean;
  is_complete_to_verify: boolean;
  missing_or_uncertain_fields: string[];
  completeness_note: string;
}

export interface CanonicalFinancialSummaryItem {
  canonical_category: string;
  name: string;
  amount: number | null;
  amount_state: AmountState;
  charge_nature: string;
  formatted_amount: string;
  is_deduction: boolean;
}

export interface DecisionHero {
  quoted_total: number | null;
  stated_total: number | null;
  formatted_total: string;
  currency: string;
  payment_status: string;
  balance_due: number | null;
  formatted_balance_due?: string | null;
  review_status: string;
  readiness_state: PaymentReadinessState;
}

export interface ReconciliationThreeTier {
  component_tier_total: number | null;
  formatted_component_total: string;
  component_count: number;
  unreadable_component_count: number;
  stated_subtotal: number | null;
  formatted_stated_subtotal?: string | null;
  subtotal_reconciled: boolean;
  offers_tier_total: number;
  formatted_offers_total: string;
  offers_count: number;
  quoted_total: number | null;
  formatted_quoted_total: string;
  quoted_total_reconciled: boolean;
  discrepancy_amount?: number | null;
  formatted_discrepancy?: string | null;
  reconciliation_notes: string[];
}

export interface AttentionItem {
  item_id: string;
  title: string;
  category: string;
  amount?: number | null;
  formatted_amount: string;
  reason: string;
  confidence: number;
  evidence: string;
  action_or_question: string;
  related_component_id?: string | null;
  page_number?: number | null;
  provenance_text?: string | null;
}

export interface CostReviewOpportunity {
  opportunity_id: string;
  category: string;
  component: string;
  amount?: number | null;
  formatted_amount: string;
  potential_amount_to_review?: number | null;
  formatted_potential_amount: string;
  evidence: string;
  explanation: string;
  suggested_action: string;
  related_component_id?: string | null;
  linked_opportunity_ids: string[];
}

export interface WaysToReviewCostSummary {
  active_categories: string[];
  opportunities: CostReviewOpportunity[];
  disclaimer: string;
}

export interface SupportingDocComparison {
  comparison_type: string;
  title: string;
  current_charge_name: string;
  current_charge_amount?: number | null;
  supporting_document_text: string;
  finding_description: string;
  action_guidance: string;
}

export interface BeforeYouPayFinalSummary {
  summary_id: string;
  document_id: string;
  user_id: string;
  hero: DecisionHero;
  reconciliation: ReconciliationThreeTier;
  financial_summary: CanonicalFinancialSummaryItem[];
  attention_items: AttentionItem[];
  ways_to_review_cost: WaysToReviewCostSummary;
  supporting_document_context?: SupportingDocComparison[] | null;
  questions_to_ask: string[];
  suggested_message: string;
  checklist: BeforeYouPayChecklist;
  completeness: InformationCompleteness;
}

// ── Phase 7: Evidence-First Explainability ──

export type EvidenceType =
  | "DOCUMENT_TEXT"
  | "OCR_TEXT"
  | "EXTRACTED_VALUE"
  | "SEMANTIC_CLASSIFICATION"
  | "DETERMINISTIC_CALCULATION"
  | "SUPPORTING_DOCUMENT"
  | "CROSS_DOCUMENT_COMPARISON"
  | "AUTHORITATIVE_KNOWLEDGE";

export type ConfidenceLevel = "High" | "Medium" | "Low" | "Requires verification";

export interface EvidenceItem {
  evidence_id: string;
  evidence_type: EvidenceType;
  source_document_id: string;
  source_document_role: "primary" | "supporting";
  page_number?: number | null;
  ocr_line_id?: string | null;
  field_id?: string | null;
  component_id?: string | null;
  validation_id?: string | null;
  finding_id?: string | null;
  original_text?: string | null;
  interpreted_as?: string | null;
  extracted_value?: number | null;
  normalized_label?: string | null;
  semantic_category?: string | null;
  bounding_box?: {
    x: number;
    y: number;
    width: number;
    height: number;
    coordinate_unit: CoordinateUnit;
  } | null;
  confidence: number;
  confidence_level: ConfidenceLevel;
  uncertainty_reason?: string | null;
  calculation_inputs?: Record<string, unknown> | null;
  calculation_expected?: number | null;
  calculation_document_result?: number | null;
  calculation_delta?: number | null;
  calculation_status?: string | null;
  supporting_document_id?: string | null;
  supporting_text?: string | null;
  supporting_amount?: number | null;
  comparison_result?: string | null;
  okf_rule_id?: string | null;
  okf_rule_version?: string | null;
  okf_source_reference?: string | null;
}

export interface CalculationExplanation {
  calculation_id: string;
  check_code: string;
  title: string;
  inputs: Record<string, unknown>;
  expected_result?: number | null;
  document_result?: number | null;
  delta?: number | null;
  status: string;
  explanation: string;
  input_field_ids: string[];
}

export interface SupportingDocumentExplanation {
  explanation_id: string;
  finding_type: string;
  current_document_label: string;
  current_document_amount?: number | null;
  current_document_text?: string | null;
  supporting_document_label: string;
  supporting_document_amount?: number | null;
  supporting_document_text?: string | null;
  finding: string;
  uncertainty: string;
  action: string;
  primary_evidence: EvidenceItem[];
  supporting_evidence: EvidenceItem[];
}

export interface FindingExplanation {
  explanation_id: string;
  finding_id: string;
  finding_type: string;
  concise_explanation: string;
  what_we_know: string[];
  what_we_infer: string[];
  what_remains_uncertain: string[];
  action?: string | null;
  evidence: EvidenceItem[];
  calculation_explanation?: CalculationExplanation | null;
  supporting_document_explanation?: SupportingDocumentExplanation | null;
  confidence: number;
  confidence_level: ConfidenceLevel;
  uncertainty_reason?: string | null;
  why_flagged: string;
}

export interface QuestionProvenance {
  question_id: string;
  question: string;
  source_finding_type: string;
  source_finding_id?: string | null;
  source_evidence_ids: string[];
  confidence: number;
}

export interface SuggestedMessageItem {
  item_id: string;
  text: string;
  source_finding_type: string;
  source_finding_id?: string | null;
  source_question_id?: string | null;
  source_evidence_ids: string[];
}

export interface EvidenceFirstResult {
  evidence_result_id: string;
  result_id: string;
  evidence_items: EvidenceItem[];
  finding_explanations: FindingExplanation[];
  question_provenance: QuestionProvenance[];
  suggested_message_items: SuggestedMessageItem[];
}


