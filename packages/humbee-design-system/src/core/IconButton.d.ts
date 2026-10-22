export interface IconButtonProps {
  iconName?: string;
  icon?: React.ReactNode;
  color?: "primary" | "secondary" | "error" | "success" | "info" | "warning" | "neutral";
  size?: number;
  disabled?: boolean;
  onClick?: (e: React.MouseEvent) => void;
  style?: React.CSSProperties;
}
export declare function IconButton(props: IconButtonProps): JSX.Element;
