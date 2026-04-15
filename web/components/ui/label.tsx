import { clsx } from "clsx";
import type { LabelHTMLAttributes, ReactNode } from "react";

export function Label({
  children,
  className,
  ...rest
}: LabelHTMLAttributes<HTMLLabelElement> & { children: ReactNode }) {
  return (
    <label
      className={clsx(
        "block text-sm font-medium text-[var(--text-primary)]",
        className,
      )}
      {...rest}
    >
      {children}
    </label>
  );
}
