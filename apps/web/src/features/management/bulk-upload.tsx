"use client";

import { importBeatsApiV1BeatsImportPost, type BeatImportResponse } from "@humbee/api-contract";
import { BottomSheet, Button, Icon, IconButton, ListRow, TextField } from "humbee-design-system";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useMemo, useRef, useState, type DragEvent } from "react";
import { ApiClientError, createIdempotencyKey, getBrowserApiClient, idempotencyHeaders } from "@/src/shared/api";
import { downloadAdminReport } from "./download-report";
import { useGeographyMaster } from "./organization-hooks";
import { ManagementScreen, Notice, Section, SummaryGrid } from "./ui";
import styles from "./management.module.css";
import uploadStyles from "./bulk-upload.module.css";

const MAX_FILE_BYTES = 5 * 1_048_576;
const VISIBLE_ERRORS = 50;
const BEAT_SEARCH_THRESHOLD = 10;
const XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

const BEAT_REFERENCE_REPORTS = [
  {
    id: "geography-mapping",
    title: "Employee codes and their geography",
    subtitle: "Sales person codes with their assigned zones, states and districts",
    icon: "PersonRounded",
    path: "/api/v1/reporting/admin/reports/geography-mapping",
    filename: "geography-mapping-report.xlsx",
  },
  {
    id: "unassigned-outlets",
    title: "Outlets not on any beat",
    subtitle: "Outlet IDs to list in the Beat Outlets sheet",
    icon: "InventoryOutlined",
    path: "/api/v1/reporting/admin/reports/unassigned-outlets",
    filename: "unassigned-outlets-by-geography-report.xlsx",
  },
];

interface BeatImportRowError {
  sheet: string;
  row: number;
  column: string | null;
  code: string;
  message: string;
}

type ImportStage =
  | { kind: "idle" }
  | { kind: "checking"; file: File }
  | { kind: "ready"; file: File; idempotencyKey: string; preview: BeatImportResponse }
  | { kind: "creating"; file: File; idempotencyKey: string; preview: BeatImportResponse }
  | { kind: "invalid"; file: File; errors: BeatImportRowError[] }
  | { kind: "failed"; file: File | null; message: string }
  | { kind: "done"; result: BeatImportResponse };

function isRowError(value: unknown): value is BeatImportRowError {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return typeof item.sheet === "string" && typeof item.row === "number" && typeof item.message === "string";
}

/** Row errors from a `422 xlsx_validation_failed`; null for any other failure. */
function importRowErrors(error: unknown): BeatImportRowError[] | null {
  if (!(error instanceof ApiClientError) || error.code !== "xlsx_validation_failed") return null;
  const details = error.details as { errors?: unknown } | null;
  return Array.isArray(details?.errors) ? details.errors.filter(isRowError) : [];
}

function importErrorMessage(error: unknown) {
  if (!(error instanceof ApiClientError)) return "The file could not be checked. Try again.";
  // Header errors name the offending columns in details.
  const columns = (error.details as { columns?: unknown } | null)?.columns;
  const names = Array.isArray(columns) ? columns.filter((column): column is string => typeof column === "string") : [];
  if (!names.length) return error.message;
  return `${error.message} ${error.code === "xlsx_unknown_columns" ? "Not accepted" : "Missing"}: ${names.join(", ")}.`;
}

async function importBeats(file: File, options: { dryRun: true } | { dryRun: false; idempotencyKey: string }) {
  const result = await importBeatsApiV1BeatsImportPost({
    client: getBrowserApiClient(),
    body: { file },
    query: { dry_run: options.dryRun },
    headers: options.dryRun ? undefined : idempotencyHeaders(options.idempotencyKey),
    throwOnError: true,
  });
  return result.data;
}

function fileSizeLabel(bytes: number) {
  return bytes < 1_048_576 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1_048_576).toFixed(1)} MB`;
}

function countLabel(count: number, noun: string) {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

function csvCell(value: string | number | null) {
  const text = value === null ? "" : String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function downloadCsv(filename: string, rows: Array<Array<string | number | null>>) {
  const blob = new Blob([rows.map((row) => row.map(csvCell).join(",")).join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function BulkUploadHub() {
  const router = useRouter();
  return (
    <ManagementScreen view="bulk-upload">
      <div className={styles.content}>
        <Section label="Upload types">
          <div className={styles.card} style={{ padding: 0 }}>
            <ListRow
              leading={<Icon name="LocationMarker" size={22} color="var(--color-primary)" />}
              title="Beats"
              subtitle="Create many beats at once from one Excel file"
              showChevron
              onClick={() => router.push("/mgmt/bulk-upload-beats")}
            />
          </div>
        </Section>
      </div>
    </ManagementScreen>
  );
}

export function BeatBulkUpload() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const geography = useGeographyMaster();
  const inputRef = useRef<HTMLInputElement>(null);
  const checkToken = useRef(0);
  const [stage, setStage] = useState<ImportStage>({ kind: "idle" });
  const [dragging, setDragging] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [beatQuery, setBeatQuery] = useState("");
  const [pendingDownload, setPendingDownload] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);

  const preview = stage.kind === "ready" || stage.kind === "creating" ? stage.preview : stage.kind === "done" ? stage.result : null;
  const previewBeats = useMemo(() => {
    const beats = preview?.beats ?? [];
    const query = beatQuery.trim().toLocaleLowerCase();
    return query ? beats.filter((beat) => `${beat.name} ${beat.owner_employee_code}`.toLocaleLowerCase().includes(query)) : beats;
  }, [beatQuery, preview]);
  const outletTotal = preview?.beats.reduce((total, beat) => total + beat.outlet_count, 0) ?? 0;
  const ownerTotal = new Set(preview?.beats.map((beat) => beat.owner_employee_code)).size;
  const errorGroups = useMemo(() => {
    if (stage.kind !== "invalid") return [];
    const groups = new Map<string, BeatImportRowError[]>();
    stage.errors.slice(0, VISIBLE_ERRORS).forEach((error) => {
      groups.set(error.sheet, [...(groups.get(error.sheet) ?? []), error]);
    });
    return [...groups.entries()];
  }, [stage]);
  const currentFile = stage.kind === "idle" || stage.kind === "done" ? null : stage.file;
  const busy = stage.kind === "checking" || stage.kind === "creating";

  async function checkFile(file: File) {
    setBeatQuery("");
    setCreateError(null);
    if (!file.name.toLowerCase().endsWith(".xlsx")) {
      setStage({ kind: "failed", file, message: "Choose an Excel .xlsx file. Download the template above to start." });
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      setStage({ kind: "failed", file, message: "The file is larger than 5 MB. Split it into smaller files." });
      return;
    }
    const token = ++checkToken.current;
    setStage({ kind: "checking", file });
    try {
      const result = await importBeats(file, { dryRun: true });
      if (token !== checkToken.current) return;
      setStage({ kind: "ready", file, idempotencyKey: createIdempotencyKey(), preview: result });
    } catch (error) {
      if (token !== checkToken.current) return;
      const errors = importRowErrors(error);
      setStage(errors ? { kind: "invalid", file, errors } : { kind: "failed", file, message: importErrorMessage(error) });
    }
  }

  async function createBeats() {
    if (stage.kind !== "ready") return;
    setConfirmOpen(false);
    setCreateError(null);
    const { file, idempotencyKey } = stage;
    setStage({ ...stage, kind: "creating" });
    try {
      const result = await importBeats(file, { dryRun: false, idempotencyKey });
      setStage({ kind: "done", result });
      void queryClient.invalidateQueries({ queryKey: ["beats"] });
    } catch (error) {
      const errors = importRowErrors(error);
      setStage(errors ? { kind: "invalid", file, errors } : { ...stage, kind: "ready" });
      if (!errors) setCreateError(importErrorMessage(error));
    }
  }

  function pickFile() {
    setDownloadError(null);
    inputRef.current?.click();
  }

  function reset() {
    checkToken.current += 1;
    setStage({ kind: "idle" });
    setBeatQuery("");
    setDownloadError(null);
    setCreateError(null);
  }

  async function runDownload(id: string, path: string, filename: string) {
    setDownloadError(null);
    setPendingDownload(id);
    try {
      await downloadAdminReport(path, filename);
    } catch {
      setDownloadError("Couldn't download the file. Try again.");
    } finally {
      setPendingDownload(null);
    }
  }

  function downloadGeographyCodes() {
    const master = geography.data;
    if (!master) return;
    const zoneNames = new Map(master.zones.map((zone) => [zone.id, zone.name]));
    const states = new Map(master.states.map((state) => [state.id, state]));
    downloadCsv("geography-codes.csv", [
      ["Zone ID (C1)", "Zone", "State ID (C2)", "State", "District ID (C3)", "District"],
      ...master.districts.map((district) => {
        const state = states.get(district.state_id);
        return [state?.zone_id ?? "", zoneNames.get(state?.zone_id ?? "") ?? "", district.state_id, state?.name ?? "", district.id, district.name];
      }),
    ]);
  }

  function downloadErrors() {
    if (stage.kind !== "invalid") return;
    downloadCsv("beat-upload-errors.csv", [
      ["Sheet", "Row", "Column", "Problem"],
      ...stage.errors.map((error) => [error.sheet, error.row, error.column, error.message]),
    ]);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file && !busy) void checkFile(file);
  }

  const footer = stage.kind === "ready" || stage.kind === "creating" ? (
    <Button variant="filled" color="primary" label={`Create ${countLabel(stage.preview.beat_count, "beat")}`} loading={stage.kind === "creating"} disabled={stage.kind === "creating"} onClick={() => setConfirmOpen(true)} />
  ) : stage.kind === "done" ? (
    <>
      <Button variant="outlined" color="neutral" label="Upload another file" onClick={reset} />
      <Button variant="filled" color="primary" label="View beats" onClick={() => router.push("/mgmt/beats")} />
    </>
  ) : undefined;

  return (
    <ManagementScreen view="bulk-upload-beats" footer={footer}>
      <div className={styles.content}>
        <input
          ref={inputRef}
          className={uploadStyles.hiddenInput}
          type="file"
          accept={`.xlsx,${XLSX_TYPE}`}
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file) void checkFile(file);
          }}
        />
        {stage.kind === "done" ? (
          <>
            <Notice tone="success">{`${countLabel(stage.result.beat_count, "beat")} created. They are live for their sales persons now.`}</Notice>
            <SummaryGrid items={[[String(stage.result.beat_count), "Beats"], [String(outletTotal), "Outlets"], [String(ownerTotal), "Sales persons"]]} />
            <Section label="Created beats">
              <div className={styles.card} style={{ padding: 0 }}>
                {stage.result.beats.map((beat) => (
                  <ListRow key={beat.row} leading={<Icon name="CheckCircle" size={22} color="var(--color-success)" />} title={beat.name} subtitle={`${beat.owner_employee_code} · ${countLabel(beat.outlet_count, "outlet")}`} />
                ))}
              </div>
            </Section>
          </>
        ) : (
          <>
            <Section label="1. Prepare your file">
              <div className={styles.card} style={{ padding: 0 }}>
                <ListRow
                  leading={<Icon name="DownloadOutlined" size={22} color="var(--color-primary)" />}
                  title="Beat upload template"
                  subtitle="Excel file with the Beat Configuration and Beat Outlets sheets"
                  trailing={<IconButton iconName="DownloadOutlined" color="primary" disabled={pendingDownload !== null} onClick={() => { void runDownload("template", "/api/v1/beats/import/template", "beat-import-template.xlsx"); }} />}
                />
                <ListRow
                  leading={<Icon name="Map" size={22} color="var(--color-primary)" />}
                  title="Geography codes"
                  subtitle="Zone, state and district IDs for the C1, C2 and C3 columns"
                  trailing={<IconButton iconName="DownloadOutlined" color="primary" disabled={!geography.data} onClick={downloadGeographyCodes} />}
                />
                {BEAT_REFERENCE_REPORTS.map((report) => (
                  <ListRow
                    key={report.id}
                    leading={<Icon name={report.icon} size={22} color="var(--color-primary)" />}
                    title={report.title}
                    subtitle={report.subtitle}
                    trailing={<IconButton iconName="DownloadOutlined" color="primary" disabled={pendingDownload !== null} onClick={() => { void runDownload(report.id, report.path, report.filename); }} />}
                  />
                ))}
              </div>
              {downloadError ? <Notice tone="error">{downloadError}</Notice> : null}
              <div className={styles.card}>
                <ul className={uploadStyles.rules}>
                  <li>One beat per row in <strong>Beat Configuration</strong>; list each beat&apos;s outlets in <strong>Beat Outlets</strong> by Beat Name.</li>
                  <li>Frequency: <code>daily</code>, <code>weekly</code>, <code>fortnightly</code> or <code>monthly</code>. Visit Days like <code>Mon, Thu</code>. Week Cycle like <code>1, 3</code> for fortnightly and monthly.</li>
                  <li>Use IDs for zones, states and districts, separated by commas. They must sit inside the sales person&apos;s assigned geography.</li>
                  <li>Leave <strong>Categories</strong> blank.</li>
                  <li>Up to 200 beats and 10,000 outlet rows, 5 MB per file. If any row has a problem, no beats are created.</li>
                </ul>
              </div>
            </Section>
            <Section label="2. Upload and check">
              {currentFile ? (
                <div className={uploadStyles.fileRow}>
                  <Icon name="InventoryOutlined" size={20} color="var(--color-primary)" />
                  <span className={uploadStyles.fileName} title={currentFile.name}>{currentFile.name}</span>
                  <span className={uploadStyles.fileSize}>{fileSizeLabel(currentFile.size)}</span>
                  <Button variant="text" color="primary" size="small" label="Replace" disabled={busy} onClick={pickFile} />
                </div>
              ) : (
                <div
                  className={`${uploadStyles.dropzone}${dragging ? ` ${uploadStyles.dropzoneActive}` : ""}`}
                  onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={onDrop}
                >
                  <Icon name="InventoryOutlined" size={28} color="var(--color-primary)" />
                  <p className={uploadStyles.dropzoneTitle}>Upload the filled template</p>
                  <p className={uploadStyles.dropzoneHint}>.xlsx up to 5 MB. We check every row before anything is created.</p>
                  <Button variant="filled" color="primary" size="small" label="Choose file" onClick={pickFile} />
                </div>
              )}
              {stage.kind === "checking" ? <Notice>Checking every row in the file...</Notice> : null}
              {stage.kind === "failed" ? <Notice tone="error">{stage.message}</Notice> : null}
              {stage.kind === "invalid" ? (
                <>
                  <Notice tone="error">{`Fix ${countLabel(stage.errors.length, "problem")} and upload the file again. No beats were created.`}</Notice>
                  <div className={uploadStyles.actions}>
                    <Button variant="outlined" color="primary" size="small" label="Download problem list" leftIcon={<Icon name="DownloadOutlined" size={18} color="currentColor" />} onClick={downloadErrors} />
                    <Button variant="filled" color="primary" size="small" label="Upload corrected file" onClick={pickFile} />
                  </div>
                  <div className={styles.card} style={{ padding: 0 }}>
                    {errorGroups.map(([sheet, errors]) => (
                      <div key={sheet}>
                        <p className={uploadStyles.errorGroupLabel}>{sheet}</p>
                        {errors.map((error, index) => (
                          <ListRow
                            key={`${error.row}-${error.column ?? ""}-${index}`}
                            leading={<Icon name="Warning" size={20} color="var(--color-error)" />}
                            title={error.column ? `Row ${error.row} · ${error.column}` : `Row ${error.row}`}
                            subtitle={error.message}
                          />
                        ))}
                      </div>
                    ))}
                  </div>
                  {stage.errors.length > VISIBLE_ERRORS ? <Notice>{`Showing the first ${VISIBLE_ERRORS}. Download the problem list to see all ${stage.errors.length}.`}</Notice> : null}
                </>
              ) : null}
            </Section>
            {preview ? (
              <Section label="3. Review and create">
                <Notice tone="success">Every row passed the check. Nothing is created until you confirm.</Notice>
                {createError ? <Notice tone="error">{createError}</Notice> : null}
                <SummaryGrid items={[[String(preview.beat_count), "Beats"], [String(outletTotal), "Outlets"], [String(ownerTotal), "Sales persons"]]} />
                {preview.beats.length > BEAT_SEARCH_THRESHOLD ? (
                  <TextField
                    placeholder="Search beats or employee codes"
                    startAdornment={<Icon name="SearchOutlined" size={20} color="var(--color-text-placeholder)" />}
                    value={beatQuery}
                    onChange={(event) => setBeatQuery((event.target as HTMLInputElement).value)}
                  />
                ) : null}
                <div className={styles.card} style={{ padding: 0 }}>
                  {previewBeats.length ? previewBeats.map((beat) => (
                    <ListRow
                      key={beat.row}
                      leading={<Icon name="LocationMarker" size={22} color="var(--color-primary)" />}
                      title={beat.name}
                      subtitle={`${beat.owner_employee_code} · ${countLabel(beat.outlet_count, "outlet")}`}
                      meta={`Row ${beat.row}`}
                    />
                  )) : <ListRow title={`No beats match "${beatQuery}"`} />}
                </div>
              </Section>
            ) : null}
          </>
        )}
      </div>
      <BottomSheet open={confirmOpen} title={preview ? `Create ${countLabel(preview.beat_count, "beat")}?` : "Create beats?"} onClose={() => setConfirmOpen(false)}>
        <p className={styles.meta} style={{ margin: "0 0 var(--space-md)" }}>
          {`They go live immediately for ${countLabel(ownerTotal, "sales person")}, without a separate approval. ${countLabel(outletTotal, "outlet")} will be attached.`}
        </p>
        <div className={uploadStyles.sheetActions}>
          <Button variant="filled" color="primary" label="Create beats" onClick={() => { void createBeats(); }} style={{ width: "100%" }} />
          <Button variant="outlined" color="neutral" label="Cancel" onClick={() => setConfirmOpen(false)} style={{ width: "100%" }} />
        </div>
      </BottomSheet>
    </ManagementScreen>
  );
}
