import { AlertCircle, AlertTriangle, Info } from "lucide-react";

interface Issue {
  title?: string;
  message?: string;
  severity?: string;
  dimension?: string;
  [key: string]: unknown;
}

interface IssueListProps {
  issues: Issue[];
}

function severityIcon(severity?: string) {
  switch (severity) {
    case "critical":
    case "high":
      return (
        <AlertCircle
          size={14}
          className="text-[var(--danger)] shrink-0 mt-0.5"
          aria-hidden="true"
        />
      );
    case "medium":
    case "warning":
      return (
        <AlertTriangle
          size={14}
          className="text-[var(--warning)] shrink-0 mt-0.5"
          aria-hidden="true"
        />
      );
    default:
      return (
        <Info
          size={14}
          className="text-[var(--text-tertiary)] shrink-0 mt-0.5"
          aria-hidden="true"
        />
      );
  }
}

export function IssueList({ issues }: IssueListProps) {
  if (!issues.length) {
    return (
      <p className="text-sm text-[var(--text-tertiary)]">No issues flagged.</p>
    );
  }

  return (
    <ul className="space-y-2">
      {issues.map((issue, i) => (
        <li key={i} className="flex items-start gap-2 text-sm">
          {severityIcon(issue.severity)}
          <div className="min-w-0">
            <div className="text-[var(--text-primary)]">
              {issue.title || issue.message || "Issue"}
            </div>
            {issue.dimension ? (
              <div className="text-xs text-[var(--text-tertiary)] mt-0.5">
                {issue.dimension}
                {issue.severity ? ` · ${issue.severity}` : ""}
              </div>
            ) : null}
          </div>
        </li>
      ))}
    </ul>
  );
}
