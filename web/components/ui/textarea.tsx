import { clsx } from "clsx";
import { forwardRef, type TextareaHTMLAttributes } from "react";

type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  invalid?: boolean;
};

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  function Textarea({ className, invalid, rows = 4, ...rest }, ref) {
    return (
      <textarea
        ref={ref}
        rows={rows}
        aria-invalid={invalid || undefined}
        className={clsx(
          "w-full px-3 py-2 text-sm rounded-md",
          "bg-white text-[var(--text-primary)]",
          "border",
          invalid
            ? "border-[var(--danger)]"
            : "border-[var(--surface-3)] hover:border-[var(--text-tertiary)]",
          "placeholder:text-[var(--text-tertiary)]",
          "transition-colors duration-150",
          "resize-y",
          className,
        )}
        {...rest}
      />
    );
  },
);
