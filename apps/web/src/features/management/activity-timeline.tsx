"use client";

import { Icon } from "humbee-design-system";
import { useEffect, useState, type CSSProperties } from "react";
import styles from "./management.module.css";

export interface TeamDayActivity {
  id: string;
  occurredAt: string | null;
  sequence: number;
  title: string;
  subtitle: string;
  chipLabel: string;
  details: string[];
}

interface ActivityVisual {
  icon: string;
  background: string;
}

const ROW_REVEAL_MS = 130;
const ROW_REVEAL_START_MS = 60;

function istDayKey(date = new Date()) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).format(date);
}

function timestampMs(value: string | null | undefined) {
  if (!value) return null;
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? null : parsed;
}

function formatTimelineTime(value: string | null | undefined) {
  if (!value) return null;
  const date = new Date(value);
  const dayKey = istDayKey(date);
  const time = new Intl.DateTimeFormat("en-GB", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    timeZone: "Asia/Kolkata",
  }).format(date);
  const dateLabel = dayKey === istDayKey()
    ? "Today"
    : new Intl.DateTimeFormat("en-GB", {
      day: "numeric",
      month: "short",
      timeZone: "Asia/Kolkata",
    }).format(date);
  return `${dateLabel} ${time}`;
}

function activityVisual(activity: TeamDayActivity): ActivityVisual {
  if (activity.id === "punch-in") {
    return { icon: "PersonRounded", background: "var(--color-success)" };
  }
  if (activity.id === "punch-out") {
    return { icon: "LogoutOutlined", background: "var(--color-text-secondary)" };
  }
  const telephonic = activity.subtitle.toLowerCase().includes("telephonic");
  switch (activity.chipLabel) {
    case "Order placed":
      return { icon: "ShoppingCartOutlined", background: "var(--color-info)" };
    case "No order":
      return { icon: telephonic ? "Call" : "LocationPin", background: "var(--color-info)" };
    case "Completed":
      return { icon: "CheckCircle", background: "var(--color-success)" };
    case "In progress":
      return { icon: telephonic ? "Call" : "GpsFixed", background: "var(--color-primary)" };
    case "Missed":
      return { icon: "Close", background: "var(--color-error)" };
    default:
      return {
        icon: "Schedule",
        background: "color-mix(in srgb, var(--color-info) 58%, var(--color-primary))",
      };
  }
}

function titleLeadingIcon(activity: TeamDayActivity) {
  if (activity.id === "punch-in" || activity.id === "punch-out") return null;
  if (activity.chipLabel === "Order placed") return "ShoppingCartOutlined";
  if (activity.subtitle.toLowerCase().includes("telephonic")) return "Call";
  return "LocationPin";
}

function activityHasDetails(activity: TeamDayActivity) {
  return Boolean(activity.subtitle || activity.details.length);
}

function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function compareTeamDayActivities(a: TeamDayActivity, b: TeamDayActivity) {
  const aAt = timestampMs(a.occurredAt);
  const bAt = timestampMs(b.occurredAt);
  if (aAt === null && bAt === null) return a.sequence - b.sequence;
  if (aAt === null) return 1;
  if (bAt === null) return -1;
  if (aAt !== bAt) return aAt - bAt;
  return a.sequence - b.sequence;
}

function ActivityTimelineSkeletonRow({ index, last }: { index: number; last: boolean }) {
  return (
    <div
      className={styles.activityTimelineSkeletonStep}
      style={{ "--activity-step-delay": `${index * ROW_REVEAL_MS}ms` } as CSSProperties}
    >
      <div className={styles.activityTimelineRail}>
        <span className={styles.activityTimelineSkeletonDot} aria-hidden="true" />
        {!last ? <span className={styles.activityTimelineSkeletonLine} aria-hidden="true" /> : null}
      </div>
      <div className={styles.activityTimelineSkeletonBody}>
        <span className={styles.activityTimelineSkeletonTime} aria-hidden="true" />
        <span className={styles.activityTimelineSkeletonTitle} aria-hidden="true" />
        <span className={styles.activityTimelineSkeletonMeta} aria-hidden="true" />
      </div>
    </div>
  );
}

export function CoverageActivityTimelineSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className={styles.activityTimeline} aria-busy="true" aria-label="Loading activity timeline">
      {Array.from({ length: rows }, (_, index) => (
        <ActivityTimelineSkeletonRow key={index} index={index} last={index === rows - 1} />
      ))}
    </div>
  );
}

function ActivityTimelineStep({
  activity,
  index,
  last,
}: {
  activity: TeamDayActivity;
  index: number;
  last: boolean;
}) {
  const [open, setOpen] = useState(false);
  const visual = activityVisual(activity);
  const leadingIcon = titleLeadingIcon(activity);
  const time = formatTimelineTime(activity.occurredAt);
  const expandable = activityHasDetails(activity);

  return (
    <div className={styles.activityTimelineStep}>
      <div className={styles.activityTimelineRail}>
        <span className={styles.activityTimelineDot} style={{ background: visual.background }}>
          <Icon name={visual.icon} size={16} color="var(--color-text-inverse)" />
        </span>
        {!last ? <span className={styles.activityTimelineLine} aria-hidden="true" /> : null}
      </div>
      <div
        className={styles.activityTimelineBody}
        style={{ "--activity-content-delay": `${Math.min(index, 2) * 40}ms` } as CSSProperties}
      >
        {expandable ? (
          <button
            type="button"
            className={styles.activityTimelineToggle}
            aria-expanded={open}
            onClick={() => setOpen((current) => !current)}
          >
            {time ? <span className={styles.activityTimelineTime}>{time}</span> : null}
            <span className={styles.activityTimelineTitleRow}>
              <span className={styles.activityTimelineTitle}>
                {leadingIcon ? (
                  <span className={styles.activityTimelineTitleIcon}>
                    <Icon
                      name={leadingIcon}
                      size={14}
                      color="var(--color-text-secondary)"
                    />
                  </span>
                ) : null}
                <span>{activity.title}</span>
              </span>
              <span className={styles.activityTimelineChevron} data-open={open ? "true" : "false"}>
                <Icon name="KeyboardArrowRight" size={20} color="var(--color-text-secondary)" />
              </span>
            </span>
            {activity.chipLabel ? <span className={styles.activityTimelineMeta}>{activity.chipLabel}</span> : null}
          </button>
        ) : (
          <div className={styles.activityTimelineSummary}>
            {time ? <div className={styles.activityTimelineTime}>{time}</div> : null}
            <div className={styles.activityTimelineTitle}>
              {leadingIcon ? (
                <span className={styles.activityTimelineTitleIcon}>
                  <Icon
                    name={leadingIcon}
                    size={14}
                    color="var(--color-text-secondary)"
                  />
                </span>
              ) : null}
              <span>{activity.title}</span>
            </div>
            {activity.chipLabel ? <div className={styles.activityTimelineMeta}>{activity.chipLabel}</div> : null}
          </div>
        )}
        {expandable ? (
          <div className={styles.activityTimelinePanel} data-open={open ? "true" : "false"}>
            <div className={styles.activityTimelinePanelInner}>
              {activity.subtitle ? <div className={styles.activityTimelineDescription}>{activity.subtitle}</div> : null}
              {activity.details.map((detail) => (
                <div key={detail} className={styles.activityTimelineDetail}>{detail}</div>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function CoverageActivityTimeline({ activities }: { activities: TeamDayActivity[] }) {
  const [visibleCount, setVisibleCount] = useState(0);
  const activityKey = activities.map((activity) => activity.id).join("|");
  const [revealedKey, setRevealedKey] = useState(activityKey);
  if (revealedKey !== activityKey) {
    setRevealedKey(activityKey);
    setVisibleCount(0);
  }
  const shownCount = prefersReducedMotion() ? activities.length : visibleCount;

  useEffect(() => {
    if (!activities.length || prefersReducedMotion()) return;

    let index = 0;
    let cancelled = false;
    let timer: number | undefined;

    const revealNext = () => {
      if (cancelled) return;
      index += 1;
      setVisibleCount(index);
      if (index < activities.length) {
        timer = window.setTimeout(revealNext, ROW_REVEAL_MS);
      }
    };

    timer = window.setTimeout(revealNext, ROW_REVEAL_START_MS);

    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [activityKey, activities.length]);

  return (
    <div className={styles.activityTimeline}>
      {activities.slice(0, shownCount).map((activity, index) => (
        <ActivityTimelineStep
          key={activity.id}
          activity={activity}
          index={index}
          last={index === activities.length - 1}
        />
      ))}
    </div>
  );
}
