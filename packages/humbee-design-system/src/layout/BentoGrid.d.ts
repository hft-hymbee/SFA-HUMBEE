export interface BentoGridProps {
  children?: React.ReactNode;
  gap?: number;
  column?: number;
  masonry?: boolean;
  style?: React.CSSProperties;
}
export interface BentoItemProps {
  children?: React.ReactNode;
  colSpan?: number;
  style?: React.CSSProperties;
}
export declare function BentoGrid(props: BentoGridProps): JSX.Element;
export declare function BentoItem(props: BentoItemProps): JSX.Element;
