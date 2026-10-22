export interface PaperElevationProps {
  children?: React.ReactNode;
  padding?: number;
  radius?: number;
  bordered?: boolean;
  elevation?: "none" | "card" | "menu";
  style?: React.CSSProperties;
}
export declare function PaperElevation(props: PaperElevationProps): JSX.Element;
