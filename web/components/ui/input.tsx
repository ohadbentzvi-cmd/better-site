import { clsx } from "clsx";
import { forwardRef, type InputHTMLAttributes } from "react";

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  invalid?: boolean;
};

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, invalid, ...rest },
  ref,
) {
  return (
    <input
      ref={ref}
      aria-invalid={invalid || undefined}
      className={clsx(
        "h-9 w-full px-3 text-sm rounded-md",
        "bg-white text-[var(--text-primary)]",
        "border",
        invalid
          ? "border-[var(--danger)]"
          : "border-[var(--surface-3)] hover:border-[var(--text-tertiary)]",
        "placeholder:text-[var(--text-tertiary)]",
        "transition-colors duration-150",
        "disabled:bg-[var(--surface-2)] disabled:cursor-not-allowed",
        className,
      )}
      {...rest}
    />
  );
});
