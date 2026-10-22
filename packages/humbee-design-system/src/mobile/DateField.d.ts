export interface DateFieldProps {
  label?: string; value?: string; dateValue?: string; placeholder?: string;
  onClick?: () => void; onChange?: (value: string) => void;
  min?: string; max?: string; isDateEnabled?: (iso: string) => boolean;
  inline?: boolean; error?: boolean; disabled?: boolean;
  fullWidth?: boolean; compact?: boolean; style?: React.CSSProperties;
}
export declare function DateField(props: DateFieldProps): JSX.Element;
