export interface FABProps { iconName?: string; label?: string; onClick?: () => void; color?: string; style?: React.CSSProperties; }
export interface BottomSheetProps { open: boolean; onClose?: () => void; title?: string; children?: React.ReactNode; style?: React.CSSProperties; }
export declare function FAB(props: FABProps): JSX.Element;
export declare function BottomSheet(props: BottomSheetProps): JSX.Element | null;
