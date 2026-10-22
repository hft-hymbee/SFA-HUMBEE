"use client";

import { Button, Icon } from "humbee-design-system";
import { useRouter } from "next/navigation";
import { useState, useSyncExternalStore } from "react";
import { LogoutConfirmSheet } from "@/src/features/identity/screens";
import { SpCard, SpScreen, SpSectionLabel } from "@/src/features/shell/components";
import { AccountActionList, ProfileIdentity, type AccountAction } from "@/src/features/profile/components";
import {
  getServerSession,
  readSessionSync,
  subscribeToSession,
} from "@/src/shared/auth/session";

const groups: Array<{ label: string; items: AccountAction[] }> = [
  {
    label: "Account",
    items: [
      { icon: "ProfileOutlined", label: "My profile", href: "/sp/more/profile" },
      { icon: "NotificationsOutlined", label: "Notifications", href: "/sp/notifications" },
    ],
  },
  {
    label: "My work",
    items: [
      { icon: "Schedule", label: "My day", href: "/sp/my-day" },
      { icon: "GpsFixed", label: "Attendance", href: "/sp/more/attendance/history" },
      { icon: "Schedule", label: "Official work", href: "/sp/more/official-work" },
    ],
  },
  {
    label: "Outlets",
    items: [
      { icon: "InventoryOutlined", label: "Onboard outlet", href: "/sp/outlets/new" },
      { icon: "PersonRounded", label: "Capture lead", href: "/sp/leads/new" },
      { icon: "LocationMarker", label: "Missed visits", href: "/sp/visits/missed" },
    ],
  },
  {
    label: "Requests",
    items: [
      { icon: "Calendar", label: "Leave", href: "/sp/more/leave" },
      { icon: "RewardsOutlined", label: "My requests", href: "/sp/more/requests" },
    ],
  },
  {
    label: "Performance",
    items: [{ icon: "RewardsOutlined", label: "My targets", href: "/sp/more/targets" }],
  },
];

export function MoreScreen() {
  const router = useRouter();
  const session = useSyncExternalStore(subscribeToSession, readSessionSync, getServerSession);
  const [confirmLogout, setConfirmLogout] = useState(false);
  return (
    <SpScreen title="More" bell>
      <div className="sp-more-page">
        <div className="sp-content">
          <SpCard>
            <ProfileIdentity
              compact
              name={session?.displayName ?? "Employee"}
              subtitle={session ? `Sales Person · ${session.employeeId}` : "Sales Person"}
            />
          </SpCard>
          {groups.map((group) => (
            <section key={group.label}>
              <SpSectionLabel>{group.label}</SpSectionLabel>
              <AccountActionList actions={group.items} onNavigate={(href) => router.push(href)} />
            </section>
          ))}
        </div>
        <div className="sp-logout-bar">
          <Button
            variant="outlined"
            color="error"
            label="Log out"
            leftIcon={<Icon name="LogoutOutlined" size={20} color="currentColor" />}
            onClick={() => setConfirmLogout(true)}
            style={{ width: "100%" }}
          />
        </div>
      </div>
      {confirmLogout ? <LogoutConfirmSheet onClose={() => setConfirmLogout(false)} /> : null}
    </SpScreen>
  );
}
