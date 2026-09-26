with open("frontend/src/lib/types.ts", encoding="utf-8") as f:
    types_code = f.read()

new_state_types = """export type CoordinateUnit = "normalized_percentage" | "pixels";

export type AnalysisState =
  | "FINANCIAL_DATA_FOUND"
  | "NO_FINANCIAL_DATA_AFTER_RELIABLE_OCR"
  | "OCR_UNRELIABLE"
  | "DOCUMENT_UNREADABLE"
  | "EXTRACTION_INCONCLUSIVE";

export type OCRQualityStatus = "GOOD" | "DEGRADED" | "UNRELIABLE";

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
  confidence: number;
  is_unreliable?: boolean;
}"""

assert 'export type CoordinateUnit = "normalized_percentage" | "pixels";' in types_code
types_code = types_code.replace(
    'export type CoordinateUnit = "normalized_percentage" | "pixels";', new_state_types
)

target_res_summary = """export interface ResultSummary {
  headline: string;
  overall_status: DecisionStatus;
  total_flags: number;
  requires_human_verification: boolean;
}"""

replacement_res_summary = """export interface ResultSummary {
  headline: string;
  overall_status: DecisionStatus;
  total_flags: number;
  requires_human_verification: boolean;
  analysis_state?: AnalysisState;
  ocr_quality?: OCRQualityResult | null;
}"""

assert target_res_summary in types_code
types_code = types_code.replace(target_res_summary, replacement_res_summary)

target_final_res = """export interface FinalDecisionSupportResult {
  result_id: string;
  document_id: string;
  user_id: string;
  summary: ResultSummary;
  flags: DecisionFlag[];
  reasoning_claims: ReasoningClaim[];
  validation_checks: ValidationCheck[];
  document?: StructuredFinancialDocument | null;
  raw_ocr_lines?: string[];
  generated_at: string;
}"""

replacement_final_res = """export interface FinalDecisionSupportResult {
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
}"""

assert target_final_res in types_code
types_code = types_code.replace(target_final_res, replacement_final_res)

with open("frontend/src/lib/types.ts", "w", encoding="utf-8") as f:
    f.write(types_code)
print("Updated frontend/src/lib/types.ts successfully")
