export interface ModalProps {
  open: boolean;
  onClose?: () => void;
  title?: string;
  subtitle?: string;
  children?: React.ReactNode;
  maxWidth?: number;
  showHeader?: boolean;
  style?: React.CSSProperties;
}
export declare function Modal(props: ModalProps): JSX.Element | null;
