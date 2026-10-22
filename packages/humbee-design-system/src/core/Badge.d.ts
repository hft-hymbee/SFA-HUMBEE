export interface BadgeProps {
  badgeText: string;
  badgeType?: "card" | "list" | "default";
  badgePosition?: { top?: number | string; right?: number | string };
  badgeSize?: "small" | "large";
  style?: React.CSSProperties;
}
export declare function Badge(props: BadgeProps): JSX.Element | null;
