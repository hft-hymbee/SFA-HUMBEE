import React from "react";
import { Icon } from "../core/Icon.jsx";

/* Humbee ApprovalTimeline — vertical status thread for the approval engine
   (requested → approved / edited / rejected). Used on My requests, Order detail, Beat detail. */
const TONE = {
  done:     { color: "var(--color-success)", surface: "var(--color-success-surface)", icon: "Check" },
  edited:   { color: "var(--color-info)", surface: "var(--color-info-surface)", icon: "Edit" },
  rejected: { color: "var(--color-error)", surface: "var(--color-error-surface)", icon: "Close" },
  pending:  { color: "var(--color-primary)", surface: "var(--color-warning-surface)", icon: "Schedule" },
  current:  { color: "var(--color-primary)", surface: "var(--color-primary-surface)", icon: "Schedule" },
  future:   { color: "var(--color-text-disabled)", surface: "var(--color-neutral-200)", icon: "Schedule" },
};

const TIMELINE_MOTION = `
  @keyframes hb-timeline-dot-enter {
    from { opacity: 0; transform: translateY(3px) scale(0.88); }
    to { opacity: 1; transform: scale(1); }
  }
  @keyframes hb-timeline-content-enter {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @keyframes hb-timeline-line-grow {
    from { opacity: 0; transform: scaleY(0); }
    to { opacity: var(--hb-timeline-line-opacity); transform: scaleY(1); }
  }
  @keyframes hb-timeline-current-pulse {
    0%, 100% {
      box-shadow:
        inset 0 1px 1px rgba(255, 255, 255, 0.86),
        inset 0 -5px 8px color-mix(in srgb, var(--hb-timeline-tone-color) 13%, transparent),
        0 7px 12px -8px color-mix(in srgb, var(--hb-timeline-tone-color) 66%, transparent),
        0 2px 4px rgba(29, 22, 13, 0.12),
        0 0 0 0 color-mix(in srgb, var(--color-primary) 0%, transparent);
    }
    50% {
      box-shadow:
        inset 0 1px 1px rgba(255, 255, 255, 0.86),
        inset 0 -5px 8px color-mix(in srgb, var(--hb-timeline-tone-color) 13%, transparent),
        0 7px 12px -8px color-mix(in srgb, var(--hb-timeline-tone-color) 66%, transparent),
        0 2px 4px rgba(29, 22, 13, 0.12),
        0 0 0 5px color-mix(in srgb, var(--color-primary) 14%, transparent);
    }
  }
  .hb-approval-timeline__dot {
    animation: hb-timeline-dot-enter 280ms cubic-bezier(0.16, 1, 0.3, 1) both;
    animation-delay: var(--hb-timeline-step-delay);
    position: relative;
    overflow: hidden;
    box-sizing: border-box;
    border: 1px solid color-mix(in srgb, var(--hb-timeline-tone-color) 26%, #fff);
    background:
      radial-gradient(circle at 30% 22%, rgba(255, 255, 255, 0.95), transparent 32%),
      linear-gradient(145deg, color-mix(in srgb, var(--hb-timeline-tone-surface) 84%, #fff), var(--hb-timeline-tone-surface) 54%, color-mix(in srgb, var(--hb-timeline-tone-color) 20%, var(--hb-timeline-tone-surface)));
    box-shadow:
      inset 0 1px 1px rgba(255, 255, 255, 0.86),
      inset 0 -5px 8px color-mix(in srgb, var(--hb-timeline-tone-color) 13%, transparent),
      0 7px 12px -8px color-mix(in srgb, var(--hb-timeline-tone-color) 66%, transparent),
      0 2px 4px rgba(29, 22, 13, 0.12);
    transform-style: preserve-3d;
    transition: background-color 200ms ease, box-shadow 200ms ease, transform 200ms ease;
    will-change: opacity, transform;
  }
  .hb-approval-timeline__dot::after {
    content: "";
    position: absolute;
    inset: 4px 6px auto;
    height: 8px;
    border-radius: 999px;
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.72), rgba(255, 255, 255, 0));
    pointer-events: none;
  }
  .hb-approval-timeline__icon {
    position: relative;
    z-index: 1;
    filter: drop-shadow(0 1px 0 rgba(255, 255, 255, 0.7)) drop-shadow(0 2px 2px color-mix(in srgb, var(--hb-timeline-tone-color) 28%, transparent));
    transform: translateZ(8px);
  }
  .hb-approval-timeline__dot[data-current="true"] {
    animation-name: hb-timeline-dot-enter, hb-timeline-current-pulse;
    animation-duration: 280ms, 2.4s;
    animation-timing-function: cubic-bezier(0.16, 1, 0.3, 1), ease-in-out;
    animation-fill-mode: both, none;
    animation-delay: var(--hb-timeline-step-delay), calc(var(--hb-timeline-step-delay) + 360ms);
    animation-iteration-count: 1, infinite;
  }
  .hb-approval-timeline__content {
    animation: hb-timeline-content-enter 320ms cubic-bezier(0.16, 1, 0.3, 1) both;
    animation-delay: calc(var(--hb-timeline-step-delay) + 80ms);
    will-change: opacity, transform;
  }
  .hb-approval-timeline__line {
    animation: hb-timeline-line-grow 300ms cubic-bezier(0.16, 1, 0.3, 1) both;
    animation-delay: calc(var(--hb-timeline-step-delay) + 160ms);
    transform-origin: top;
    will-change: opacity, transform;
  }
  @media (prefers-reduced-motion: reduce) {
    .hb-approval-timeline__content,
    .hb-approval-timeline__dot,
    .hb-approval-timeline__line {
      animation: none;
      transition: none;
    }
  }
`;

export function ApprovalTimeline({ steps = [], style }) {
  const motionKey = JSON.stringify(steps);

  return (
    <div key={motionKey} className="hb-approval-timeline" style={{ fontFamily: "var(--font-family-base, Lato, sans-serif)", ...style }}>
      {steps.map((s, i) => {
        const tone = TONE[s.state] || TONE.future;
        const last = i === steps.length - 1;
        const muted = s.state === "future";
        const delay = Math.min(i, 6) * 300;
        return (
          <div
            key={`${s.label}-${s.state}`}
            className="hb-approval-timeline__step"
            style={{ "--hb-timeline-step-delay": `${delay}ms`, display: "flex", gap: 12 }}
          >
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
              <div
                aria-current={s.state === "current" ? "step" : undefined}
                className="hb-approval-timeline__dot"
                data-current={s.state === "current"}
                style={{
                  "--hb-timeline-tone-color": tone.color,
                  "--hb-timeline-tone-surface": tone.surface,
                  width: 28,
                  height: 28,
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                <Icon className="hb-approval-timeline__icon" name={tone.icon} size={16} color={tone.color} />
              </div>
              {!last && <div className="hb-approval-timeline__line" style={{ "--hb-timeline-line-opacity": muted ? 1 : 0.4, width: 2, flex: 1, minHeight: 20, background: muted ? "var(--color-neutral-300)" : tone.color, opacity: "var(--hb-timeline-line-opacity)" }} />}
            </div>
            <div className="hb-approval-timeline__content" style={{ paddingBottom: last ? 0 : 16, flex: 1 }}>
              <div className="hb-heading" style={{ color: muted ? "var(--color-text-placeholder)" : "var(--color-text-primary)", fontSize: "var(--text-body-size)", lineHeight: "var(--text-body-line)" }}>{s.label}</div>
              {s.detail && <div style={{ color: "var(--color-text-secondary)", fontSize: "var(--text-body-sm-size)", lineHeight: "var(--text-body-sm-line)", marginTop: 2 }}>{s.detail}</div>}
              {s.time && <div style={{ color: "var(--color-text-secondary)", fontSize: "var(--text-caption-size)", lineHeight: "var(--text-caption-line)", marginTop: 2 }}>{s.time}</div>}
            </div>
          </div>
        );
      })}
      <style>{TIMELINE_MOTION}</style>
    </div>
  );
}

export default ApprovalTimeline;
