export interface ToggleSwitchProps {
  checked?: boolean;
  onChange?: (e: { target: { checked: boolean } }) => void;
  label?: string;
  disabled?: boolean;
  size?: "small" | "medium" | "large";
  error?: boolean;
  style?: React.CSSProperties;
}
export declare function ToggleSwitch(props: ToggleSwitchProps): JSX.Element;
