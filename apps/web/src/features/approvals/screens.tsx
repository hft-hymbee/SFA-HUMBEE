"use client";

import {
  Button,
  EmptyState,
  ErrorState,
  Icon,
  ListRow,
  SkeletonRow,
  StatusChip,
} from "humbee-design-system";
import type { ApprovalListItem, NotificationItem } from "@humbee/api-contract";
import { useRouter } from "next/navigation";
import type { ReactNode, Ref } from "react";
import { readSessionSync } from "@/src/shared/auth/session";
import { useConnectivity } from "@/src/shared/capabilities";
import { useInfiniteScrollTrigger } from "@/src/shared/state";
import { SpScreen } from "@/src/features/shell/components";
import {
  flattenApprovals,
  useMyRequests,
  useNotificationActions,
  useNotifications,
  useUnreadNotificationCount,
} from "./hooks";
import {
  notificationHref,
  requestChip,
  requestDisplaySubtitle,
  requestDisplayTitle,
  requestSubjectHref,
} from "./service";

const toneColor = {
  success: "var(--color-success)",
  info: "var(--color-info)",
  error: "var(--color-error)",
  primary: "var(--color-primary)",
  warning: "var(--color-warning)",
} as const;

const toneIcon = {
  success: "CheckCircle",
  info: "Edit",
  error: "Close",
  primary: "NotificationsOutlined",
  warning: "Warning",
} as const;

export type NotificationRow = {
  id: string;
  title: string;
  subtitle: string;
  time: string;
  href: string;
  icon?: string;
  color?: string;
  tone?: keyof typeof toneColor;
  unread?: boolean;
  onOpen?: () => void;
};

export function NotificationList({ notifications, listRef }: { notifications: NotificationRow[]; listRef?: Ref<HTMLDivElement> }) {
  const router = useRouter();
  return (
    <div className="sp-list" ref={listRef}>
      {notifications.map((notification) => (
        <div
          key={notification.id}
          style={notification.unread ? { borderLeft: "var(--space-xs) solid var(--color-accent)" } : undefined}
        >
          <ListRow
            leading={<Icon name={notification.icon ?? toneIcon[notification.tone ?? "primary"]} size={22} color={notification.color ?? toneColor[notification.tone ?? "primary"]} />}
            title={notification.title}
            subtitle={notification.subtitle}
            meta={notification.time}
            showChevron={Boolean(notification.href)}
            onClick={notification.href || notification.onOpen ? () => {
              notification.onOpen?.();
              if (notification.href) router.push(notification.href);
            } : undefined}
          />
        </div>
      ))}
    </div>
  );
}

function requestRows(requests: ApprovalListItem[], onNavigate: (href: string) => void, listRef?: Ref<HTMLDivElement>) {
  return (
    <div className="sp-list" ref={listRef}>
      {requests.map((request) => {
        const chip = requestChip(request.status);
        const href = requestSubjectHref(request);
        return (
          <ListRow
            key={request.id}
            title={requestDisplayTitle(request)}
            subtitle={requestDisplaySubtitle(request)}
            trailing={<StatusChip status={chip.status} label={chip.label} type="outlined" />}
            showChevron={Boolean(href)}
            onClick={href ? () => onNavigate(href) : undefined}
          />
        );
      })}
    </div>
  );
}

export function MyRequestsScreen() {
  const router = useRouter();
  const { isOnline } = useConnectivity();
  const requests = useMyRequests();
  const items = flattenApprovals(requests.data);
  const listRef = useInfiniteScrollTrigger<HTMLDivElement>({
    hasNextPage: requests.hasNextPage,
    isFetchingNextPage: requests.isFetchingNextPage,
    fetchNextPage: requests.fetchNextPage,
  });

  if (requests.isPending) {
    return <SpScreen title="My requests" back offline={!isOnline}><div className="sp-content">{[0, 1, 2, 3].map((item) => <SkeletonRow key={item} />)}</div></SpScreen>;
  }
  if (requests.isError && !items.length) {
    return <SpScreen title="My requests" back offline={!isOnline}><ErrorState title="Requests unavailable" message="Your request history could not be loaded." onRetry={() => { void requests.refetch(); }} /></SpScreen>;
  }
  if (!items.length) {
    return <SpScreen title="My requests" back offline={!isOnline}><EmptyState icon="RewardsOutlined" title="No requests yet" message="Beat plans, DP orders and leave you submit will appear here." actionLabel="Apply for leave" onAction={() => router.push("/sp/more/leave/apply")} /></SpScreen>;
  }

  return (
    <SpScreen title="My requests" back offline={!isOnline}>
      {requestRows(items, (href) => router.push(href), listRef)}
      {requests.hasNextPage ? (
        <div className="sp-content">
          <Button
            variant="outlined"
            color="primary"
            label={requests.isFetchingNextPage ? "Loading…" : "Load more"}
            disabled={requests.isFetchingNextPage}
            onClick={() => { void requests.fetchNextPage(); }}
            style={{ width: "100%" }}
          />
        </div>
      ) : null}
    </SpScreen>
  );
}

function notificationTone(kind: string): NotificationRow["tone"] {
  if (["approved", "auto_approved"].includes(kind)) return "success";
  if (kind === "edited") return "info";
  if (kind === "rejected") return "error";
  if (kind === "escalated") return "warning";
  return "primary";
}

function notificationTime(createdAt: string) {
  const date = new Date(createdAt);
  const now = new Date();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const dateKey = date.toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
  const todayKey = now.toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
  const yesterdayKey = yesterday.toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
  if (dateKey === todayKey) return date.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit", timeZone: "Asia/Kolkata" });
  if (dateKey === yesterdayKey) return "Yesterday";
  return date.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: date.getFullYear() === now.getFullYear() ? undefined : "numeric", timeZone: "Asia/Kolkata" });
}

function toNotificationRow(
  notification: NotificationItem,
  onOpen: () => void,
  resolveHref: (href: string) => string = (href) => href,
): NotificationRow {
  const role = readSessionSync()?.role ?? "sp";
  const href = notificationHref(notification, role) ?? "";
  return {
    id: notification.id,
    title: notification.title,
    subtitle: notification.subtitle ?? "",
    time: notificationTime(notification.created_at),
    href: href ? resolveHref(href) : "",
    tone: notificationTone(notification.kind),
    unread: notification.is_unread,
    onOpen,
  };
}

type NotificationsShellProps = {
  children: ReactNode;
  action?: ReactNode;
  offline: boolean;
};

export function NotificationsFeed({
  renderShell,
  resolveHref,
}: {
  renderShell: (props: NotificationsShellProps) => ReactNode;
  resolveHref?: (href: string) => string;
}) {
  const { isOnline } = useConnectivity();
  const notifications = useNotifications();
  const unread = useUnreadNotificationCount();
  const { markRead, markAllRead } = useNotificationActions();
  const items = notifications.data?.pages.flatMap((page) => page.items) ?? [];
  const unreadCount = unread.data?.count ?? notifications.data?.pages[0]?.unread_count ?? 0;
  const listRef = useInfiniteScrollTrigger<HTMLDivElement>({
    hasNextPage: notifications.hasNextPage,
    isFetchingNextPage: notifications.isFetchingNextPage,
    fetchNextPage: notifications.fetchNextPage,
  });
  const shell = (children: ReactNode, action?: ReactNode) => renderShell({ children, action, offline: !isOnline });

  if (notifications.isPending) {
    return shell(<div className="sp-content">{[0, 1, 2, 3].map((item) => <SkeletonRow key={item} />)}</div>);
  }
  if (notifications.isError && !items.length) {
    return shell(<ErrorState title="Notifications unavailable" message="The feed could not be loaded." onRetry={() => { void notifications.refetch(); }} />);
  }
  if (!items.length) {
    return shell(<EmptyState icon="NotificationsOutlined" title="Nothing new" message="Approvals, edits and rejections show up here." actionLabel="Refresh" onAction={() => { void notifications.refetch(); }} />);
  }

  return shell(
    <>
      <NotificationList
        listRef={listRef}
        notifications={items.map((notification) => toNotificationRow(
          notification,
          () => {
            if (notification.is_unread) markRead.mutate(notification.id);
          },
          resolveHref,
        ))}
      />
      {notifications.hasNextPage ? (
        <div className="sp-content">
          <Button
            variant="outlined"
            color="primary"
            label={notifications.isFetchingNextPage ? "Loading…" : "Load more"}
            disabled={notifications.isFetchingNextPage}
            onClick={() => { void notifications.fetchNextPage(); }}
            style={{ width: "100%" }}
          />
        </div>
      ) : null}
    </>,
    unreadCount > 0 ? (
      <button
        className="sp-text-link"
        type="button"
        disabled={markAllRead.isPending || !isOnline}
        onClick={() => markAllRead.mutate()}
      >
        Mark all read
      </button>
    ) : undefined,
  );
}

export function NotificationsScreen() {
  return (
    <NotificationsFeed
      renderShell={({ children, action, offline }) => (
        <SpScreen title="Notifications" back offline={offline} action={action}>
          {children}
        </SpScreen>
      )}
    />
  );
}
