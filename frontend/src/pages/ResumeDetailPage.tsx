import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { AlertTriangle, ChevronLeft, ChevronRight, FileImage, FileText, Info, MapPinOff } from "lucide-react";
import { api } from "../lib/api";
import type { Confidence, FieldValue, ProvenanceLegendEntry, ProvenancePayload, ResumeRecord } from "../lib/types";
import { FieldConfidenceBadge, ParseQualityBadge, Pill } from "../components/Badge";
import { Card } from "../components/Card";
import { ErrorNotice, IconButton, PageLoader } from "../components/UI";

export function ResumeDetailPage() {
  const { resumeId = "" } = useParams();
  const [resume, setResume] = useState<ResumeRecord | null>(null);
  const [provenance, setProvenance] = useState<ProvenancePayload | null>(null);
  const [selectedField, setSelectedField] = useState<string | null>(null);
  const [leftPane, setLeftPane] = useState(() => {
    const saved = Number(localStorage.getItem(`sift-resume-pane:${resumeId}`));
    return saved >= 40 && saved <= 68 ? saved : 56;
  });
  const [error, setError] = useState("");
  const layoutRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setResume(null);
    setError("");
    Promise.all([api.resumes.get(resumeId), api.resumes.pages(resumeId)])
      .then(([record, pages]) => {
        setResume(record);
        setProvenance(pages);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load resume."));
  }, [resumeId]);

  const identity = useMemo(() => resume ? [
    ["Full name", resume.full_name],
    ["Email", resume.email],
    ["Phone", resume.phone],
  ] as const : [], [resume]);

  const education = useMemo(() => resume ? [
    ["College", resume.college],
    ["Degree", resume.degree],
    ["Branch", resume.branch],
    ["Graduation year", resume.graduation_year],
    ["CGPA", resume.cgpa],
  ] as const : [], [resume]);

  if (error) {
    return <main className="mx-auto max-w-4xl px-5 py-12 sm:px-6"><ErrorNotice message={error} /></main>;
  }
  if (!resume) return <PageLoader label="Loading extracted resume" />;

  const candidateName = textValue(resume.full_name) || resume.file;
  const provenanceByField = new Map(provenance?.legend.map((entry) => [entry.field, entry]));
  const selectField = (field: string) => setSelectedField((current) => current === field ? null : field);
  const resizePane = (clientX: number) => {
    const rect = layoutRef.current?.getBoundingClientRect();
    if (!rect) return;
    const next = Math.max(40, Math.min(68, (clientX - rect.left) / rect.width * 100));
    setLeftPane(next);
    localStorage.setItem(`sift-resume-pane:${resumeId}`, String(next));
  };
  const startResize = (event: React.PointerEvent<HTMLButtonElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    resizePane(event.clientX);
  };

  return (
    <main className="mx-auto w-full max-w-7xl px-5 py-8 sm:px-6 sm:py-12">
      <div className="flex flex-col gap-4 border-b border-border-soft pb-7 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <p className="mb-2 text-xs font-semibold uppercase text-lavender-ink">{resume.file}</p>
          <h1 className="break-words text-3xl font-extrabold sm:text-4xl">{candidateName}</h1>
          <p className="mt-2 text-sm text-ink-soft">Extracted with {resume.method}</p>
        </div>
        <div className="flex gap-2">
          <ParseQualityBadge quality={resume.parse_quality} />
          {resume.anomalies.length > 0 && <Pill tone="amber"><AlertTriangle size={12} /> {resume.anomalies.length} anomalies</Pill>}
        </div>
      </div>

      <div
        ref={layoutRef}
        className="resume-layout mt-7 items-start"
        style={{ "--resume-left": `${leftPane}%` } as React.CSSProperties}
      >
        <div className="resume-fields min-w-0 space-y-7">
          <FieldSection title="Identity" fields={identity} provenance={provenanceByField} onSelect={selectField} />
          <FieldSection title="Education" fields={education} provenance={provenanceByField} onSelect={selectField} />

          <section>
            <SectionHeading title="Skills" count={resume.skills.length} />
            {resume.skills.length ? (
              <div className="flex flex-wrap gap-2">
                {resume.skills.map((skill, index) => (
                  <EvidenceChip
                    key={`${textValue(skill)}-${index}`}
                    field={`skills.${index}`}
                    value={textValue(skill) || "Unknown skill"}
                    confidence={skill.confidence}
                    evidence={skill.evidence}
                    source={provenanceByField.get(`skills.${index}`)}
                    onSelect={selectField}
                  />
                ))}
              </div>
            ) : <MissingValue />}
          </section>

          <EntrySection
            title="Projects"
            entries={resume.projects.map((project) => ({
              field: `projects.${resume.projects.indexOf(project)}`,
              title: project.title || "Untitled project",
              subtitle: project.one_liner,
              evidence: project.evidence,
              confidence: project.confidence,
            }))}
            provenance={provenanceByField}
            onSelect={selectField}
          />
          <EntrySection
            title="Experience"
            entries={resume.experience.map((experience) => ({
              field: `experience.${resume.experience.indexOf(experience)}`,
              title: [experience.role, experience.company].filter(Boolean).join(" at ") || "Experience",
              subtitle: experience.duration,
              evidence: experience.evidence,
              confidence: experience.confidence,
            }))}
            provenance={provenanceByField}
            onSelect={selectField}
          />

          {resume.certifications.length > 0 && (
            <section>
              <SectionHeading title="Certifications" count={resume.certifications.length} />
              <div className="space-y-2">
                {resume.certifications.map((item, index) => (
                  <FieldRow key={index} fieldKey={`certifications.${index}`} label={`Certification ${index + 1}`} field={item} source={provenanceByField.get(`certifications.${index}`)} onSelect={selectField} />
                ))}
              </div>
            </section>
          )}

          {resume.additional_fields.length > 0 && (
            <section>
              <SectionHeading title="Additional fields" count={resume.additional_fields.length} />
              <div className="space-y-2">
                {resume.additional_fields.map((field, index) => (
                  <FieldDisplay
                    key={`${field.field_name}-${index}`}
                    fieldKey={`additional_fields.${index}`}
                    label={field.field_name}
                    value={displayValue(field.raw_value, field.normalized_value)}
                    confidence={field.confidence}
                    evidence={field.evidence}
                    meta={field.data_type}
                    source={provenanceByField.get(`additional_fields.${index}`)}
                    onSelect={selectField}
                  />
                ))}
              </div>
            </section>
          )}
        </div>

        <button
          type="button"
          className="resume-divider focus-visible:outline-2 focus-visible:outline-lavender"
          role="separator"
          aria-label="Resize resume panels"
          aria-orientation="vertical"
          aria-valuemin={40}
          aria-valuemax={68}
          aria-valuenow={Math.round(leftPane)}
          onPointerDown={startResize}
          onPointerMove={(event) => {
            if (event.currentTarget.hasPointerCapture(event.pointerId)) resizePane(event.clientX);
          }}
          onKeyDown={(event) => {
            if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
              event.preventDefault();
              const next = Math.max(40, Math.min(68, leftPane + (event.key === "ArrowLeft" ? -2 : 2)));
              setLeftPane(next);
              localStorage.setItem(`sift-resume-pane:${resumeId}`, String(next));
            }
          }}
        />

        <aside className="resume-source min-w-0 space-y-5 lg:sticky lg:top-24">
          <SourceViewer
            payload={provenance}
            selectedField={selectedField}
            onSelectField={setSelectedField}
          />

          <Card className="p-5">
            <h2 className="flex items-center gap-2 text-lg font-medium">
              <AlertTriangle size={18} className={resume.anomalies.length ? "text-amber-ink" : "text-mint-ink"} />
              Extraction anomalies
            </h2>
            {resume.anomalies.length ? (
              <ul className="mt-4 space-y-2">
                {resume.anomalies.map((anomaly, index) => (
                  <li key={index} className="break-words rounded-lg bg-amber-soft px-3 py-2.5 text-sm text-amber-ink">{anomaly}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-sm text-ink-soft">No extraction anomalies were reported.</p>
            )}
          </Card>
        </aside>
      </div>
    </main>
  );
}

function SectionHeading({ title, count }: { title: string; count?: number }) {
  return (
    <div className="mb-3 flex items-center gap-2">
      <h2 className="text-xl font-extrabold">{title}</h2>
      {count !== undefined && <Pill>{count}</Pill>}
      <span className="ml-1 h-px flex-1 bg-border" aria-hidden="true" />
    </div>
  );
}

function FieldSection({
  title,
  fields,
  provenance,
  onSelect,
}: {
  title: string;
  fields: ReadonlyArray<readonly [string, FieldValue | null]>;
  provenance: Map<string, ProvenanceLegendEntry>;
  onSelect: (field: string) => void;
}) {
  return (
    <section>
      <SectionHeading title={title} />
      <div className="space-y-2">
        {fields.map(([label, field]) => {
          const fieldKey = label.toLowerCase().replaceAll(" ", "_");
          return <FieldRow key={label} fieldKey={fieldKey} label={label} field={field} source={provenance.get(fieldKey)} onSelect={onSelect} />;
        })}
      </div>
    </section>
  );
}

function FieldRow({
  fieldKey,
  label,
  field,
  source,
  onSelect,
}: {
  fieldKey: string;
  label: string;
  field: FieldValue | null;
  source?: ProvenanceLegendEntry;
  onSelect: (field: string) => void;
}) {
  return (
    <FieldDisplay
      label={label}
      fieldKey={fieldKey}
      value={field ? displayValue(field.raw_value, field.normalized_value, field.scale) : null}
      confidence={field?.confidence ?? null}
      evidence={field?.evidence ?? null}
      meta={field?.assumption ?? null}
      source={source}
      onSelect={onSelect}
    />
  );
}

function FieldDisplay({
  label,
  fieldKey,
  value,
  confidence,
  evidence,
  meta,
  source,
  onSelect,
}: {
  fieldKey: string;
  label: string;
  value: string | null;
  confidence: Confidence | null;
  evidence: string | null;
  meta?: string | null;
  source?: ProvenanceLegendEntry;
  onSelect: (field: string) => void;
}) {
  return (
    <details className="group rounded-lg border border-border-soft bg-surface-raised open:border-lavender/40">
      <summary className="flex cursor-pointer list-none items-center gap-3 px-4 py-3.5">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-ink-faint">{label}</p>
          <p className={`mt-0.5 break-words text-sm ${value ? "font-medium text-ink" : "text-ink-faint"}`}>{value || "Not found"}</p>
        </div>
        {(confidence || evidence || meta) && (
          <button
            type="button"
            aria-label={`Show details for ${label}`}
            title={`Show details for ${label}`}
            onClick={(event) => {
              event.preventDefault();
              const details = event.currentTarget.closest("details");
              if (details) details.open = !details.open;
            }}
            className="shrink-0 rounded-lg p-1.5 text-ink-faint hover:bg-lavender-soft hover:text-lavender-ink"
          >
            <Info size={16} />
          </button>
        )}
      </summary>
      {(confidence || evidence || meta) && (
        <div className="border-t border-border-soft px-4 py-3 text-sm">
          <div className="mb-3 flex items-center justify-between gap-3">
            <p className="text-xs font-extrabold text-ink-faint">Confidence</p>
            <FieldConfidenceBadge confidence={confidence} />
          </div>
          {evidence && (
            <>
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-extrabold text-ink-faint">Evidence</p>
                <button
                  type="button"
                  onClick={() => onSelect(fieldKey)}
                  disabled={!source?.located}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-lavender-soft px-2.5 py-1.5 text-xs font-extrabold text-lavender-ink disabled:bg-black/5 disabled:text-ink-faint"
                >
                  {source?.located ? <FileImage size={14} /> : <MapPinOff size={14} />}
                  {source?.located ? "Locate on PDF" : "Source not located"}
                </button>
              </div>
              <blockquote className="mt-1.5 border-l-2 border-lavender pl-3 leading-relaxed text-ink-soft">{evidence}</blockquote>
            </>
          )}
          {meta && <p className="mt-2 text-xs text-ink-faint">{meta}</p>}
        </div>
      )}
    </details>
  );
}

function EvidenceChip({
  field,
  value,
  confidence,
  evidence,
  source,
  onSelect,
}: {
  field: string;
  value: string;
  confidence: Confidence | null;
  evidence: string | null;
  source?: ProvenanceLegendEntry;
  onSelect: (field: string) => void;
}) {
  return (
    <details className="relative">
      <summary className="cursor-pointer list-none rounded-full bg-lavender-soft px-3 py-1.5 text-sm font-medium text-lavender-ink hover:bg-lavender/25">
        {value}
      </summary>
      <div className="fixed inset-x-4 bottom-4 z-[var(--z-dropdown)] w-auto min-w-0 rounded-lg border border-border-soft bg-surface-raised p-3 text-xs shadow-[var(--shadow-soft)] sm:absolute sm:inset-x-auto sm:bottom-auto sm:left-0 sm:mt-2 sm:w-80">
        <FieldConfidenceBadge confidence={confidence} />
        <p className="mt-2 leading-relaxed text-ink-soft">{evidence || "No evidence quote available."}</p>
        {evidence && (
          <button type="button" onClick={() => onSelect(field)} disabled={!source?.located} className="mt-2 text-xs font-semibold text-lavender-ink disabled:text-ink-faint">
            {source?.located ? "Show source" : "Source not located"}
          </button>
        )}
      </div>
    </details>
  );
}

function EntrySection({
  title,
  entries,
  provenance,
  onSelect,
}: {
  title: string;
  entries: Array<{ field: string; title: string; subtitle: string | null; evidence: string | null; confidence: Confidence | null }>;
  provenance: Map<string, ProvenanceLegendEntry>;
  onSelect: (field: string) => void;
}) {
  return (
    <section>
      <SectionHeading title={title} count={entries.length} />
      {entries.length ? (
        <div className="space-y-3">
          {entries.map((entry, index) => (
            <details key={index} className="rounded-lg border border-border-soft bg-surface-raised">
              <summary className="flex cursor-pointer list-none items-start justify-between gap-4 px-4 py-4">
                <div>
                  <h3 className="text-base font-medium">{entry.title}</h3>
                  {entry.subtitle && <p className="mt-1 text-sm leading-relaxed text-ink-soft">{entry.subtitle}</p>}
                </div>
                <button
                  type="button"
                  aria-label={`Show details for ${entry.title}`}
                  title={`Show details for ${entry.title}`}
                  onClick={(event) => {
                    event.preventDefault();
                    const details = event.currentTarget.closest("details");
                    if (details) details.open = !details.open;
                  }}
                  className="shrink-0 rounded-lg p-1.5 text-ink-faint hover:bg-peach-soft hover:text-peach-ink"
                >
                  <Info size={16} />
                </button>
              </summary>
              {(entry.evidence || entry.confidence) && (
                <div className="border-t border-border-soft px-4 py-3">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <p className="text-xs font-extrabold text-ink-faint">Confidence</p>
                    <FieldConfidenceBadge confidence={entry.confidence} />
                  </div>
                  {entry.evidence && (
                    <>
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-xs font-extrabold text-ink-faint">Evidence</p>
                        <button
                          type="button"
                          onClick={() => onSelect(entry.field)}
                          disabled={!provenance.get(entry.field)?.located}
                          className="inline-flex items-center gap-1.5 rounded-lg bg-lavender-soft px-2.5 py-1.5 text-xs font-extrabold text-lavender-ink disabled:bg-black/5 disabled:text-ink-faint"
                        >
                          {provenance.get(entry.field)?.located ? <FileImage size={14} /> : <MapPinOff size={14} />}
                          {provenance.get(entry.field)?.located ? "Locate on PDF" : "Source not located"}
                        </button>
                      </div>
                      <blockquote className="mt-1.5 border-l-2 border-peach pl-3 text-sm leading-relaxed text-ink-soft">{entry.evidence}</blockquote>
                    </>
                  )}
                </div>
              )}
            </details>
          ))}
        </div>
      ) : <MissingValue />}
    </section>
  );
}

function SourceViewer({
  payload,
  selectedField,
  onSelectField,
}: {
  payload: ProvenancePayload | null;
  selectedField: string | null;
  onSelectField: (field: string | null) => void;
}) {
  const [pageNumber, setPageNumber] = useState(1);
  const [annotationMode, setAnnotationMode] = useState<"focus" | "all" | "off">("focus");
  const viewerRef = useRef<HTMLDivElement>(null);
  const selected = payload?.legend.find((entry) => entry.field === selectedField && entry.located);
  const page = payload?.pages.find((entry) => entry.page === pageNumber);
  const pageEntries = payload?.legend.filter((entry) => entry.located && entry.page === pageNumber) ?? [];
  const markers = groupMarkers(
    annotationMode === "all"
      ? pageEntries
      : annotationMode === "focus" && selected
        ? pageEntries.filter((entry) => entry.field === selected.field)
        : [],
  );

  useEffect(() => {
    if (selected?.page) {
      setPageNumber(selected.page);
      viewerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [selectedField, selected?.page]);

  if (!payload) {
    return (
      <Card className="flex min-h-80 items-center justify-center p-8 text-sm text-ink-soft">
        Loading source document…
      </Card>
    );
  }

  if (!payload.available || !page) {
    return (
      <Card className="overflow-hidden">
        <div className="border-b border-border-soft px-5 py-4">
          <h2 className="flex items-center gap-2 text-lg font-medium"><FileImage size={18} /> Source document</h2>
        </div>
        <div className="flex min-h-72 flex-col items-center justify-center px-7 py-10 text-center">
          <FileText size={24} className="text-ink-faint" />
          <h3 className="mt-3 text-base font-medium">No source view available</h3>
          <p className="mt-2 text-sm text-ink-soft">{payload.reason || "This format does not include PDF provenance."}</p>
        </div>
      </Card>
    );
  }

  return (
    <Card className="scroll-mt-24 overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-soft px-4 py-3">
        <h2 className="flex items-center gap-2 text-lg font-medium"><FileImage size={18} /> Source document</h2>
        <div className="flex items-center gap-1">
          <IconButton label="Previous page" disabled={pageNumber <= 1} onClick={() => setPageNumber((current) => current - 1)}><ChevronLeft size={16} /></IconButton>
          <span className="min-w-16 text-center text-xs text-ink-soft">{pageNumber} / {payload.pages.length}</span>
          <IconButton label="Next page" disabled={pageNumber >= payload.pages.length} onClick={() => setPageNumber((current) => current + 1)}><ChevronRight size={16} /></IconButton>
        </div>
      </div>
      <div className="flex items-center justify-between border-b border-border-soft bg-surface px-4 py-2">
        <span className="text-xs font-extrabold text-ink-faint">Highlights</span>
        <div className="flex rounded-lg bg-black/5 p-1" role="group" aria-label="PDF highlight mode">
          {(["off", "focus", "all"] as const).map((mode) => (
            <button
              key={mode}
              type="button"
              aria-pressed={annotationMode === mode}
              onClick={() => setAnnotationMode(mode)}
              className={`rounded-md px-2.5 py-1 text-xs font-extrabold capitalize transition-colors ${
                annotationMode === mode ? "bg-surface-raised text-lavender-ink shadow-sm" : "text-ink-faint hover:text-ink"
              }`}
            >
              {mode}
            </button>
          ))}
        </div>
      </div>
      <div ref={viewerRef} className="max-h-[70vh] overflow-auto bg-black/[0.035] p-3">
        <div className="relative mx-auto w-full max-w-[720px]" style={{ aspectRatio: `${page.width}/${page.height}` }}>
          <img
            src={`${page.image_url}?annotations=${annotationMode === "all" ? "true" : "false"}`}
            alt={`Resume page ${page.page}`}
            className="block h-auto w-full shadow-sm"
          />
          {markers.map((marker) => {
            const [left, top] = marker.bbox;
            const isSelected = marker.fields.includes(selectedField || "");
            return (
              <button
                key={marker.key}
                type="button"
                aria-label={`Show ${marker.label} source`}
                title={marker.fullLabel}
                onClick={() => onSelectField(marker.fields[0])}
                className={`absolute z-10 max-w-36 truncate rounded-md border px-1.5 py-0.5 text-left text-[10px] font-bold leading-tight text-ink shadow-sm transition-transform hover:scale-105 ${isSelected ? "ring-2 ring-white" : ""}`}
                style={{
                  left: `${left / page.width * 100}%`,
                  top: `${top / page.height * 100}%`,
                  transform: top < 34 ? "translateY(2px)" : "translateY(calc(-100% - 2px))",
                  borderColor: marker.color,
                  backgroundColor: `${marker.color}E8`,
                }}
              >
                {marker.label}
              </button>
            );
          })}
          {annotationMode !== "off" && selected?.rendered_bbox && selected.page === pageNumber && (
            <button
              key={`${selected.field}-${selectedField}`}
              type="button"
              aria-label={`Highlighted source for ${selected.label}`}
              onClick={() => onSelectField(null)}
              className="source-pulse absolute border-2"
              style={{
                left: `${selected.rendered_bbox[0] / page.width * 100}%`,
                top: `${selected.rendered_bbox[1] / page.height * 100}%`,
                width: `${(selected.rendered_bbox[2] - selected.rendered_bbox[0]) / page.width * 100}%`,
                height: `${(selected.rendered_bbox[3] - selected.rendered_bbox[1]) / page.height * 100}%`,
                borderColor: selected.color,
                backgroundColor: `${selected.color}55`,
                borderRadius: "6px",
              }}
            />
          )}
        </div>
      </div>
    </Card>
  );
}

function groupMarkers(entries: ProvenanceLegendEntry[]) {
  const groups = new Map<string, {
    key: string;
    bbox: [number, number, number, number];
    color: string;
    fields: string[];
    labels: string[];
  }>();
  for (const entry of entries) {
    if (!entry.rendered_bbox) continue;
    const key = `${entry.color}:${entry.rendered_bbox.map((value) => Math.round(value / 4) * 4).join(":")}`;
    const current = groups.get(key);
    if (current) {
      current.fields.push(entry.field);
      if (!current.labels.includes(entry.label)) current.labels.push(entry.label);
    } else {
      groups.set(key, {
        key,
        bbox: entry.rendered_bbox,
        color: entry.color,
        fields: [entry.field],
        labels: [entry.label],
      });
    }
  }
  return [...groups.values()].map((group) => ({
    ...group,
    label: group.labels.length > 2 ? `${group.labels.slice(0, 2).join(", ")} +${group.labels.length - 2}` : group.labels.join(", "),
    fullLabel: group.labels.join(", "),
  }));
}

function MissingValue() {
  return <p className="rounded-lg border border-dashed border-border px-4 py-5 text-sm text-ink-faint">Nothing was extracted for this section.</p>;
}

function textValue(field: FieldValue | null) {
  if (!field) return null;
  return displayValue(field.raw_value, field.normalized_value, field.scale);
}

function displayValue(raw: string | null, normalized: unknown, scale?: string | null): string | null {
  const value = normalized ?? raw;
  if (value === null || value === undefined || value === "") return null;
  const rendered = typeof value === "object" ? JSON.stringify(value) : String(value);
  return scale ? `${rendered} (${scale})` : rendered;
}
