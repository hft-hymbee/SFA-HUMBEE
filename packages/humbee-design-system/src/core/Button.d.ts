export interface ButtonProps {
  /** @startingPoint section="Core" subtitle="Primary action button" viewport="360x120" */
  variant?: "filled" | "outlined" | "text";
  color?: "primary" | "secondary" | "error" | "success" | "neutral";
  label?: string;
  children?: React.ReactNode;
  size?: "small" | "medium";
  disabled?: boolean;
  loading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  onClick?: (e: React.MouseEvent) => void;
  style?: React.CSSProperties;
}
export declare function Button(props: ButtonProps): JSX.Element;
