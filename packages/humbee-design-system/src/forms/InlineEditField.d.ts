export interface InlineEditFieldProps {
  label?: string;
  value?: string;
  onSave?: (next: string) => void;
  style?: React.CSSProperties;
}
export declare function InlineEditField(props: InlineEditFieldProps): JSX.Element;
