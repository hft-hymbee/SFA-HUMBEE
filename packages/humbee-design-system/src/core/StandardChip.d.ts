export interface StandardChipProps {
  label: string;
  selected?: boolean;
  defaultSelected?: boolean;
  showDelete?: boolean;
  size?: "small" | "medium";
  onChange?: (selected: boolean) => void;
  capitalise?: boolean;
  style?: React.CSSProperties;
}
export declare function StandardChip(props: StandardChipProps): JSX.Element;
