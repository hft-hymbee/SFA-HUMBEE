import type { CSSProperties, ReactNode } from "react";

export interface TabsProps {
  tabs: Array<{ label: ReactNode; value: string | number } | string>;
  value?: string | number;
  onChange?: (value: string | number) => void;
  variant?: "primary" | "secondary";
  type?: "boxed" | "standard";
  size?: "small" | "medium";
  style?: CSSProperties;
}
export declare function Tabs(props: TabsProps): JSX.Element;
