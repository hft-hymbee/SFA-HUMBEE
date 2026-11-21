import { Icon } from "humbee-design-system";
import type { ReactNode } from "react";
import type { OutletListItem } from "@/src/shared/outlet-list";
import styles from "./outlet-identity.module.css";

const VISIBLE_MANUFACTURERS = 3;

type OutletIdentitySource = Pick<OutletListItem, "gstinPan" | "district" | "manufacturers">;

function OutletIdentity({ outlet, note }: { outlet: OutletIdentitySource; note?: string | null }) {
  const manufacturers = outlet.manufacturers ?? [];
  const shownManufacturers = manufacturers.slice(0, VISIBLE_MANUFACTURERS);
  const hiddenManufacturers = manufacturers.length - shownManufacturers.length;
  return (
    <div className={styles.identity}>
      {note ? <span>{note}</span> : null}
      {outlet.district || outlet.gstinPan ? (
        <span className={styles.ids}>
          {outlet.district ? (
            <span className={styles.district}>
              <Icon name="LocationPin" size={14} color="currentColor" />
              <span className={styles.districtName}>{outlet.district}</span>
            </span>
          ) : null}
          {outlet.gstinPan ? (
            <span className={styles.taxId}>
              <span className={styles.taxIdLabel}>GSTIN/PAN</span>
              <span className={styles.taxIdValue}>{outlet.gstinPan}</span>
            </span>
          ) : null}
        </span>
      ) : null}
      {shownManufacturers.length ? (
        <span className={styles.chips} title={manufacturers.join(", ")}>
          {shownManufacturers.map((name) => <span key={name} className={styles.chip}>{name}</span>)}
          {hiddenManufacturers > 0 ? <span className={styles.more}>+{hiddenManufacturers}</span> : null}
        </span>
      ) : null}
    </div>
  );
}

/** ListRow subtitle for an outlet: the row's note, then district, GSTIN/PAN and manufacturer chips when known. */
export function outletSubtitle(outlet: OutletIdentitySource, note?: string | null): ReactNode {
  if (!outlet.district && !outlet.gstinPan && !outlet.manufacturers?.length) return note || undefined;
  return <OutletIdentity outlet={outlet} note={note} />;
}
