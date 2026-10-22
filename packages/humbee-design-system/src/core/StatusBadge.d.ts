export interface StatusBadgeProps {
  label?: string;
  status?: string;
  /** Explicit hex; otherwise colour is derived from the label text. */
  color?: string;
  variant?: "soft" | "outlined" | "filled" | "text";
  size?: "small" | "medium" | "large";
  style?: React.CSSProperties;
}
export declare function StatusBadge(props: StatusBadgeProps): JSX.Element;
