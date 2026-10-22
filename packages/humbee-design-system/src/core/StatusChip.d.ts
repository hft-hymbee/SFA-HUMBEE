export interface StatusChipProps {
  status?: "pending" | "not-verified" | "verified" | "approved" | "completed" | "success" | "partially-completed" | "cancelled" | "default";
  label?: string;
  type?: "outlined" | "filled" | "text";
  className?: string;
  style?: React.CSSProperties;
}
export declare function StatusChip(props: StatusChipProps): JSX.Element;
