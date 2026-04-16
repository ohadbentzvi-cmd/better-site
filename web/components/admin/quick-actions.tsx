"use client";

import { useState, useTransition } from "react";
import { Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { submitReviewAction } from "@/app/admin/actions";

const REASON_LABELS: Record<string, string> = {
  not_icp: "Wrong ICP (vertical / geo / size)",
  site_already_good: "Site is already good",
  site_broken_or_dead: "Site is broken or dead",
  duplicate_or_other: "Duplicate or other (requires note)",
};

interface QuickActionsProps {
  leadId: string;
  businessName: string;
}

export function QuickActions({ leadId, businessName }: QuickActionsProps) {
  const [showReject, setShowReject] = useState(false);
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<"approved" | "rejected" | null>(null);
  const [approvePending, startApprove] = useTransition();
  const [rejectPending, startReject] = useTransition();

  if (done) {
    return (
      <span
        className={`text-xs font-medium ${
          done === "approved"
            ? "text-[var(--success)]"
            : "text-[var(--danger)]"
        }`}
      >
        {done === "approved" ? "Approved" : "Rejected"}
      </span>
    );
  }

  function handleApprove() {
    startApprove(async () => {
      const result = await submitReviewAction({
        leadId,
        verdict: "approved",
        reason_code: null,
        note: null,
      });
      if (result?.error) {
        setError(result.error);
        return;
      }
      setDone("approved");
    });
  }

  const needsNote = reason === "duplicate_or_other";
  const rejectValid = reason && (!needsNote || note.trim().length > 0);

  function handleRejectSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!rejectValid) return;
    setError(null);
    startReject(async () => {
      const result = await submitReviewAction({
        leadId,
        verdict: "rejected",
        reason_code: reason,
        note: note.trim() || null,
      });
      if (result?.error) {
        setError(result.error);
        return;
      }
      setShowReject(false);
      setDone("rejected");
    });
  }

  return (
    <>
      <span className="inline-flex items-center gap-1">
        <button
          type="button"
          onClick={handleApprove}
          disabled={approvePending}
          title="Approve"
          className="inline-flex items-center justify-center w-7 h-7 rounded-md text-[var(--success)] hover:bg-[var(--success)]/10 transition-colors disabled:opacity-40"
        >
          <Check size={16} />
        </button>
        <button
          type="button"
          onClick={() => setShowReject(true)}
          title="Reject"
          className="inline-flex items-center justify-center w-7 h-7 rounded-md text-[var(--danger)] hover:bg-[var(--danger)]/10 transition-colors"
        >
          <X size={16} />
        </button>
      </span>

      <Dialog
        open={showReject}
        onClose={() => setShowReject(false)}
        title={`Reject — ${businessName}`}
      >
        <form onSubmit={handleRejectSubmit} className="space-y-4">
          <Field label="Reason" htmlFor={`reject-reason-${leadId}`}>
            <Select
              id={`reject-reason-${leadId}`}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              required
            >
              <option value="">Select a reason...</option>
              {Object.entries(REASON_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>

          {needsNote ? (
            <Field
              label="Note"
              htmlFor={`reject-note-${leadId}`}
              hint="Required — explain why"
            >
              <Textarea
                id={`reject-note-${leadId}`}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Explain..."
              />
            </Field>
          ) : null}

          {error ? (
            <p className="text-sm text-[var(--danger)]" role="alert">
              {error}
            </p>
          ) : null}

          <div className="flex items-center gap-2 justify-end">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setShowReject(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="danger"
              disabled={!rejectValid}
              loading={rejectPending}
            >
              Reject
            </Button>
          </div>
        </form>
      </Dialog>
    </>
  );
}
