export interface TextFieldProps {
  /** @startingPoint section="Forms" subtitle="Labelled text input" viewport="360x120" */
  label?: string;
  helperText?: string;
  placeholder?: string;
  value?: string;
  onChange?: (e: React.ChangeEvent) => void;
  variant?: "outlined" | "standard";
  multiline?: boolean;
  rows?: number;
  error?: boolean;
  disabled?: boolean;
  required?: boolean;
  startAdornment?: React.ReactNode;
  endAdornment?: React.ReactNode;
  fullWidth?: boolean;
  style?: React.CSSProperties;
  inputProps?: React.InputHTMLAttributes<HTMLInputElement | HTMLTextAreaElement>;
}
export declare function TextField(props: TextFieldProps): JSX.Element;
