export interface MapPreviewProps { height?: number; pin?: boolean; label?: string; style?: React.CSSProperties; }
export interface LocationCaptureCardProps {
  status?: "locating" | "captured" | "error";
  address?: string; coords?: string; accuracy?: string; time?: string;
  preview?: React.ReactNode;
  style?: React.CSSProperties;
}
export declare function MapPreview(props: MapPreviewProps): JSX.Element;
export declare function LocationCaptureCard(props: LocationCaptureCardProps): JSX.Element;
