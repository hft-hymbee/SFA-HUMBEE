"use client";

import { Icon, ListRow } from "humbee-design-system";
import { SpCard, SpSectionLabel, SpStatusRow } from "@/src/features/shell/components";

export function formatOrderMoney(paise: number) {
  return `₹ ${(paise / 100).toLocaleString("en-IN", {
    maximumFractionDigits: 2,
  })}`;
}

export type OrderFormType = "STRAIGHT" | "BEND";

export function formatFormTypeLabel(formType: OrderFormType | null | undefined) {
  if (formType === "STRAIGHT") return "Straight";
  if (formType === "BEND") return "Bend";
  return null;
}

export type OrderSummaryLine = {
  key: string;
  productName: string;
  approvedQty: number;
  requestedQty?: number;
  unitLabel?: string | null;
  formType?: OrderFormType | null;
  lineTotalPaise?: number;
};

export function mapOrderDetailSummaryLine(line: {
  product_id: string;
  product_name: string;
  approved_qty?: number | null;
  requested_qty: number;
  pack_size?: string | null;
  form_type?: OrderFormType | null;
  approved_line_net_paise?: number | null;
  line_net_paise: number;
  approved_line_gst_amount_paise?: number | null;
  line_gst_amount_paise: number;
  scheme_line_discount_paise: number;
  product_line_discount_paise: number;
}): OrderSummaryLine {
  const approvedQty = line.approved_qty ?? line.requested_qty;
  const lineNetPaise = line.approved_line_net_paise ?? line.line_net_paise;
  const lineGstAmountPaise = line.approved_line_gst_amount_paise ?? line.line_gst_amount_paise;
  const lineDiscountPaise = line.scheme_line_discount_paise + line.product_line_discount_paise;
  return {
    key: line.product_id,
    productName: line.product_name,
    approvedQty,
    requestedQty: line.requested_qty,
    unitLabel: line.pack_size,
    formType: line.form_type,
    lineTotalPaise: lineNetPaise - lineDiscountPaise + lineGstAmountPaise,
  };
}

export function mapDpOrderSummaryLine(line: {
  key: string;
  productName: string;
  qty: number;
  unitLabel?: string | null;
  formType?: OrderFormType | null;
  lineTotalPaise: number;
}): OrderSummaryLine {
  return {
    key: line.key,
    productName: line.productName,
    approvedQty: line.qty,
    unitLabel: line.unitLabel,
    formType: line.formType,
    lineTotalPaise: line.lineTotalPaise,
  };
}

export type OrderPriceSummaryProps = {
  itemCount: number;
  subtotalPaise: number;
  productDiscountPaise?: number;
  schemeDiscountPaise: number;
  gstPaise: number;
  gstRateBp?: number | null;
  totalPaise: number;
  pricedAsOf?: string | null;
};

function hasSchemeDiscount(schemeDiscountPaise: number | null | undefined) {
  return (schemeDiscountPaise ?? 0) > 0;
}

function hasProductDiscount(productDiscountPaise: number | null | undefined) {
  return (productDiscountPaise ?? 0) > 0;
}

export function sharedGstRateBp(rates: Array<number | null | undefined>) {
  const unique = [
    ...new Set(rates.filter((rate): rate is number => rate != null && rate > 0)),
  ];
  return unique.length === 1 ? unique[0] : null;
}

export function formatGstRateLabel(gstRateBp?: number | null) {
  if (gstRateBp == null || gstRateBp <= 0) return "GST";
  const percent = gstRateBp / 100;
  const display = Number.isInteger(percent)
    ? String(percent)
    : percent.toFixed(2).replace(/\.?0+$/, "");
  return `GST (${display}%)`;
}

export function SchemeAppliedBanner({
  label,
  discountPaise,
}: {
  label?: string | null;
  discountPaise?: number | null;
}) {
  if (!label || !hasSchemeDiscount(discountPaise)) return null;
  return (
    <div className="sp-scheme-applied">
      <Icon name="RewardsOutlined" size={20} color="var(--color-success)" />
      <span>{label}</span>
    </div>
  );
}

function lineQuantitySubtitleParts(line: OrderSummaryLine) {
  const approvedQty = line.approvedQty;
  const requestedQty = line.requestedQty ?? approvedQty;
  if (requestedQty !== approvedQty) {
    return [`Requested: ${requestedQty}`, `Approved: ${approvedQty}`];
  }
  return [`Quantity: ${approvedQty}`];
}

function lineSummarySubtitle(line: OrderSummaryLine) {
  const formTypeLabel = formatFormTypeLabel(line.formType);
  return [
    ...lineQuantitySubtitleParts(line),
    line.unitLabel ? `Unit: ${line.unitLabel}` : "",
    formTypeLabel ? `Form: ${formTypeLabel}` : "",
  ].filter(Boolean).join(" · ");
}

export function OrderPriceSummaryCard({
  subtotalPaise,
  productDiscountPaise,
  schemeDiscountPaise,
  gstPaise,
  gstRateBp,
  totalPaise,
  pricedAsOf,
}: OrderPriceSummaryProps) {
  const summaryColumns = "minmax(0, 1fr) auto";
  const taxableBasePaise = totalPaise - gstPaise;
  return (
    <SpCard style={{ borderRadius: "var(--radius-lg)" }}>
      <div className="sp-stack sp-order-price-summary">
        <div className="sp-stack sp-order-price-summary__rows">
          <SpStatusRow
            label="Subtotal (excl. GST)"
            value={formatOrderMoney(taxableBasePaise)}
            valueAlign="right"
            columns={summaryColumns}
          />
          {hasProductDiscount(productDiscountPaise) ? (
            <SpStatusRow
              label="Discount"
              value={`− ${formatOrderMoney(productDiscountPaise!)}`}
              tone="var(--color-success)"
              valueAlign="right"
              columns={summaryColumns}
            />
          ) : null}
          {hasSchemeDiscount(schemeDiscountPaise) ? (
            <SpStatusRow
              label="Scheme discount"
              value={`− ${formatOrderMoney(schemeDiscountPaise)}`}
              tone="var(--color-success)"
              valueAlign="right"
              columns={summaryColumns}
            />
          ) : null}
          <SpStatusRow
            label={formatGstRateLabel(gstRateBp)}
            value={`${formatOrderMoney(gstPaise)}`}
            valueAlign="right"
            columns={summaryColumns}
          />
        </div>
        <div className="sp-order-price-summary__total">
          <span className="sp-order-price-summary__total-label">Total (incl. GST)</span>
          <strong className="sp-order-price-summary__total-value">{formatOrderMoney(totalPaise)}</strong>
        </div>
        {pricedAsOf ? (
          <p className="sp-meta sp-order-price-summary__as-of">
            Priced as of {new Date(pricedAsOf).toLocaleString("en-IN")}
          </p>
        ) : null}
      </div>
    </SpCard>
  );
}

export function OrderSummarySections({
  pricedLines,
  quantityOnlyLines,
  priceSummary,
  schemeLabel,
}: {
  pricedLines: OrderSummaryLine[];
  quantityOnlyLines: OrderSummaryLine[];
  priceSummary: OrderPriceSummaryProps | null;
  schemeLabel?: string | null;
}) {
  return (
    <>
      {pricedLines.length ? (
        <>
          <SpSectionLabel>
            {quantityOnlyLines.length
              ? `Priced items · ${pricedLines.length}`
              : `Order summary · ${pricedLines.length} items`}
          </SpSectionLabel>
          <SpCard padded={false}>
            <div className="sp-list">
              {pricedLines.map((line) => (
                <ListRow
                  key={line.key}
                  title={line.productName}
                  subtitle={lineSummarySubtitle(line)}
                  meta={line.lineTotalPaise != null ? formatOrderMoney(line.lineTotalPaise) : undefined}
                />
              ))}
            </div>
          </SpCard>
        </>
      ) : null}
      {quantityOnlyLines.length ? (
        <>
          <SpSectionLabel>
            {pricedLines.length
              ? `Quantity-only items · ${quantityOnlyLines.length}`
              : `Order summary · ${quantityOnlyLines.length} items`}
          </SpSectionLabel>
          <SpCard padded={false}>
            <div className="sp-list">
              {quantityOnlyLines.map((line) => (
                <ListRow
                  key={line.key}
                  title={line.productName}
                  subtitle={lineSummarySubtitle(line)}
                />
              ))}
            </div>
          </SpCard>
        </>
      ) : null}
      <SchemeAppliedBanner
        label={schemeLabel}
        discountPaise={priceSummary?.schemeDiscountPaise}
      />
      {pricedLines.length && priceSummary ? (
        <OrderPriceSummaryCard {...priceSummary} />
      ) : null}
    </>
  );
}
