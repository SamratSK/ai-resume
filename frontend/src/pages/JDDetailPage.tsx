import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  AlertTriangle,
  BotMessageSquare,
  Download,
  FileWarning,
  RefreshCw,
  Send,
  Sparkles,
  Trash2,
  Users,
} from "lucide-react";
import { api } from "../lib/api";
import type { ChatResponse, ChatSource, JobDescription, ScoredCandidate, ShortlistPayload } from "../lib/types";
import { ConfidenceBadge, ParseQualityBadge, Pill, TierBadge } from "../components/Badge";
import { Drawer } from "../components/Drawer";
import { EmptyState } from "../components/EmptyState";
import { Button, ErrorNotice, PageHeader, PageLoader } from "../components/UI";
import { ProgressNote } from "../components/Spinner";

export function JDDetailPage() {
  const { jdId = "" } = useParams();
  const [jd, setJd] = useState<JobDescription | null>(null);
  const [shortlist, setShortlist] = useState<ShortlistPayload | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState<ScoredCandidate | null>(null);
  const [leftTab, setLeftTab] = useState<"description" | "chat">("description");
  const [progress, setProgress] = useState("");
  const [error, setError] = useState("");
  const [scoring, setScoring] = useState(false);

  const resolveNames = useCallback(async (payload: ShortlistPayload) => {
    const candidates = [...payload.shortlist, ...payload.reserve, ...payload.excluded];
    const resolved = await Promise.all(
      candidates.map(async (candidate) => {
        try {
          const record = await api.resumes.get(candidate.doc_id);
          return [candidate.doc_id, String(record.full_name?.normalized_value ?? record.full_name?.raw_value ?? candidate.file)] as const;
        } catch {
          return [candidate.doc_id, candidate.file] as const;
        }
      }),
    );
    setNames(Object.fromEntries(resolved));
  }, []);

  const runScoring = useCallback(async () => {
    setScoring(true);
    setError("");
    setProgress("Preparing candidate pool…");
    try {
      const payload = await api.shortlist.run(jdId, setProgress);
      setShortlist(payload);
      void resolveNames(payload);
      setProgress("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not score this candidate pool.");
      setProgress("");
    } finally {
      setScoring(false);
    }
  }, [jdId, resolveNames]);

  useEffect(() => {
    let active = true;
    setJd(null);
    setShortlist(null);
    setError("");
    api.jds.get(jdId)
      .then((loaded) => {
        if (!active) return;
        setJd(loaded);
        void runScoring();
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "Could not load the job description.");
      });
    return () => {
      active = false;
    };
  }, [jdId, runScoring]);

  const counts = useMemo(() => shortlist ? {
    shortlisted: shortlist.shortlist.length,
    reserve: shortlist.reserve.length,
    excluded: shortlist.excluded.length,
  } : null, [shortlist]);

  if (!jd && !error) return <PageLoader label="Loading job description" />;

  return (
    <main className="mx-auto w-full max-w-[1600px] px-5 py-8 sm:px-6 sm:py-10">
      <div className="grid min-w-0 items-start gap-6 lg:grid-cols-[330px_minmax(0,1fr)] xl:grid-cols-[360px_minmax(0,1fr)]">
        {jd && (
          <aside className="min-w-0 lg:sticky lg:top-20">
            <div className="overflow-hidden rounded-lg border-2 border-ink bg-surface-raised shadow-[5px_5px_0_var(--color-lavender)]">
              <div className="bg-peach-soft/60 px-5 py-5">
                <p className="text-xs font-extrabold text-peach-ink">{jd.id}</p>
                <h1 className="mt-2 text-2xl font-extrabold leading-tight text-ink">{jd.role}</h1>
                <div className="mt-3 flex gap-3 text-sm font-semibold text-ink-soft">
                  <span>{jd.slots} {jd.slots === 1 ? "opening" : "openings"}</span>
                  <span>CGPA {jd.cgpa_min}+</span>
                </div>
              </div>

              <div className="grid grid-cols-2 border-y border-border bg-surface p-1.5" role="tablist" aria-label="Job workspace">
                <button
                  type="button"
                  role="tab"
                  aria-selected={leftTab === "description"}
                  onClick={() => setLeftTab("description")}
                  className={`rounded-lg px-3 py-2 text-sm font-extrabold transition-colors ${leftTab === "description" ? "bg-lavender-soft text-lavender-ink" : "text-ink-faint hover:bg-black/5"}`}
                >
                  Description
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={leftTab === "chat"}
                  onClick={() => setLeftTab("chat")}
                  className={`flex items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-sm font-extrabold transition-colors ${leftTab === "chat" ? "bg-mint-soft text-mint-ink" : "text-ink-faint hover:bg-black/5"}`}
                >
                  <BotMessageSquare size={15} /> Chat
                </button>
              </div>

              {leftTab === "description" ? (
                <JDDescription jd={jd} />
              ) : (
                <CandidateChatPanel jdId={jdId} role={jd.role} />
              )}
            </div>
          </aside>
        )}

        <section className="min-w-0">
          <PageHeader
            eyebrow={jd?.role ?? "Role"}
            title="Candidate pool"
            description={shortlist ? `${shortlist.candidates_evaluated} resumes evaluated against this job description.` : "Scoring resumes against this role."}
            actions={
              <>
                <Button tone="lavender" onClick={runScoring} disabled={scoring}><RefreshCw size={17} /> Rescore</Button>
                <a
                  href={shortlist && jd ? api.shortlist.csvUrl(jd.id) : undefined}
                  aria-disabled={!shortlist}
                  className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-lg px-4 text-sm font-extrabold transition-colors ${
                    shortlist ? "bg-ink text-white shadow-[0_3px_0_oklch(16%_0.04_274)] hover:bg-ink-soft" : "pointer-events-none bg-black/5 text-ink-faint"
                  }`}
                >
                  <Download size={17} /> CSV
                </a>
              </>
            }
          />

          {error && <div className="mt-6"><ErrorNotice message={error} /></div>}
          {scoring && (
            <div className="mt-6 rounded-lg border border-border bg-surface-raised px-5 py-4 shadow-[var(--shadow-soft)]">
              <ProgressNote label={progress || "Scoring candidates…"} />
            </div>
          )}

          {shortlist && counts && (
            <>
              <section className="mt-7 grid grid-cols-2 gap-3 xl:grid-cols-4" aria-label="Shortlist summary">
                <Stat label="Evaluated" value={shortlist.candidates_evaluated} tone="neutral" />
                <Stat label="Shortlisted" value={counts.shortlisted} tone="mint" />
                <Stat label="Reserve" value={counts.reserve} tone="peach" />
                <Stat label="Excluded" value={counts.excluded} tone="rose" />
              </section>

              {shortlist.slots_filled_note && (
                <div className="mt-4 flex items-start gap-2 rounded-lg bg-amber-soft px-4 py-3 text-sm font-semibold text-amber-ink">
                  <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                  {shortlist.slots_filled_note}
                </div>
              )}

              {!shortlist.candidates_evaluated ? (
                <div className="mt-8">
                  <EmptyState
                    icon={<Users size={28} />}
                    title="No candidates to score"
                    description="Upload and extract resumes, then return here to run the shortlist."
                    action={<Link className="text-sm font-semibold text-lavender-ink hover:underline" to="/resumes">Go to resumes</Link>}
                  />
                </div>
              ) : (
                <div className="mt-8 space-y-9">
                  <CandidateSection
                    title="Shortlisted"
                    description={`Top candidates selected for ${shortlist.slots} ${shortlist.slots === 1 ? "slot" : "slots"}.`}
                    candidates={shortlist.shortlist}
                    names={names}
                    onSelect={setSelected}
                  />
                  <CandidateSection
                    title="Reserve"
                    description="Eligible candidates below the current slot boundary."
                    candidates={shortlist.reserve}
                    names={names}
                    onSelect={setSelected}
                    emptyText="No reserve candidates in this scoring run."
                  />
                  <CandidateSection
                    title="Excluded"
                    description="Failed parses and candidates below the scoring cutoff remain visible for audit."
                    candidates={shortlist.excluded}
                    names={names}
                    onSelect={setSelected}
                    muted
                    emptyText="No candidates were excluded."
                  />
                </div>
              )}
            </>
          )}
        </section>
      </div>
      <ExplanationDrawer candidate={selected} name={selected ? names[selected.doc_id] ?? selected.file : ""} onClose={() => setSelected(null)} />
    </main>
  );
}

function JDDescription({ jd }: { jd: JobDescription }) {
  return (
    <div className="space-y-6 px-5 py-5">
      <section>
        <h2 className="text-xs font-extrabold text-ink-faint">Required skills</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {jd.required_skills.length
            ? jd.required_skills.map((skill) => <Pill key={skill} tone="lavender">{skill}</Pill>)
            : <span className="text-sm text-ink-faint">None specified</span>}
        </div>
      </section>
      <section className="border-t border-border-soft pt-5">
        <h2 className="text-xs font-extrabold text-ink-faint">Preferred skills</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {jd.preferred_skills.length
            ? jd.preferred_skills.map((skill) => <Pill key={skill} tone="peach">{skill}</Pill>)
            : <span className="text-sm text-ink-faint">None specified</span>}
        </div>
      </section>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone: "neutral" | "mint" | "peach" | "rose" }) {
  const colors = {
    neutral: "bg-surface-raised",
    mint: "bg-mint-soft",
    peach: "bg-peach-soft",
    rose: "bg-rose-soft",
  };
  return (
    <div className={`rounded-lg border border-border-soft p-4 ${colors[tone]}`}>
      <p className="text-xs font-medium text-ink-soft">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-ink">{value}</p>
    </div>
  );
}

function CandidateSection({
  title,
  description,
  candidates,
  names,
  onSelect,
  muted = false,
  emptyText,
}: {
  title: string;
  description: string;
  candidates: ScoredCandidate[];
  names: Record<string, string>;
  onSelect: (candidate: ScoredCandidate) => void;
  muted?: boolean;
  emptyText?: string;
}) {
  return (
    <section>
      <div className="mb-3 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-2xl font-medium">{title}</h2>
          <p className="mt-1 text-sm text-ink-soft">{description}</p>
        </div>
        <span className="text-sm text-ink-faint">{candidates.length} candidates</span>
      </div>
      {!candidates.length ? (
        <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-ink-faint">{emptyText}</p>
      ) : (
        <div className={`overflow-x-auto rounded-lg border border-border-soft shadow-[var(--shadow-soft)] ${muted ? "bg-black/[0.025]" : "bg-surface-raised"}`}>
          <table className="w-full min-w-[840px] border-collapse text-left">
            <thead>
              <tr className="border-b border-border-soft text-xs font-semibold text-ink-faint">
                <th className="w-16 px-4 py-3">Rank</th>
                <th className="px-4 py-3">Candidate</th>
                <th className="w-24 px-4 py-3">Score</th>
                <th className="w-72 px-4 py-3">Breakdown</th>
                <th className="w-28 px-4 py-3">Confidence</th>
                <th className="w-28 px-4 py-3">Parse</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((candidate) => (
                <tr
                  key={candidate.doc_id}
                  tabIndex={0}
                  onClick={() => onSelect(candidate)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelect(candidate);
                    }
                  }}
                  className={`cursor-pointer border-b border-border-soft last:border-b-0 hover:bg-lavender-soft/35 focus:bg-lavender-soft/35 focus:outline-none ${muted ? "text-ink-soft grayscale-[0.25]" : ""}`}
                >
                  <td className="px-4 py-4 text-sm font-semibold">{candidate.rank ?? "—"}</td>
                  <td className="px-4 py-4">
                    <p className="max-w-72 truncate text-sm font-semibold text-ink">{names[candidate.doc_id] ?? candidate.file}</p>
                    <p className="mt-0.5 max-w-72 truncate text-xs text-ink-faint">
                      {candidate.file}
                      {candidate.human_review_required ? " · review required" : ""}
                    </p>
                  </td>
                  <td className="whitespace-nowrap px-4 py-4">
                    <span className="text-lg font-semibold text-ink">{candidate.score === null ? "—" : candidate.score.toFixed(1)}</span>
                    {candidate.score !== null && <span className="text-xs text-ink-faint"> / 100</span>}
                  </td>
                  <td className="px-4 py-4"><MiniBreakdown candidate={candidate} /></td>
                  <td className="px-4 py-4"><ConfidenceBadge confidence={candidate.confidence} /></td>
                  <td className="px-4 py-4"><ParseQualityBadge quality={candidate.parse_quality} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function MiniBreakdown({ candidate }: { candidate: ScoredCandidate }) {
  if (!candidate.breakdown) return <span className="text-xs text-ink-faint">{candidate.error || "No score details"}</span>;
  const tones = ["bg-lavender", "bg-mint", "bg-peach", "bg-amber", "bg-rose"];
  return (
    <div className="space-y-1.5" aria-label="Score component bars">
      {Object.entries(candidate.breakdown).map(([key, component], index) => {
        const width = component.max_points ? Math.max(0, Math.min(100, component.points / component.max_points * 100)) : 0;
        return (
          <div key={key} className="flex items-center gap-2" title={`${formatLabel(key)}: ${component.points}/${component.max_points}`}>
            <span className="w-20 truncate text-[11px] text-ink-faint">{formatLabel(key)}</span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-black/[0.06]">
              <div className={`h-full rounded-full ${tones[index % tones.length]}`} style={{ width: `${width}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ExplanationDrawer({ candidate, name, onClose }: { candidate: ScoredCandidate | null; name: string; onClose: () => void }) {
  return (
    <Drawer open={Boolean(candidate)} onClose={onClose} title={name || "Candidate explanation"} widthClassName="max-w-2xl">
      {candidate && (
        <div className="space-y-7">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-3xl font-semibold">{candidate.score === null ? "—" : candidate.score.toFixed(1)}</span>
            <span className="text-sm text-ink-faint">/ 100</span>
            <ConfidenceBadge confidence={candidate.confidence} />
            <ParseQualityBadge quality={candidate.parse_quality} />
            <Link to={`/resumes/${candidate.doc_id}`} className="ml-auto text-sm font-semibold text-lavender-ink hover:underline">View resume</Link>
          </div>

          {candidate.error && <ErrorNotice message={candidate.error} />}

          <section>
            <h3 className="text-lg font-medium">Why this score</h3>
            {candidate.reasoning_bullets.length ? (
              <ul className="mt-3 space-y-2">
                {candidate.reasoning_bullets.map((reason, index) => (
                  <li key={index} className="flex gap-3 rounded-lg bg-lavender-soft/55 px-3.5 py-3 text-sm leading-relaxed text-ink-soft">
                    <Sparkles size={15} className="mt-0.5 shrink-0 text-lavender-ink" />
                    {reason}
                  </li>
                ))}
              </ul>
            ) : <p className="mt-2 text-sm text-ink-faint">No reasoning bullets were produced.</p>}
          </section>

          <section>
            <h3 className="text-lg font-medium">Component breakdown</h3>
            {candidate.breakdown ? (
              <div className="mt-3 space-y-4">
                {Object.entries(candidate.breakdown).map(([key, component]) => (
                  <div key={key}>
                    <div className="flex items-center justify-between gap-3 text-sm">
                      <span className="font-semibold">{formatLabel(key)}</span>
                      <span className="text-ink-soft">{component.points} / {component.max_points}</span>
                    </div>
                    <div className="mt-2 h-2 overflow-hidden rounded-full bg-black/[0.06]">
                      <div
                        className={component.source === "python" ? "h-full rounded-full bg-mint" : "h-full rounded-full bg-peach"}
                        style={{ width: `${component.max_points ? component.points / component.max_points * 100 : 0}%` }}
                      />
                    </div>
                    <div className="mt-2 flex items-start gap-2">
                      <Pill tone={component.source === "python" ? "mint" : "peach"}>{component.source === "python" ? "Python computed" : "LLM assessed"}</Pill>
                    </div>
                    <p className="mt-2 text-sm leading-relaxed text-ink-soft">{component.detail}</p>
                  </div>
                ))}
              </div>
            ) : <p className="mt-2 text-sm text-ink-faint">No component data is available.</p>}
          </section>

          <SkillMatches title="Required skills" matches={candidate.required_skill_matches} />
          <SkillMatches title="Preferred skills" matches={candidate.preferred_skill_matches} />

          {candidate.anomalies.length > 0 && (
            <section>
              <h3 className="flex items-center gap-2 text-lg font-medium"><FileWarning size={18} /> Parse flags</h3>
              <ul className="mt-3 space-y-2">
                {candidate.anomalies.map((anomaly, index) => (
                  <li key={index} className="break-words rounded-lg bg-amber-soft px-3 py-2.5 text-sm text-amber-ink">{anomaly}</li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
    </Drawer>
  );
}

function SkillMatches({ title, matches }: { title: string; matches: ScoredCandidate["required_skill_matches"] }) {
  return (
    <section>
      <h3 className="text-lg font-medium">{title}</h3>
      {matches.length ? (
        <div className="mt-3 space-y-2">
          {matches.map((match) => (
            <details key={match.jd_skill} className="rounded-lg border border-border-soft">
              <summary className="flex cursor-pointer list-none items-center gap-2 px-3.5 py-3">
                <span className="min-w-0 flex-1 text-sm font-semibold">{match.jd_skill}</span>
                <TierBadge tier={match.tier} />
              </summary>
              <div className="border-t border-border-soft px-3.5 py-3 text-sm text-ink-soft">
                <p>{match.matched_against ? <>Matched <strong className="text-ink">{match.matched_against}</strong></> : "No matching resume skill found."}</p>
                {match.evidence && <blockquote className="mt-2 border-l-2 border-lavender pl-3 leading-relaxed">{match.evidence}</blockquote>}
                {match.note && <p className="mt-2 text-xs text-ink-faint">{match.note}</p>}
              </div>
            </details>
          ))}
        </div>
      ) : <p className="mt-2 text-sm text-ink-faint">No skill match data is available.</p>}
    </section>
  );
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  route?: ChatResponse["route_taken"];
}

function CandidateChatPanel({ jdId, role }: { jdId: string; role: string }) {
  const storageKey = `sift-chat:${jdId}`;
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(storageKey) || "[]") as ChatMessage[];
    } catch {
      return [];
    }
  });
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [chatError, setChatError] = useState("");

  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(messages));
    } catch {
      // Chat still works when storage is unavailable.
    }
  }, [messages, storageKey]);

  const send = async (event: React.FormEvent) => {
    event.preventDefault();
    const text = draft.trim();
    if (!text || loading) return;
    const userMessage: ChatMessage = { role: "user", content: text };
    const history = messages.map(({ role: messageRole, content }) => ({ role: messageRole, content }));
    setMessages((current) => [...current, userMessage]);
    setDraft("");
    setLoading(true);
    setChatError("");
    try {
      const response = await api.chat.send(jdId, text, history);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: response.answer,
          sources: response.sources,
          route: response.route_taken,
        },
      ]);
    } catch (err) {
      setChatError(err instanceof Error ? err.message : "Could not send the message.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-[min(620px,calc(100vh-220px))] min-h-[440px] flex-col px-4 py-4">
        <div className="mb-3 flex items-center justify-between">
          <p className="truncate text-xs font-extrabold text-ink-faint">{role} pool</p>
          {messages.length > 0 && (
            <button
              type="button"
              onClick={() => {
                setMessages([]);
                setChatError("");
              }}
              className="inline-flex items-center gap-1.5 text-xs font-bold text-ink-faint hover:text-rose-ink"
            >
              <Trash2 size={14} /> Clear
            </button>
          )}
        </div>
        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pb-4">
          {!messages.length && (
            <div className="flex min-h-64 flex-col items-center justify-center text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-peach-soft text-peach-ink">
                <BotMessageSquare size={23} />
              </div>
              <h3 className="mt-4 text-base font-extrabold">Ask about this pool</h3>
            </div>
          )}
          {messages.map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              className={message.role === "user" ? "ml-7 rounded-lg bg-ink px-3 py-2.5 text-xs leading-relaxed text-white" : "mr-2 rounded-lg bg-lavender-soft/65 px-3 py-2.5 text-xs leading-relaxed text-ink"}
            >
              <p className="whitespace-pre-wrap">{message.content}</p>
              {message.role === "assistant" && (
                <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-lavender/20 pt-2.5">
                  {message.route && <Pill tone="lavender">{message.route}</Pill>}
                  {message.sources?.map((source) => (
                    <Link
                      key={source.resume_id}
                      to={`/resumes/${source.resume_id}`}
                      className="rounded-full bg-surface-raised px-2.5 py-1 text-xs font-semibold text-lavender-ink hover:underline"
                    >
                      {source.name}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div className="mr-8 rounded-lg bg-lavender-soft/65 px-3 py-2.5">
              <ProgressNote label="Searching candidate evidence…" />
            </div>
          )}
          {chatError && <ErrorNotice message={chatError} />}
        </div>
        <form onSubmit={send} className="flex gap-2 border-t border-border-soft bg-surface-raised pt-3">
          <input
            aria-label="Message candidate chat"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Ask about candidates"
            maxLength={4000}
            className="h-10 min-w-0 flex-1 rounded-lg border border-border bg-surface px-3 text-xs outline-none placeholder:text-ink-faint focus:border-lavender"
          />
          <button
            type="submit"
            disabled={!draft.trim() || loading}
            aria-label="Send message"
            title="Send message"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-ink text-white hover:bg-ink-soft disabled:opacity-40"
          >
            <Send size={17} />
          </button>
        </form>
    </div>
  );
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
