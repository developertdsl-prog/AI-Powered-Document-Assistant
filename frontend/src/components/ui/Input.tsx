import { type InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
}

export function Input({ label, hint, id, className = "", ...props }: InputProps) {
  const inputId = id ?? props.name;

  return (
    <label className="flex flex-col gap-2 text-sm" htmlFor={inputId}>
      {label ? (
        <span className="font-medium text-slate-700 dark:text-slate-200">
          {label}
        </span>
      ) : null}
      <input
        id={inputId}
        className={`w-full rounded-lg border border-slate-200 px-3 py-2 text-slate-900 shadow-sm placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:placeholder:text-slate-500 ${className}`}
        {...props}
      />
      {hint ? (
        <span className="text-xs text-slate-500 dark:text-slate-400">
          {hint}
        </span>
      ) : null}
    </label>
  );
}
