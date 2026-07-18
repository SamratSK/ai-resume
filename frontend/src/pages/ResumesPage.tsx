import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useDropzone } from "react-dropzone";
import { AlertTriangle, FileSearch, FileText, Trash2, UploadCloud } from "lucide-react";
import { api } from "../lib/api";
import type { ResumeSummary } from "../lib/types";
import { ParseQualityBadge, Pill } from "../components/Badge";
import { EmptyState } from "../components/EmptyState";
import { Modal } from "../components/Modal";
import { Button, ErrorNotice, IconButton, PageHeader, PageLoader } from "../components/UI";
import { ProgressNote } from "../components/Spinner";

export function ResumesPage() {
  const [resumes, setResumes] = useState<ResumeSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState<ResumeSummary | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setResumes(await api.resumes.list());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load resumes.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => void load(), [load]);

  const upload = useCallback(async (files: File[]) => {
    if (!files.length) return;
    setUploading(true);
    setError("");
    setProgress(`Uploading ${files.length} ${files.length === 1 ? "file" : "files"}…`);
    try {
      const added = await api.resumes.upload(files, setProgress);
      setResumes((current) => {
        const addedIds = new Set(added.map((resume) => resume.doc_id));
        return [...current.filter((resume) => !addedIds.has(resume.doc_id)), ...added];
      });
      setProgress(`Processed ${added.length} ${added.length === 1 ? "resume" : "resumes"}`);
      window.setTimeout(() => setProgress(""), 2500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Resume extraction failed.");
      setProgress("");
    } finally {
      setUploading(false);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop: upload,
    noClick: true,
    noKeyboard: true,
    disabled: uploading,
    multiple: true,
  });

  const remove = async () => {
    if (!deleting) return;
    try {
      await api.resumes.remove(deleting.doc_id);
      setResumes((current) => current.filter((resume) => resume.doc_id !== deleting.doc_id));
      setDeleting(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete the resume.");
      setDeleting(null);
    }
  };

  return (
    <main className="mx-auto w-full max-w-6xl px-5 py-10 sm:px-6 sm:py-14">
      <PageHeader
        eyebrow="Candidate pool"
        title="Resumes"
        description="Upload source files, monitor extraction, and inspect the evidence behind every parsed field."
      />

      <section
        {...getRootProps()}
        className={`mt-8 flex min-h-44 flex-col items-center justify-center rounded-lg border border-dashed px-6 py-8 text-center transition-colors ${
          isDragActive ? "border-lavender bg-lavender-soft/60" : "border-border bg-surface"
        }`}
      >
        <input {...getInputProps()} />
        <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-lavender-soft text-lavender-ink">
          <UploadCloud size={22} />
        </div>
        <h2 className="mt-3 text-lg font-medium">{isDragActive ? "Drop files to begin" : "Add resume files"}</h2>
        <p className="mt-1 text-sm text-ink-soft">Drop one or more files here, or choose them from your device.</p>
        <Button className="mt-4" tone="lavender" onClick={open} disabled={uploading}>
          <FileText size={16} /> Choose files
        </Button>
      </section>

      {(uploading || progress) && (
        <div className="mt-4 rounded-lg border border-border-soft bg-surface-raised px-4 py-3">
          <ProgressNote label={progress || "Starting extraction…"} />
        </div>
      )}
      {error && <div className="mt-4"><ErrorNotice message={error} /></div>}

      {loading ? (
        <PageLoader label="Loading resumes" />
      ) : !resumes.length ? (
        <div className="mt-8">
          <EmptyState
            icon={<FileSearch size={28} />}
            title="No resumes extracted"
            description="Upload files above to start building the candidate pool."
          />
        </div>
      ) : (
        <section className="mt-9" aria-labelledby="resume-list-heading">
          <div className="mb-3 flex items-center justify-between">
            <h2 id="resume-list-heading" className="text-xl font-medium">Extracted candidates</h2>
            <span className="text-sm text-ink-faint">{resumes.length} total</span>
          </div>
          <div className="overflow-hidden rounded-lg border border-border-soft bg-surface-raised shadow-[var(--shadow-soft)]">
            {resumes.map((resume, index) => (
              <div
                key={resume.doc_id}
                className={`flex items-center gap-3 px-4 py-4 sm:px-5 ${index ? "border-t border-border-soft" : ""}`}
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-peach-soft text-peach-ink">
                  <FileText size={19} />
                </div>
                <Link to={`/resumes/${resume.doc_id}`} className="min-w-0 flex-1 focus-visible:outline-2 focus-visible:outline-lavender">
                  <p className="truncate text-sm font-semibold text-ink hover:text-lavender-ink">{resume.file}</p>
                  <p className="mt-0.5 truncate text-xs text-ink-faint">{resume.doc_id} · {resume.method}</p>
                </Link>
                <div className="hidden items-center gap-2 sm:flex">
                  <ParseQualityBadge quality={resume.parse_quality} />
                  {resume.anomaly_count > 0 && (
                    <Pill tone="amber"><AlertTriangle size={12} /> {resume.anomaly_count}</Pill>
                  )}
                </div>
                <IconButton
                  label={`Delete ${resume.file}`}
                  onClick={() => setDeleting(resume)}
                  className="hover:bg-rose-soft hover:text-rose-ink"
                >
                  <Trash2 size={16} />
                </IconButton>
              </div>
            ))}
          </div>
        </section>
      )}

      <Modal open={Boolean(deleting)} onClose={() => setDeleting(null)} title="Delete resume?">
        <p className="text-sm leading-relaxed text-ink-soft">
          This removes <strong className="text-ink">{deleting?.file}</strong> from the extracted candidate pool. Future scoring runs will no longer include it.
        </p>
        <div className="mt-6 flex justify-end gap-2">
          <Button tone="ghost" onClick={() => setDeleting(null)}>Cancel</Button>
          <Button tone="danger" onClick={remove}><Trash2 size={16} /> Delete</Button>
        </div>
      </Modal>
    </main>
  );
}
