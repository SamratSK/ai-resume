import clsx from "clsx";
import type { Confidence, ParseQuality, SkillTier } from "../lib/types";

const toneClasses = {
  mint: "bg-mint-soft text-mint-ink",
  amber: "bg-amber-soft text-amber-ink",
  rose: "bg-rose-soft text-rose-ink",
  lavender: "bg-lavender-soft text-lavender-ink",
  peach: "bg-peach-soft text-peach-ink",
  neutral: "bg-black/5 text-ink-soft",
} as const;

export function Pill({
  tone = "neutral",
  children,
  className,
}: {
  tone?: keyof typeof toneClasses;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold leading-none",
        toneClasses[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

const parseQualityTone: Record<ParseQuality, keyof typeof toneClasses> = {
  Clean: "mint",
  Partial: "amber",
  Failed: "rose",
};

export function ParseQualityBadge({ quality }: { quality: ParseQuality }) {
  return <Pill tone={parseQualityTone[quality]}>{quality}</Pill>;
}

const confidenceTone: Record<string, keyof typeof toneClasses> = {
  High: "mint",
  Medium: "amber",
  Low: "rose",
};

export function ConfidenceBadge({ confidence }: { confidence: "High" | "Medium" | "Low" | null }) {
  if (!confidence) return <Pill tone="neutral">Unscored</Pill>;
  return <Pill tone={confidenceTone[confidence]}>{confidence}</Pill>;
}

export function FieldConfidenceBadge({ confidence }: { confidence: Confidence | null }) {
  if (!confidence) return <Pill tone="neutral">—</Pill>;
  const tone = confidence === "high" ? "mint" : confidence === "medium" ? "amber" : "rose";
  return <Pill tone={tone}>{confidence}</Pill>;
}

const tierTone: Record<SkillTier, keyof typeof toneClasses> = {
  exact: "mint",
  synonym: "mint",
  partial: "amber",
  implicit: "peach",
  missing: "neutral",
};

export function TierBadge({ tier }: { tier: SkillTier }) {
  return <Pill tone={tierTone[tier]}>{tier}</Pill>;
}
