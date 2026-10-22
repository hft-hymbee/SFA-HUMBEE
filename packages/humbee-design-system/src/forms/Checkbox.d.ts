export interface CheckboxProps {
  label?: string;
  checked?: boolean;
  indeterminate?: boolean;
  disabled?: boolean;
  error?: boolean;
  size?: "small" | "medium" | "large";
  onChange?: (e: React.ChangeEvent) => void;
  labelPlacement?: "end" | "start";
  style?: React.CSSProperties;
}
export declare function Checkbox(props: CheckboxProps): JSX.Element;
