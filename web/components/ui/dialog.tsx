"use client";

import { useEffect, useRef } from "react";

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}

export function Dialog({ open, onClose, title, children }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      className="backdrop:bg-black/50 bg-[var(--surface-1)] text-[var(--text-primary)] text-left border border-[var(--surface-3)] rounded-lg shadow-xl p-0 w-full max-w-md"
    >
      <div className="px-5 py-4 border-b border-[var(--surface-3)] flex items-center justify-between">
        <h2 className="text-sm font-semibold">{title}</h2>
        <button
          type="button"
          onClick={onClose}
          className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)] text-lg leading-none"
          aria-label="Close"
        >
          &times;
        </button>
      </div>
      <div className="px-5 py-4 text-left">{children}</div>
    </dialog>
  );
}
