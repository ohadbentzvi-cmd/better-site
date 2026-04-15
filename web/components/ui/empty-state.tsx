import type { ReactNode } from "react";

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-12 px-4 text-center">
      {icon ? (
        <div className="text-[var(--text-tertiary)]" aria-hidden="true">
          {icon}
        </div>
      ) : null}
      <div className="text-base font-medium text-[var(--text-primary)]">
        {title}
      </div>
      {description ? (
        <p className="text-sm text-[var(--text-secondary)] max-w-sm">
          {description}
        </p>
      ) : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
