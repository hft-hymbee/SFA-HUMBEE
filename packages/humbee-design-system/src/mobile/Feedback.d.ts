export interface SkeletonProps { width?: number | string; height?: number; radius?: number; style?: React.CSSProperties; }
export interface EmptyStateProps { icon?: string; title: string; message?: string; actionLabel?: string; onAction?: () => void; style?: React.CSSProperties; }
export interface ErrorStateProps { title?: string; message?: string; onRetry?: () => void; retryLabel?: string; style?: React.CSSProperties; }
export interface OfflineBannerProps { message?: string; onRetry?: () => void; style?: React.CSSProperties; }
export interface LockBannerProps { title?: string; message?: string; actionLabel?: string; onAction?: () => void; style?: React.CSSProperties; }
export declare function Skeleton(props: SkeletonProps): JSX.Element;
export declare function SkeletonRow(props: { style?: React.CSSProperties }): JSX.Element;
export declare function EmptyState(props: EmptyStateProps): JSX.Element;
export declare function ErrorState(props: ErrorStateProps): JSX.Element;
export declare function OfflineBanner(props: OfflineBannerProps): JSX.Element;
export declare function LockBanner(props: LockBannerProps): JSX.Element;
