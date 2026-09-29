"use client";

import React from "react";
import { ListOrdered } from "lucide-react";
import { formatCurrency } from "../lib/utils";
import { StatusBadge, FinancialValue } from "./ui";

export interface ItemRow {
  description: string;
  amount: number | string;
  unitPrice?: number | string | null;
  quantity?: number | string | null;
  mrp?: number | string | null;
  discount?: number | string | null;
  linePointer?: string;
  status?: "PASS" | "REQUIRES_VERIFICATION";
}

interface LineItemsTableProps {
  items: ItemRow[];
  currency?: string | null;
}

export const LineItemsTable: React.FC<LineItemsTableProps> = ({ items, currency }) => {
  return (
    <div className="surface-card rounded-2xl p-5 sm:p-6 shadow-card mb-6 border border-white/10">
      <div className="flex items-center justify-between gap-3 mb-4 pb-3 border-b border-white/10">
        <div className="flex items-center gap-2">
          <ListOrdered className="w-5 h-5 text-brand-400" />
          <h3 className="font-bold text-sm sm:text-base text-white">Itemized Financial Lines</h3>
        </div>
        <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-semibold bg-white/10 text-slate-300">
          {items.length} items
        </span>
      </div>

      {items.length === 0 ? (
        <div className="text-center py-6 text-xs text-slate-400">
          No explicit itemized line extensions found in document.
        </div>
      ) : (
        <>
          {/* Mobile Stacked Cards (< md) */}
          <div className="md:hidden divide-y divide-white/5 font-mono">
            {items.map((item, idx) => (
              <div key={idx} className="py-3 space-y-1.5">
                <div className="flex items-start justify-between gap-2">
                  <div className="font-sans font-medium text-slate-100 text-xs">
                    {item.description}
                  </div>
                  <div className="font-bold text-sm text-white shrink-0">
                    {formatCurrency(item.amount, currency)}
                  </div>
                </div>

                <div className="flex items-center justify-between text-[11px] text-slate-400 pt-0.5">
                  <div className="flex items-center gap-2">
                    {item.quantity && Number(item.quantity) > 1 && (
                      <span>Qty: {String(item.quantity)}</span>
                    )}
                    {item.unitPrice && (
                      <span>@ {formatCurrency(item.unitPrice, currency)}</span>
                    )}
                    {item.discount && Number(item.discount) > 0 && (
                      <span className="text-emerald-400">
                        Off: −{formatCurrency(item.discount, currency)}
                      </span>
                    )}
                  </div>

                  {item.status && (
                    <span
                      className={`text-[9px] font-bold px-1.5 py-0.2 rounded uppercase ${
                        item.status === "PASS"
                          ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                          : "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                      }`}
                    >
                      {item.status === "PASS" ? "Verified" : "Check"}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Desktop Table (>= md) */}
          <div className="hidden md:block overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-white/10 text-slate-400 uppercase tracking-wider font-semibold text-[11px]">
                  <th className="pb-2.5 font-semibold">Item Description</th>
                  <th className="pb-2.5 font-semibold text-right">Rate / MRP</th>
                  <th className="pb-2.5 font-semibold text-right">Discount</th>
                  <th className="pb-2.5 font-semibold text-right">Final Amount</th>
                  <th className="pb-2.5 font-semibold text-right">Status</th>
                  <th className="pb-2.5 font-semibold text-right">Provenance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 font-mono">
                {items.map((item, idx) => (
                  <tr key={idx} className="hover:bg-white/2 transition">
                    <td className="py-2.5 pr-4 font-sans text-slate-200">
                      <div className="font-medium text-slate-100">{item.description}</div>
                      {item.quantity && Number(item.quantity) > 1 && (
                        <span className="text-[11px] text-slate-400">Qty: {String(item.quantity)}</span>
                      )}
                    </td>
                    <td className="py-2.5 text-right text-slate-300">
                      {item.unitPrice ? (
                        <div>
                          <span>{formatCurrency(item.unitPrice, currency)}</span>
                          {item.mrp && Number(item.mrp) > Number(item.unitPrice) && (
                            <div className="text-[10px] text-slate-500 line-through">
                              MRP {formatCurrency(item.mrp, currency)}
                            </div>
                          )}
                        </div>
                      ) : item.mrp ? (
                        formatCurrency(item.mrp, currency)
                      ) : (
                        "-"
                      )}
                    </td>
                    <td className="py-2.5 text-right text-emerald-400">
                      {item.discount && Number(item.discount) > 0
                        ? `-${formatCurrency(item.discount, currency)}`
                        : "-"}
                    </td>
                    <td className="py-2.5 text-right font-bold text-white">
                      <FinancialValue amount={item.amount} currency={currency} variant="item" />
                    </td>
                    <td className="py-2.5 text-right">
                      {item.status === "PASS" && (
                        <StatusBadge status="PASS" label="PASS" />
                      )}
                      {item.status === "REQUIRES_VERIFICATION" && (
                        <StatusBadge status="REQUIRES_VERIFICATION" label="CHECK" />
                      )}
                      {!item.status && <span className="text-slate-500">—</span>}
                    </td>
                    <td className="py-2.5 text-right text-slate-500">
                      <span className="px-2 py-0.5 rounded bg-white/5 font-mono text-[10px]">
                        {item.linePointer || `line-${idx + 1}`}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
};
