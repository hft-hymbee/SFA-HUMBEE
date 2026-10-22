import type { ReactNode } from "react";
import { SpMobileFrame } from "@/src/features/shell/components";
import { RouteTransition } from "@/src/shared/navigation";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <SpMobileFrame>
      <RouteTransition>{children}</RouteTransition>
    </SpMobileFrame>
  );
}
