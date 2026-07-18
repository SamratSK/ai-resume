import { useState } from "react";
import { X } from "lucide-react";

export function ChipInput({
  label,
  values,
  onChange,
  placeholder,
  tone = "lavender",
}: {
  label: string;
  values: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
  tone?: "lavender" | "peach";
}) {
  const [draft, setDraft] = useState("");

  const commit = () => {
    const trimmed = draft.trim();
    if (trimmed && !values.includes(trimmed)) onChange([...values, trimmed]);
    setDraft("");
  };

  const chipTone = tone === "lavender" ? "bg-lavender-soft text-lavender-ink" : "bg-peach-soft text-peach-ink";

  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-ink-soft">{label}</label>
      <div className="flex flex-wrap items-center gap-1.5 rounded-lg border border-border bg-surface px-2.5 py-2 focus-within:border-lavender focus-within:ring-3 focus-within:ring-lavender/10">
        {values.map((v) => (
          <span key={v} className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${chipTone}`}>
            {v}
            <button
              type="button"
              onClick={() => onChange(values.filter((x) => x !== v))}
              aria-label={`Remove ${v}`}
              className="rounded-full hover:opacity-70"
            >
              <X size={12} />
            </button>
          </span>
        ))}
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault();
              commit();
            } else if (e.key === "Backspace" && !draft && values.length) {
              onChange(values.slice(0, -1));
            }
          }}
          onBlur={commit}
          placeholder={values.length ? "" : placeholder}
          className="min-w-[8ch] flex-1 bg-transparent py-0.5 text-sm outline-none placeholder:text-ink-faint"
        />
      </div>
      <p className="mt-1 text-xs text-ink-faint">Press Enter or comma to add. Use "X or Y" / "X/Y" for alternatives.</p>
    </div>
  );
}
