export interface QuantityHandlerProps {
  value?: number | string;
  onIncrease?: () => void;
  onDecrease?: () => void;
  onChange?: (e: React.ChangeEvent) => void;
  variant?: "small" | "medium";
  disabled?: boolean;
  min?: number;
  increaseDisabled?: boolean;
  style?: React.CSSProperties;
}
export declare function QuantityHandler(props: QuantityHandlerProps): JSX.Element;
