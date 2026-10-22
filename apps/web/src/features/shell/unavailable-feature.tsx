"use client";

import { Button, IconSurface } from "humbee-design-system";
import { useRouter } from "next/navigation";
import { SpCard, SpInlineAlert, SpScreen } from "./components";

export function SpUnavailableFeature({
  title,
  message,
  recoveryHref = "/sp/more",
  recoveryLabel = "Back to More",
  secondaryHref,
  secondaryLabel,
}: {
  title: string;
  message: string;
  recoveryHref?: string;
  recoveryLabel?: string;
  secondaryHref?: string;
  secondaryLabel?: string;
}) {
  const router = useRouter();
  return (
    <SpScreen title={title} back>
      <div className="sp-unavailable-feature">
        <SpCard>
          <div className="sp-unavailable-feature__hero">
            <IconSurface name="Lock" size="metric" shape="soft-square" tone="primary" />
            <div>
              <p>Feature not released</p>
              <h2>{title} unavailable</h2>
              <span>{message}</span>
            </div>
          </div>
          <SpInlineAlert>
            We are showing this as unavailable instead of estimating numbers from incomplete APIs.
          </SpInlineAlert>
          <div className="sp-unavailable-feature__actions">
            <Button
              variant="filled"
              color="primary"
              label={recoveryLabel}
              onClick={() => router.push(recoveryHref)}
            />
            {secondaryHref && secondaryLabel ? (
              <Button
                variant="outlined"
                color="neutral"
                label={secondaryLabel}
                onClick={() => router.push(secondaryHref)}
              />
            ) : null}
          </div>
        </SpCard>
      </div>
    </SpScreen>
  );
}
