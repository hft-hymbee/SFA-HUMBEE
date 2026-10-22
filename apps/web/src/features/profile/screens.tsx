"use client";

import { useQuery } from "@tanstack/react-query";
import { EmptyState, ErrorState } from "humbee-design-system";
import { useSyncExternalStore } from "react";
import {
  getServerSession,
  readSessionSync,
  subscribeToSession,
} from "@/src/shared/auth/session";
import { SpScreen } from "@/src/features/shell/components";
import { UserProfilePanel, UserProfilePanelSkeleton } from "./components";
import { getProfile } from "./service";

function roleLabel(role: string) {
  if (role === "admin") return "Admin";
  if (role === "manager") return "Manager";
  return "Sales Person";
}

export function ProfileScreen() {
  const session = useSyncExternalStore(subscribeToSession, readSessionSync, getServerSession);
  const profile = useQuery({
    queryKey: ["profile", { actorId: session?.employeeId ?? "" }],
    queryFn: ({ signal }) => getProfile(signal),
    enabled: Boolean(session?.employeeId),
  });

  if (profile.isPending) {
    return (
      <SpScreen title="My profile" back>
        <UserProfilePanelSkeleton />
      </SpScreen>
    );
  }
  if (profile.isError) {
    return (
      <SpScreen title="My profile" back>
        <ErrorState
          title="Profile unavailable"
          message="Your profile could not be loaded."
          onRetry={() => { void profile.refetch(); }}
        />
      </SpScreen>
    );
  }
  if (!profile.data) {
    return (
      <SpScreen title="My profile" back>
        <EmptyState title="Profile unavailable" message="No profile was returned for this account." />
      </SpScreen>
    );
  }

  const value = profile.data;
  return (
    <SpScreen title="My profile" back>
      <UserProfilePanel
        profile={{
          name: value.name,
          initials: value.initials,
          employeeCode: value.employeeCode,
          roleLabel: roleLabel(value.role),
          sections: [
            {
              label: "Account",
              details: [
                { icon: "Call", label: "Login number", value: value.phone },
              ],
            },
          ],
        }}
      />
    </SpScreen>
  );
}
