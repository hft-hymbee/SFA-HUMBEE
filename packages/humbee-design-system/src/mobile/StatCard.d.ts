export interface StatCardProps {
  icon?: string; iconColor?: string;
  label: string; value: React.ReactNode; sub?: string;
  delta?: string; deltaTone?: "up" | "down" | "flat";
  onClick?: () => void; style?: React.CSSProperties;
}
export declare function StatCard(props: StatCardProps): JSX.Element;
