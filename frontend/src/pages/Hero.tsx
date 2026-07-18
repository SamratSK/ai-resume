import { motion, type Variants } from "framer-motion";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  BadgeCheck,
  BriefcaseBusiness,
  FileSearch,
  Files,
  Quote,
  Sparkles,
} from "lucide-react";

const container: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06, delayChildren: 0.05 } },
};

const item: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.34, ease: [0.2, 0.8, 0.2, 1] as const } },
};

export function Hero() {
  return (
    <main className="overflow-hidden">
      <section className="relative mx-auto max-w-6xl px-5 pb-12 pt-14 sm:px-6 sm:pb-16 sm:pt-20">
        <div className="absolute right-6 top-10 hidden rotate-6 rounded-lg border-2 border-ink bg-amber px-3 py-2 text-xs font-extrabold text-ink shadow-[4px_4px_0_var(--color-ink)] lg:block">
          No mystery scores
        </div>

        <motion.div variants={container} initial="hidden" animate="show" className="mx-auto max-w-4xl text-center">
          <motion.div variants={item} className="inline-flex items-center gap-2 rounded-full border border-lavender/30 bg-lavender-soft px-3.5 py-2 text-xs font-extrabold text-lavender-ink">
            <Sparkles size={14} />
            Shortlisting, with receipts
          </motion.div>

          <motion.h1 variants={item} className="mt-5 text-6xl font-black leading-none text-ink sm:text-7xl">
            Sift<span className="text-peach">.</span>
          </motion.h1>

          <motion.p variants={item} className="mx-auto mt-5 max-w-2xl text-lg font-medium leading-relaxed text-ink-soft">
            Find the right candidates without losing the human context. Every score stays connected to the resume evidence behind it.
          </motion.p>

          <motion.div variants={item} className="mt-7 flex flex-wrap justify-center gap-3">
            <Link
              to="/jds"
              className="inline-flex min-h-12 items-center gap-2 rounded-lg bg-ink px-5 text-sm font-extrabold text-white shadow-[0_4px_0_oklch(15%_0.04_274)] transition-transform hover:-translate-y-1"
            >
              <BriefcaseBusiness size={17} /> Open job descriptions <ArrowRight size={16} />
            </Link>
            <Link
              to="/resumes"
              className="inline-flex min-h-12 items-center gap-2 rounded-lg border-2 border-ink bg-mint-soft px-5 text-sm font-extrabold text-mint-ink shadow-[0_4px_0_var(--color-mint)] transition-transform hover:-translate-y-1"
            >
              <Files size={17} /> Browse resumes
            </Link>
          </motion.div>
        </motion.div>

        <motion.div
          variants={item}
          initial="hidden"
          animate="show"
          className="relative mx-auto mt-12 max-w-5xl"
        >
          <div className="grid overflow-hidden rounded-lg border-2 border-ink bg-surface-raised shadow-[8px_8px_0_var(--color-lavender)] md:grid-cols-[1fr_0.85fr_1fr]">
            <FlowPanel tone="peach" icon={<Files size={18} />} label="Resume">
              <div className="space-y-2">
                <Line width="72%" color="bg-ink" />
                <Line width="92%" color="bg-peach" />
                <Line width="56%" color="bg-mint" />
              </div>
              <div className="mt-4 flex gap-1.5">
                <MiniPill label="Python" tone="bg-lavender-soft text-lavender-ink" />
                <MiniPill label="FastAPI" tone="bg-mint-soft text-mint-ink" />
              </div>
            </FlowPanel>

            <div className="relative flex min-h-44 items-center justify-center border-y-2 border-ink bg-amber-soft p-6 md:border-x-2 md:border-y-0">
              <motion.div
                className="absolute left-0 top-0 h-1.5 w-full origin-left bg-peach md:left-0 md:top-0"
                animate={{ scaleX: [0, 1, 1], opacity: [0.4, 1, 0.4] }}
                transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
              />
              <motion.div
                animate={{ rotate: [-3, 3, -3], y: [0, -4, 0] }}
                transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
                className="flex h-20 w-20 items-center justify-center rounded-lg border-2 border-ink bg-amber text-ink shadow-[4px_4px_0_var(--color-ink)]"
              >
                <FileSearch size={31} strokeWidth={2.3} />
              </motion.div>
              <span className="absolute bottom-5 text-xs font-extrabold text-amber-ink">Evidence check</span>
            </div>

            <FlowPanel tone="lavender" icon={<BadgeCheck size={18} />} label="Shortlist">
              <Candidate rank="1" name="Priya" score="91" tone="bg-mint-soft" />
              <Candidate rank="2" name="Ananya" score="86" tone="bg-lavender-soft" />
              <Candidate rank="3" name="Rohit" score="79" tone="bg-peach-soft" />
            </FlowPanel>
          </div>
        </motion.div>
      </section>

      <section className="border-y border-border bg-surface-raised/75">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-5 py-7 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-peach-soft text-peach-ink"><Quote size={18} /></span>
            <p className="max-w-xl text-sm font-semibold leading-relaxed text-ink-soft">A shortlist should start a conversation, not end one.</p>
          </div>
          <Link to="/resumes" className="inline-flex items-center gap-1.5 text-sm font-extrabold text-lavender-ink hover:underline">
            Inspect the evidence <ArrowRight size={15} />
          </Link>
        </div>
      </section>
    </main>
  );
}

function FlowPanel({
  icon,
  label,
  children,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
  tone: "peach" | "lavender";
}) {
  return (
    <div className={`min-h-52 p-5 sm:p-6 ${tone === "peach" ? "bg-peach-soft/45" : "bg-lavender-soft/45"}`}>
      <div className="mb-5 flex items-center gap-2 text-sm font-extrabold text-ink">
        <span className={tone === "peach" ? "text-peach-ink" : "text-lavender-ink"}>{icon}</span>
        {label}
      </div>
      {children}
    </div>
  );
}

function Line({ width, color }: { width: string; color: string }) {
  return <div className={`h-2 rounded-full ${color} opacity-55`} style={{ width }} />;
}

function MiniPill({ label, tone }: { label: string; tone: string }) {
  return <span className={`rounded-full px-2.5 py-1 text-[11px] font-extrabold ${tone}`}>{label}</span>;
}

function Candidate({ rank, name, score, tone }: { rank: string; name: string; score: string; tone: string }) {
  return (
    <motion.div
      className={`mb-2 flex items-center gap-3 rounded-lg border border-border px-3 py-2 ${tone}`}
      animate={{ x: [0, 3, 0] }}
      transition={{ duration: 2.4, repeat: Infinity, delay: Number(rank) * 0.14 }}
    >
      <span className="text-xs font-black text-ink-faint">#{rank}</span>
      <span className="flex-1 text-sm font-extrabold text-ink">{name}</span>
      <span className="text-xs font-black text-ink">{score}</span>
    </motion.div>
  );
}
