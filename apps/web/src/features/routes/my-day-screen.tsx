"use client";

import { DateField, ErrorState } from "humbee-design-system";
import { useState } from "react";
import { istBusinessDate } from "@/src/features/attendance/service";
import { SpScreen } from "@/src/features/shell/components";
import { RouteDayTimeline, RouteDayTimelineLoading } from "./day-timeline";
import { useRouteDay } from "./service";

function formatBusinessDate(iso: string) {
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone: "Asia/Kolkata",
  }).format(new Date(`${iso}T12:00:00+05:30`));
}

export function MyDayScreen() {
  const today = istBusinessDate();
  const [businessDate, setBusinessDate] = useState(today);
  const route = useRouteDay(businessDate);
  const retryRoute = () => { void route.refetch(); };

  return (
    <SpScreen title="My day" back>
      <div className="sp-content">
        <DateField
          label="Business date"
          value={formatBusinessDate(businessDate)}
          dateValue={businessDate}
          max={today}
          onChange={setBusinessDate}
        />
        {route.isPending ? (
          <RouteDayTimelineLoading />
        ) : route.isError ? (
          <ErrorState title="Day timeline unavailable" message="Your timeline could not be loaded." onRetry={retryRoute} />
        ) : !route.data ? (
          <ErrorState title="Day timeline unavailable" message="Your timeline could not be loaded." onRetry={retryRoute} />
        ) : (
          <RouteDayTimeline
            routeDay={route.data}
            locationQueryScope="my-day"
            mapLabelWithMarkers="Your check-ins"
            mapLabelWithoutMarkers="No check-in pins yet"
            punchInSubtitle="Duty started"
            punchOutSubtitle="Duty ended"
          />
        )}
      </div>
    </SpScreen>
  );
}
