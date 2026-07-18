import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { BriefcaseBusiness, Edit3, FileText, Plus, Search, Sparkles, Trash2, Users } from "lucide-react";
import { api } from "../lib/api";
import type { JobDescription } from "../lib/types";
import { Card } from "../components/Card";
import { ChipInput } from "../components/ChipInput";
import { EmptyState } from "../components/EmptyState";
import { Modal } from "../components/Modal";
import { Button, ErrorNotice, IconButton, PageHeader, PageLoader, TextInput } from "../components/UI";

const blankJD: JobDescription = {
  id: "",
  role: "",
  required_skills: [],
  preferred_skills: [],
  cgpa_min: 0,
  slots: 1,
};

export function JDsPage() {
  const [jds, setJds] = useState<JobDescription[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<JobDescription | null | undefined>(undefined);
  const [parsedDraft, setParsedDraft] = useState<JobDescription | null>(null);
  const [showParser, setShowParser] = useState(false);
  const [deleting, setDeleting] = useState<JobDescription | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setJds(await api.jds.list());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load job descriptions.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => void load(), [load]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return jds;
    return jds.filter((jd) =>
      [jd.role, jd.id, ...jd.required_skills, ...jd.preferred_skills].some((value) =>
        value.toLowerCase().includes(q),
      ),
    );
  }, [jds, search]);

  const remove = async () => {
    if (!deleting) return;
    try {
      await api.jds.remove(deleting.id);
      setJds((current) => current.filter((jd) => jd.id !== deleting.id));
      setDeleting(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete the job description.");
      setDeleting(null);
    }
  };

  return (
    <main className="mx-auto w-full max-w-6xl px-5 py-10 sm:px-6 sm:py-14">
      <PageHeader
        eyebrow="Roles"
        title="Job descriptions"
        description="Define what matters for each role, then score every extracted resume against the same criteria."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button tone="ghost" onClick={() => setShowParser(true)}><FileText size={17} /> Paste JD</Button>
            <Button onClick={() => { setParsedDraft(null); setEditing(null); }}><Plus size={17} /> New JD</Button>
          </div>
        }
      />

      <div className="relative mt-8 max-w-md">
        <Search size={17} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-faint" />
        <TextInput
          aria-label="Search job descriptions"
          placeholder="Search roles or skills"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          className="pl-10"
        />
      </div>

      {error && <div className="mt-5"><ErrorNotice message={error} /></div>}
      {loading ? (
        <PageLoader label="Loading job descriptions" />
      ) : !jds.length ? (
        <div className="mt-8">
          <EmptyState
            icon={<BriefcaseBusiness size={28} />}
            title="No job descriptions yet"
            description="Create a role to define its skill requirements and shortlist size."
            action={<Button onClick={() => { setParsedDraft(null); setEditing(null); }}><Plus size={17} /> Create first JD</Button>}
          />
        </div>
      ) : !filtered.length ? (
        <div className="mt-8">
          <EmptyState icon={<Search size={28} />} title="No matching roles" description="Try a role name, ID, or skill." />
        </div>
      ) : (
        <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((jd) => (
            <Card key={jd.id} className="group flex min-h-64 flex-col overflow-hidden p-5">
              <div className="flex items-start justify-between gap-4">
                <Link to={`/jds/${jd.id}`} className="min-w-0 focus-visible:outline-2 focus-visible:outline-lavender">
                  <p className="truncate text-xs font-semibold uppercase text-lavender-ink">{jd.id}</p>
                  <h2 className="mt-1 text-xl font-medium text-ink group-hover:text-lavender-ink">{jd.role}</h2>
                </Link>
                <div className="flex">
                  <IconButton label={`Edit ${jd.role}`} onClick={() => setEditing(jd)}><Edit3 size={16} /></IconButton>
                  <IconButton label={`Delete ${jd.role}`} onClick={() => setDeleting(jd)} className="hover:bg-rose-soft hover:text-rose-ink"><Trash2 size={16} /></IconButton>
                </div>
              </div>

              <div className="mt-5 flex flex-wrap gap-1.5">
                {jd.required_skills.slice(0, 4).map((skill) => (
                  <span key={skill} className="rounded-full bg-lavender-soft px-2.5 py-1 text-xs font-medium text-lavender-ink">{skill}</span>
                ))}
                {jd.required_skills.length > 4 && (
                  <span className="rounded-full bg-black/5 px-2.5 py-1 text-xs text-ink-soft">+{jd.required_skills.length - 4}</span>
                )}
              </div>

              <div className="mt-auto flex items-center justify-between border-t border-border-soft pt-4 text-sm text-ink-soft">
                <span className="flex items-center gap-1.5"><Users size={15} /> {jd.slots} {jd.slots === 1 ? "slot" : "slots"}</span>
                <span>CGPA {jd.cgpa_min}+</span>
              </div>
            </Card>
          ))}
        </div>
      )}

      <JDFormModal
        open={editing !== undefined}
        initial={editing ?? parsedDraft ?? blankJD}
        editing={Boolean(editing)}
        onClose={() => { setEditing(undefined); setParsedDraft(null); }}
        onSaved={(saved) => {
          setJds((current) => {
            const exists = current.some((jd) => jd.id === saved.id);
            return exists ? current.map((jd) => jd.id === saved.id ? saved : jd) : [...current, saved];
          });
          setEditing(undefined);
          setParsedDraft(null);
        }}
      />

      <RawJDModal
        open={showParser}
        onClose={() => setShowParser(false)}
        onParsed={(draft) => {
          setShowParser(false);
          setParsedDraft(draft);
          setEditing(null);
        }}
      />

      <Modal open={Boolean(deleting)} onClose={() => setDeleting(null)} title="Delete job description?">
        <p className="text-sm leading-relaxed text-ink-soft">
          This removes <strong className="text-ink">{deleting?.role}</strong> and its saved shortlist. Resume data is not affected.
        </p>
        <div className="mt-6 flex justify-end gap-2">
          <Button tone="ghost" onClick={() => setDeleting(null)}>Cancel</Button>
          <Button tone="danger" onClick={remove}><Trash2 size={16} /> Delete</Button>
        </div>
      </Modal>
    </main>
  );
}

function RawJDModal({
  open,
  onClose,
  onParsed,
}: {
  open: boolean;
  onClose: () => void;
  onParsed: (jd: JobDescription) => void;
}) {
  const [text, setText] = useState("");
  const [parsing, setParsing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) setError("");
  }, [open]);

  const parse = async (event: React.FormEvent) => {
    event.preventDefault();
    if (text.trim().length < 20) {
      setError("Paste at least a few sentences from the job posting.");
      return;
    }
    setParsing(true);
    setError("");
    try {
      onParsed(await api.jds.parse(text));
      setText("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not parse the job description.");
    } finally {
      setParsing(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Parse a job posting">
      <form onSubmit={parse}>
        {error && <div className="mb-4"><ErrorNotice message={error} /></div>}
        <label htmlFor="raw-jd" className="mb-2 block text-sm font-medium text-ink">
          Job description
        </label>
        <textarea
          id="raw-jd"
          rows={11}
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="Paste the unstructured job posting here..."
          className="w-full resize-y rounded-xl border border-border bg-white px-3.5 py-3 text-sm leading-relaxed text-ink outline-none transition focus:border-lavender focus:ring-2 focus:ring-lavender/25"
        />
        <p className="mt-2 flex items-center gap-1.5 text-xs text-ink-soft">
          <Sparkles size={13} /> You can review every extracted field before saving.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <Button type="button" tone="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" busy={parsing}><FileText size={16} /> Parse draft</Button>
        </div>
      </form>
    </Modal>
  );
}

function JDFormModal({
  open,
  initial,
  editing,
  onClose,
  onSaved,
}: {
  open: boolean;
  initial: JobDescription;
  editing: boolean;
  onClose: () => void;
  onSaved: (jd: JobDescription) => void;
}) {
  const [form, setForm] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) {
      setForm(initial);
      setError("");
    }
  }, [open, initial]);

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!form.id.trim() || !form.role.trim()) {
      setError("ID and role are required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const payload = { ...form, id: form.id.trim(), role: form.role.trim() };
      onSaved(editing ? await api.jds.update(form.id, payload) : await api.jds.create(payload));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the job description.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title={editing ? "Edit job description" : "Create job description"}>
      <form onSubmit={save} className="space-y-4">
        {error && <ErrorNotice message={error} />}
        <div className="grid gap-4 sm:grid-cols-2">
          <TextInput
            label="ID"
            value={form.id}
            disabled={editing}
            placeholder="backend_dev"
            pattern="[A-Za-z0-9_-]+"
            title="Use letters, numbers, underscores, or hyphens"
            onChange={(e) => setForm({ ...form, id: e.target.value.toLowerCase().replace(/\s+/g, "_") })}
          />
          <TextInput label="Role" value={form.role} placeholder="Backend Developer" onChange={(e) => setForm({ ...form, role: e.target.value })} />
        </div>
        <ChipInput label="Required skills" values={form.required_skills} onChange={(required_skills) => setForm({ ...form, required_skills })} placeholder="Python, REST APIs…" />
        <ChipInput label="Preferred skills" tone="peach" values={form.preferred_skills} onChange={(preferred_skills) => setForm({ ...form, preferred_skills })} placeholder="Docker, AWS…" />
        <div className="grid gap-4 sm:grid-cols-2">
          <TextInput label="Minimum CGPA" type="number" min="0" step="0.1" value={form.cgpa_min} onChange={(e) => setForm({ ...form, cgpa_min: Number(e.target.value) })} />
          <TextInput label="Shortlist slots" type="number" min="1" step="1" value={form.slots} onChange={(e) => setForm({ ...form, slots: Math.max(1, Number(e.target.value)) })} />
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" tone="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" busy={saving}>{editing ? "Save changes" : "Create JD"}</Button>
        </div>
      </form>
    </Modal>
  );
}
