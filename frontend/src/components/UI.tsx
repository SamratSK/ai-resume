import clsx from "clsx";
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";
import { AlertCircle } from "lucide-react";
import { Spinner } from "./Spinner";

const buttonTones = {
  primary: "bg-ink text-white shadow-[0_3px_0_oklch(16%_0.04_274)] hover:-translate-y-0.5 hover:bg-ink-soft",
  lavender: "bg-lavender-soft text-lavender-ink shadow-[0_3px_0_oklch(72%_0.14_285/0.3)] hover:-translate-y-0.5 hover:bg-lavender/35",
  danger: "bg-rose-soft text-rose-ink hover:bg-rose/25",
  ghost: "text-ink-soft hover:bg-black/5 hover:text-ink",
} as const;

export function Button({
  children,
  tone = "primary",
  busy = false,
  className,
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  tone?: keyof typeof buttonTones;
  busy?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      className={clsx(
        "inline-flex min-h-10 items-center justify-center gap-2 rounded-lg px-4 text-sm font-bold transition-all focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-lavender disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none",
        buttonTones[tone],
        className,
      )}
      disabled={disabled || busy}
      {...props}
    >
      {busy && <Spinner />}
      {children}
    </button>
  );
}

export function IconButton({
  label,
  className,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { label: string; children: ReactNode }) {
  return (
    <button
      aria-label={label}
      title={label}
      className={clsx(
        "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-ink-faint transition-colors hover:bg-black/5 hover:text-ink focus-visible:outline-2 focus-visible:outline-lavender",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export function TextInput({
  label,
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label?: string }) {
  const input = (
    <input
      className={clsx(
        "h-11 w-full rounded-lg border border-border bg-surface-raised px-3.5 text-sm text-ink outline-none transition-all placeholder:text-ink-faint focus:border-lavender focus:ring-3 focus:ring-lavender/10",
        className,
      )}
      {...props}
    />
  );
  if (!label) return input;
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-ink-soft">{label}</span>
      {input}
    </label>
  );
}

export function ErrorNotice({ message }: { message: string }) {
  return (
    <div role="alert" className="flex items-start gap-2 rounded-lg bg-rose-soft px-4 py-3 text-sm text-rose-ink">
      <AlertCircle size={16} className="mt-0.5 shrink-0" />
      <span>{message}</span>
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
      <div>
        {eyebrow && (
          <p className="mb-3 inline-flex items-center gap-2 rounded-full bg-peach-soft px-3 py-1.5 text-xs font-extrabold text-peach-ink">
            <span className="h-1.5 w-1.5 rounded-full bg-peach" />
            {eyebrow}
          </p>
        )}
        <h1 className="text-3xl font-extrabold text-ink sm:text-4xl">{title}</h1>
        {description && <p className="mt-2 max-w-2xl text-sm font-medium leading-relaxed text-ink-soft sm:text-base">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function PageLoader({ label }: { label: string }) {
  return (
    <div className="flex min-h-64 items-center justify-center gap-3 text-sm text-ink-soft">
      <Spinner className="h-5 w-5 text-lavender" />
      {label}
    </div>
  );
}
