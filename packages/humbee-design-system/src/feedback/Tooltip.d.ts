export interface TooltipProps {
  children: React.ReactElement;
  title: React.ReactNode;
  variant?: "neutral" | "main";
  size?: "small" | "medium" | "large";
  placement?: "top" | "bottom" | "left" | "right";
  style?: React.CSSProperties;
}
export declare function Tooltip(props: TooltipProps): JSX.Element;
