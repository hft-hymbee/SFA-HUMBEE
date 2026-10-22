export interface IconProps {
  /** Registry glyph name, e.g. "Dashboard", "ShoppingCartOutlined", "CurrencyRupee". */
  name: string;
  /** Square px size. @default 24 */
  size?: number;
  /** Fill colour (any CSS colour). @default "currentColor" */
  color?: string;
  style?: React.CSSProperties;
}
export declare function Icon(props: IconProps): JSX.Element | null;
export type IconSurfaceTone = "primary" | "accent" | "success" | "warning" | "error" | "info" | "neutral";
export type IconSurfaceShape = "circle" | "rounded" | "soft-square";
export type IconSurfaceSize = "nav" | "sm" | "md" | "metric" | "action" | "lg" | "empty" | number;
export interface IconSurfaceProps extends Omit<IconProps, "size"> {
  tone?: IconSurfaceTone;
  shape?: IconSurfaceShape;
  size?: IconSurfaceSize;
  glyphSize?: number;
  iconStyle?: React.CSSProperties;
}
export declare function IconSurface(props: IconSurfaceProps): JSX.Element | null;
export declare const ICON_NAMES: string[];
