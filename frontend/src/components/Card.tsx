import clsx from "clsx";

export function Card({
  children,
  className,
  as: As = "div",
  ...rest
}: {
  children: React.ReactNode;
  className?: string;
  as?: React.ElementType;
} & React.HTMLAttributes<HTMLElement>) {
  return (
    <As
      className={clsx(
        "rounded-lg border border-border bg-surface-raised shadow-[var(--shadow-soft)]",
        className,
      )}
      {...rest}
    >
      {children}
    </As>
  );
}
