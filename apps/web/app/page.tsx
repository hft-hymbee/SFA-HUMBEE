import { SplashScreen } from "@/src/features/identity/screens";
import { SpMobileFrame } from "@/src/features/shell/components";
import { RouteTransition } from "@/src/shared/navigation";

export default function HomePage() {
  return (
    <SpMobileFrame>
      <RouteTransition>
        <SplashScreen />
      </RouteTransition>
    </SpMobileFrame>
  );
}
