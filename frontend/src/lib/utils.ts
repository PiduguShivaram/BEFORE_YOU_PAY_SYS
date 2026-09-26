import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function generateUUID(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function formatCurrency(
  amount: number | string | null | undefined,
  currency?: string | null
): string {
  if (amount === null || amount === undefined) return "—";
  const num = typeof amount === "string" ? parseFloat(amount) : amount;
  if (isNaN(num)) return "—";

  const curr = currency ? currency.toUpperCase().trim() : null;
  if (!curr || curr === "UNKNOWN" || curr === "NULL" || curr === "NONE") {
    return num.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  if (curr === "INR" || curr === "₹") {
    return `₹${num.toLocaleString("en-IN", {
      minimumFractionDigits: Number.isInteger(num) ? 0 : 2,
      maximumFractionDigits: 2,
    })}`;
  }

  if (curr === "USD" || curr === "$") {
    return `$${num.toLocaleString("en-US", {
      minimumFractionDigits: Number.isInteger(num) ? 0 : 2,
      maximumFractionDigits: 2,
    })}`;
  }

  if (curr === "EUR" || curr === "€") {
    return `€${num.toLocaleString("de-DE", {
      minimumFractionDigits: Number.isInteger(num) ? 0 : 2,
      maximumFractionDigits: 2,
    })}`;
  }

  if (curr === "GBP" || curr === "£") {
    return `£${num.toLocaleString("en-GB", {
      minimumFractionDigits: Number.isInteger(num) ? 0 : 2,
      maximumFractionDigits: 2,
    })}`;
  }

  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: curr,
    }).format(num);
  } catch {
    return `${curr} ${num.toFixed(2)}`;
  }
}
