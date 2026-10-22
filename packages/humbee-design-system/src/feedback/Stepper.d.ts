export interface StepDef { label: string; subLabel?: string; }
export interface StepperProps {
  steps: StepDef[];
  activeStep?: number;
  orientation?: "horizontal" | "vertical";
  size?: "small" | "medium" | "large";
  showSubLabels?: boolean;
  style?: React.CSSProperties;
}
export declare function Stepper(props: StepperProps): JSX.Element;
