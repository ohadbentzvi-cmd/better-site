import { clsx } from "clsx";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Spinner } from "./spinner";

type Variant = "primary" | "ghost" | "danger";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  loading?: boolean;
  children: ReactNode;
}

const variantClasses: Record<Variant, string> = {
  primary:
    "bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] disabled:bg-[var(--surface-3)] disabled:text-[var(--text-tertiary)]",
  ghost:
    "bg-transparent text-[var(--text-primary)] hover:bg-[var(--surface-2)] disabled:text-[var(--text-tertiary)]",
  danger:
    "bg-[var(--danger)] text-white hover:bg-red-800 disabled:bg-[var(--surface-3)] disabled:text-[var(--text-tertiary)]",
};

export function Button({
  variant = "primary",
  loading = false,
  disabled,
  className,
  children,
  type = "button",
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      className={clsx(
        "inline-flex items-center justify-center gap-2",
        "h-9 px-3 text-sm font-medium rounded-md",
        "transition-colors duration-150",
        "disabled:cursor-not-allowed",
        variantClasses[variant],
        className,
      )}
      {...rest}
    >
      {loading ? (
        <>
          <Spinner size={14} />
          <span>Working...</span>
        </>
      ) : (
        children
      )}
    </button>
  );
}
