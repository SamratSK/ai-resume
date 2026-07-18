import { NavLink } from "react-router-dom";
import clsx from "clsx";
import { BriefcaseBusiness, Files, Sparkles } from "lucide-react";

const links = [
  { to: "/jds", label: "Job Descriptions", icon: BriefcaseBusiness },
  { to: "/resumes", label: "Resumes", icon: Files },
];

export function NavBar() {
  return (
    <header className="sticky top-0 z-[var(--z-sticky)] border-b border-border bg-surface/90 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
        <NavLink to="/" className="group flex items-center gap-2.5">
          <span className="relative flex h-9 w-9 items-center justify-center rounded-lg bg-amber text-ink shadow-[3px_3px_0_var(--color-lavender)] transition-transform group-hover:-rotate-3">
            <Sparkles size={17} strokeWidth={2.5} />
          </span>
          <span className="text-lg font-extrabold text-ink">Sift</span>
        </NavLink>
        <nav className="flex items-center gap-1">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                clsx(
                  "flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-xs font-bold transition-colors sm:px-3.5 sm:text-sm",
                  isActive ? "bg-lavender-soft text-lavender-ink" : "text-ink-soft hover:bg-mint-soft hover:text-mint-ink",
                )
              }
            >
              <link.icon size={15} />
              <span className="sm:hidden">{link.label === "Job Descriptions" ? "JDs" : link.label}</span>
              <span className="hidden sm:inline">{link.label}</span>
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  );
}
