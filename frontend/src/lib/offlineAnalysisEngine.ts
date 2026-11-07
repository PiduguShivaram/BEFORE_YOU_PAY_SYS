/**
 * Pure Deterministic Client-Side Financial Analysis Engine.
 * 
 * Runs 100% locally in the browser when offline.
 * Extracts amounts, line components, taxes, discounts, and total from raw OCR text,
 * then applies strict deterministic mathematical verification without any server round-trips.
 */

export interface OfflineComponent {
  name: string;
  amount: number;
  nature: "charge" | "deduction";
}

export interface OfflineAnalysisResult {
  id: string;
  timestamp: string;
  status: "COMPLETED_ON_DEVICE" | "ANALYSIS_UNAVAILABLE";
  status_label: string;
  ocr_text: string;
  detected_total: number | null;
  detected_subtotal: number | null;
  detected_tax: number | null;
  detected_discount: number | null;
  components: OfflineComponent[];
  math_status: "RECONCILED" | "DISCREPANCY" | "INCONCLUSIVE";
  discrepancy: number | null;
  currency: string;
  summary: string;
  is_on_device: true;
}

export function parseOfflineCurrencyAmount(text: string): number | null {
  // Strip currency symbols and commas, match positive decimals
  const match = text.match(/(?:₹|rs\.?|inr|\$)?\s*([0-9]{1,3}(?:,[0-9]{2,3})+|[0-9]+(?:\.[0-9]{1,2})?)/i);
  if (!match) return null;
  const clean = match[1].replace(/,/g, "");
  const num = parseFloat(clean);
  return isNaN(num) || num <= 0 ? null : num;
}

export function analyzeOfflineText(rawOcrText: string): OfflineAnalysisResult {
  const id = `offline-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const timestamp = new Date().toISOString();

  if (!rawOcrText || rawOcrText.trim().length < 5) {
    return {
      id,
      timestamp,
      status: "ANALYSIS_UNAVAILABLE",
      status_label: "Analysis unavailable",
      ocr_text: rawOcrText || "",
      detected_total: null,
      detected_subtotal: null,
      detected_tax: null,
      detected_discount: null,
      components: [],
      math_status: "INCONCLUSIVE",
      discrepancy: null,
      currency: "INR",
      summary: "No readable financial text detected in document.",
      is_on_device: true,
    };
  }

  const lines = rawOcrText.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
  let detected_total: number | null = null;
  let detected_subtotal: number | null = null;
  let detected_tax: number | null = null;
  let detected_discount: number | null = null;
  const components: OfflineComponent[] = [];

  const currency = /(?:\$|usd)/i.test(rawOcrText) ? "USD" : "INR";
  const currSym = currency === "USD" ? "$" : "₹";

  for (const line of lines) {
    const lineLower = line.toLowerCase();
    
    // Total detection
    if (/(?:total|grand\s*total|net\s*payable|amount\s*payable|on[- ]road\s*price)/i.test(lineLower) && !/subtotal/i.test(lineLower)) {
      const amt = parseOfflineCurrencyAmount(line);
      if (amt && (detected_total === null || amt > detected_total)) {
        detected_total = amt;
      }
      continue;
    }

    // Subtotal detection
    if (/subtotal|taxable|base\s*price|ex[- ]showroom/i.test(lineLower)) {
      const amt = parseOfflineCurrencyAmount(line);
      if (amt && detected_subtotal === null) {
        detected_subtotal = amt;
      }
      continue;
    }

    // Tax detection
    if (/tax|gst|cgst|sgst|vat/i.test(lineLower)) {
      const amt = parseOfflineCurrencyAmount(line);
      if (amt && detected_tax === null) {
        detected_tax = amt;
      }
      continue;
    }

    // Discount detection
    if (/discount|rebate|offer|concession/i.test(lineLower)) {
      const amt = parseOfflineCurrencyAmount(line);
      if (amt && detected_discount === null) {
        detected_discount = amt;
      }
      continue;
    }

    // Itemized components
    const amt = parseOfflineCurrencyAmount(line);
    if (amt && amt > 10) {
      // Clean label
      const name = line.replace(/(?:₹|rs\.?|inr|\$)?\s*[0-9,]+(?:\.[0-9]{1,2})?/gi, "").trim();
      if (name.length >= 2 && !/invoice|date|phone|gstin|pan|address|tax\s*invoice/i.test(name)) {
        components.push({
          name: name.slice(0, 40),
          amount: amt,
          nature: "charge",
        });
      }
    }
  }

  // Pure deterministic mathematical verification
  let math_status: "RECONCILED" | "DISCREPANCY" | "INCONCLUSIVE" = "INCONCLUSIVE";
  let discrepancy: number | null = null;
  let summary = "";

  if (detected_total !== null) {
    const baseSum = detected_subtotal !== null ? detected_subtotal : components.reduce((acc, c) => acc + c.amount, 0);
    const taxSum = detected_tax || 0;
    const discSum = detected_discount || 0;
    const calculated = Math.round((baseSum + taxSum - discSum) * 100) / 100;
    
    if (baseSum > 0) {
      discrepancy = Math.round(Math.abs(calculated - detected_total) * 100) / 100;
      if (discrepancy <= 0.05) {
        math_status = "RECONCILED";
        summary = `On-device verification confirmed: Stated total (${currSym}${detected_total.toLocaleString()}) reconciles with detected items.`;
      } else {
        math_status = "DISCREPANCY";
        summary = `On-device verification detected a ${currSym}${discrepancy.toLocaleString()} arithmetic discrepancy between constituent items and stated total.`;
      }
    } else {
      math_status = "INCONCLUSIVE";
      summary = `Stated total of ${currSym}${detected_total.toLocaleString()} detected on-device. Itemized component reconciliation inconclusive.`;
    }
  } else if (components.length > 0) {
    const compSum = components.reduce((acc, c) => acc + c.amount, 0);
    math_status = "INCONCLUSIVE";
    summary = `Identified ${components.length} itemized charge(s) totaling ${currSym}${compSum.toLocaleString()} on-device. Stated document total not detected.`;
  } else {
    math_status = "INCONCLUSIVE";
    summary = "On-device OCR complete. No verified financial totals detected.";
  }

  return {
    id,
    timestamp,
    status: "COMPLETED_ON_DEVICE",
    status_label: "Analysis completed on-device",
    ocr_text: rawOcrText,
    detected_total,
    detected_subtotal,
    detected_tax,
    detected_discount,
    components: components.slice(0, 8),
    math_status,
    discrepancy,
    currency,
    summary,
    is_on_device: true,
  };
}

