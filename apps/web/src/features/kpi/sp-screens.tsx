"use client";

import { Button } from "humbee-design-system";
import { useRouter } from "next/navigation";
import { SalespersonTargetsDashboard } from "@/src/features/kpi/home-dashboard";
import { SpScreen } from "@/src/features/shell/components";

export function SpTargetsKpiScreen() {
  const router = useRouter();
  return (
    <SpScreen title="My targets" back>
      <div className="sp-content">
        <SalespersonTargetsDashboard />
      </div>
      <div className="sp-sticky-footer">
        <Button
          variant="outlined"
          color="primary"
          label="Open orders"
          onClick={() => router.push("/sp/orders")}
          style={{ width: "100%" }}
        />
      </div>
    </SpScreen>
  );
}
