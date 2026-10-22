export interface TopAppBarProps {
  title: string;
  onBack?: () => void;
  onBell?: () => void;
  bellCount?: number;
  action?: React.ReactNode;
  variant?: "default" | "order-flow" | "insights";
  style?: React.CSSProperties;
}
export interface BottomNavTab { id: string; label: string; icon: string; activeIcon: string; }
export interface BottomNavProps {
  active?: string;
  tabs?: BottomNavTab[];
  onNav?: (id: string) => void;
  style?: React.CSSProperties;
}
export declare function TopAppBar(props: TopAppBarProps): JSX.Element;
export declare function BottomNav(props: BottomNavProps): JSX.Element;
export declare const SP_TABS: BottomNavTab[];
