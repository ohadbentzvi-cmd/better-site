import { clsx } from "clsx";
import { forwardRef, type SelectHTMLAttributes } from "react";

type SelectProps = SelectHTMLAttributes<HTMLSelectElement>;

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { className, children, ...rest },
  ref,
) {
  return (
    <select
      ref={ref}
      className={clsx(
        "h-9 px-3 text-sm rounded-md",
        "bg-white text-[var(--text-primary)]",
        "border border-[var(--surface-3)] hover:border-[var(--text-tertiary)]",
        "transition-colors duration-150",
        "disabled:bg-[var(--surface-2)] disabled:cursor-not-allowed",
        className,
      )}
      {...rest}
    >
      {children}
    </select>
  );
});
