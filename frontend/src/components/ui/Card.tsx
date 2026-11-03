import { type ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
}

export function Card({ children, className = "" }: CardProps) {
  return (
    <article
      className={`rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900 ${className}`}
    >
      {children}
    </article>
  );
}

export function CardHeader({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <header className={`p-6 pb-0 ${className}`}>{children}</header>;
}

export function CardBody({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={`p-6 ${className}`}>{children}</div>;
}

export function CardTitle({
  children,
  as: Title = "h3",
}: {
  children: ReactNode;
  /**
   * Element used for the title. Standalone screens (the auth pages) pass
   * `h1` so every page keeps exactly one top-level heading.
   */
  as?: "h1" | "h2" | "h3";
}) {
  return (
    <Title className="text-base font-semibold text-slate-900 dark:text-slate-100">
      {children}
    </Title>
  );
}

export function CardDescription({ children }: { children: ReactNode }) {
  return (
    <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
      {children}
    </p>
  );
}
