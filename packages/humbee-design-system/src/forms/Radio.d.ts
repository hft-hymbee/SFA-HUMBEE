export interface RadioProps {
  label?: string;
  checked?: boolean;
  disabled?: boolean;
  error?: boolean;
  size?: "small" | "medium" | "large";
  value?: string;
  name?: string;
  onChange?: (e: React.ChangeEvent) => void;
  style?: React.CSSProperties;
}
export interface RadioGroupProps {
  label?: string;
  options: Array<{ value: string; label: string; disabled?: boolean } | string>;
  value?: string;
  onChange?: (value: string) => void;
  name?: string;
  row?: boolean;
  disabled?: boolean;
  size?: "small" | "medium" | "large";
  helperText?: string;
  error?: boolean;
  style?: React.CSSProperties;
}
export declare function Radio(props: RadioProps): JSX.Element;
export declare function RadioGroup(props: RadioGroupProps): JSX.Element;
