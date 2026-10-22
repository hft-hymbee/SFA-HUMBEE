export interface SelectProps {
  label?: string;
  placeholder?: string;
  options: Array<{ value: string; label: string } | string>;
  value?: string;
  onChange?: (value: string) => void;
  searchable?: boolean;
  searchPlaceholder?: string;
  emptyLabel?: string;
  error?: boolean;
  helperText?: string;
  disabled?: boolean;
  width?: number;
  fullWidth?: boolean;
  style?: React.CSSProperties;
}
export declare function Select(props: SelectProps): JSX.Element;
