export interface MenuItemDef {
  label: string;
  value?: string;
  icon?: React.ReactNode;
  onClick?: () => void;
}
export interface MenuProps {
  items: MenuItemDef[];
  selectedValue?: string | null;
  onSelect?: (value: string) => void;
  width?: number;
  style?: React.CSSProperties;
}
export declare function Menu(props: MenuProps): JSX.Element;
