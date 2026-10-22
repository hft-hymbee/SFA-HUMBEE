export interface ApprovalStep { label: string; detail?: string; time?: string; state: "done" | "edited" | "rejected" | "pending" | "current" | "future"; }
export interface ApprovalTimelineProps { steps: ApprovalStep[]; style?: React.CSSProperties; }
export declare function ApprovalTimeline(props: ApprovalTimelineProps): JSX.Element;
