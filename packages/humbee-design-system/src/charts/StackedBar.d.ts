export interface StackedBarPart {
  label: string;
  value: number;
  color: string;
  hasBorder?: boolean;
}
export interface StackedBarProps {
  parts: StackedBarPart[];
  height?: number;
  referenceValue?: number;
  referenceLabel?: string;
  style?: React.CSSProperties;
}
export declare function StackedBar(props: StackedBarProps): JSX.Element;
