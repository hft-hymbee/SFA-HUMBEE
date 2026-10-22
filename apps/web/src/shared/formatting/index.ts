const inrFormatter = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 2,
  minimumFractionDigits: 2,
});

export function formatPaiseToInr(paise: number): string {
  return inrFormatter.format(paise / 100);
}
