import React, { useEffect } from "react";

const ConfirmDialog = ({
  open,
  title,
  message,
  confirmText = "Confirm",
  cancelText = "Cancel",
  danger = false,
  busy = false,
  onConfirm,
  onCancel,
}) => {
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e) => {
      if (e.key === "Escape") onCancel?.();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onCancel}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title || "Confirm"}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <div className="modal-title">{title || "Confirm"}</div>
          <button className="icon-btn" type="button" onClick={onCancel} aria-label="Close dialog">
            ✕
          </button>
        </div>
        {message && <div className="modal-body">{message}</div>}
        <div className="modal-actions">
          <button className="button ghost" type="button" onClick={onCancel} disabled={busy}>
            {cancelText}
          </button>
          <button
            className={`button ${danger ? "danger" : ""}`}
            type="button"
            onClick={onConfirm}
            disabled={busy}
          >
            {busy ? "Working..." : confirmText}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConfirmDialog;
