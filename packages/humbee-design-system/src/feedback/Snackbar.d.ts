export interface SnackbarProps {
  open?: boolean;
  onClose?: () => void;
  message: string;
  severity?: "success" | "error" | "warning";
  action?: { label: string; onClick?: () => void };
  style?: React.CSSProperties;
}
export declare function Snackbar(props: SnackbarProps): JSX.Element | null;
