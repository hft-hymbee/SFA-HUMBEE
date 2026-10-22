"use client";

import { Icon, IconSurface, ListRow, SkeletonRow } from "humbee-design-system";
import styles from "./profile.module.css";

export interface ProfileDetail {
  icon: string;
  label: string;
  value: string;
}

export interface ProfileSection {
  label: string;
  details: ProfileDetail[];
}

export interface UserProfile {
  name: string;
  employeeCode: string;
  roleLabel: string;
  initials?: string;
  sections: ProfileSection[];
}

export interface AccountAction {
  icon: string;
  label: string;
  href?: string;
  destructive?: boolean;
}

function initialsFor(name: string) {
  return name
    .split(" ")
    .filter(Boolean)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

export function ProfileIdentity({
  name,
  subtitle,
  initials,
  compact = false,
}: {
  name: string;
  subtitle: string;
  initials?: string;
  compact?: boolean;
}) {
  return (
    <div className={compact ? styles.identityCompact : styles.identity}>
      <span className={compact ? styles.avatarCompact : styles.avatar}>
        {initials || initialsFor(name)}
      </span>
      <span className={styles.identityCopy}>
        <strong>{name}</strong>
        <span>{subtitle}</span>
      </span>
    </div>
  );
}

export function UserProfilePanel({ profile }: { profile: UserProfile }) {
  return (
    <div className={styles.profile}>
      <div className={styles.hero}>
        <div className={styles.heroIdentityRow}>
          <ProfileIdentity name={profile.name} subtitle={`${profile.roleLabel} · ${profile.employeeCode}`} initials={profile.initials} />
        </div>
      </div>
      {profile.sections
        .filter((section) => section.details.length > 0)
        .map((section) => (
          <section className={styles.section} key={section.label}>
            <p className={`${styles.sectionLabel} hb-heading`}>{section.label}</p>
            <div className={styles.detailList}>
              {section.details.map((detail) => (
                <ListRow
                  key={detail.label}
                  leading={<IconSurface name={detail.icon} size="sm" shape="soft-square" tone="primary" glyphSize={20} />}
                  title={detail.value}
                  subtitle={detail.label}
                />
              ))}
            </div>
          </section>
        ))}
    </div>
  );
}

export function UserProfilePanelSkeleton() {
  return (
    <div className={styles.profile}>
      <div className={styles.hero}>
        <div className={styles.heroIdentityRow}>
          <div className={styles.identity}>
            <span className={styles.avatar} />
            <span className={styles.identityCopy}>
              <span className={styles.namePlaceholder} />
              <span className={styles.subtitlePlaceholder} />
            </span>
          </div>
        </div>
      </div>
      <section className={styles.section}>
        <span className={styles.sectionLabelPlaceholder} />
        <div className={styles.detailList}>
          <SkeletonRow />
          <SkeletonRow />
          <SkeletonRow />
        </div>
      </section>
    </div>
  );
}

export function AccountActionList({
  actions,
  onNavigate,
  onAction,
}: {
  actions: AccountAction[];
  onNavigate: (href: string) => void;
  onAction?: (action: AccountAction) => void;
}) {
  return (
    <div className={styles.list}>
      {actions.map((action) => (
        <ListRow
          key={action.href ?? action.label}
          leading={
            <Icon
              name={action.icon}
              size={22}
              color={action.destructive ? "var(--color-error)" : "var(--color-primary)"}
            />
          }
          title={
            <span style={{ color: action.destructive ? "var(--color-error)" : undefined }}>
              {action.label}
            </span>
          }
          showChevron={!action.destructive}
          onClick={() => action.href ? onNavigate(action.href) : onAction?.(action)}
        />
      ))}
    </div>
  );
}
