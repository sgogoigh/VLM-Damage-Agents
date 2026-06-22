import { useRef, useState } from "react";
import { imageUrl } from "../lib/api";
import type { ClaimObject } from "../lib/types";
import { OBJECT_ICON, SendIcon, ClipIcon } from "./icons";

const OBJECTS: ClaimObject[] = ["car", "laptop", "package"];

function idFromPath(p: string): string {
  const file = p.split("/").pop() || p;
  return file.replace(/\.[^.]+$/, "");
}

interface Props {
  claimObject: ClaimObject;
  onObject: (o: ClaimObject) => void;
  draft: string;
  onDraft: (s: string) => void;
  attachments: string[];
  onAddPath: (p: string) => void;
  onRemove: (p: string) => void;
  busy: boolean;
  onSend: () => void;
}

export default function Composer({
  claimObject,
  onObject,
  draft,
  onDraft,
  attachments,
  onAddPath,
  onRemove,
  busy,
  onSend,
}: Props) {
  const [showAdd, setShowAdd] = useState(false);
  const [path, setPath] = useState("");
  const taRef = useRef<HTMLTextAreaElement>(null);

  const canSend = !busy && draft.trim().length > 0 && attachments.length > 0;

  function grow() {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }

  function submitPath() {
    const clean = path.trim();
    if (clean) {
      onAddPath(clean);
      setPath("");
      setShowAdd(false);
    }
  }

  return (
    <div className="cd-composer">
      <div className="cd-objects" role="group" aria-label="What was damaged">
        {OBJECTS.map((o) => {
          const Icon = OBJECT_ICON[o];
          return (
            <button
              key={o}
              type="button"
              className={`cd-chip ${claimObject === o ? "is-active" : ""}`}
              aria-pressed={claimObject === o}
              onClick={() => onObject(o)}
            >
              <Icon size={17} />
              {o}
            </button>
          );
        })}
      </div>

      {attachments.length > 0 && (
        <div className="cd-tray">
          {attachments.map((p) => (
            <div key={p} className="cd-tray-item">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={imageUrl(p)}
                alt={idFromPath(p)}
                onError={(e) => {
                  (e.currentTarget.style.display = "none");
                }}
              />
              <button
                type="button"
                className="cd-tray-x"
                aria-label={`Remove ${idFromPath(p)}`}
                onClick={() => onRemove(p)}
              >
                ×
              </button>
              <span className="cd-tray-id">{idFromPath(p)}</span>
            </div>
          ))}
        </div>
      )}

      {showAdd && (
        <div className="cd-add-row">
          <input
            className="cd-path-input"
            placeholder="images/test/case_006/img_1.jpg"
            value={path}
            onChange={(e) => setPath(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), submitPath())}
            autoFocus
          />
          <button type="button" className="cd-send" onClick={submitPath} disabled={!path.trim()}>
            Attach
          </button>
        </div>
      )}

      <div className="cd-input-shell">
        <textarea
          ref={taRef}
          className="cd-textarea"
          placeholder="Describe what happened — e.g. “The rear bumper has a dent after parking.”"
          value={draft}
          rows={1}
          onChange={(e) => {
            onDraft(e.target.value);
            grow();
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (canSend) onSend();
            }
          }}
        />
        <button
          type="button"
          className="cd-icon-btn"
          title="Attach an image by dataset path"
          aria-label="Attach image by path"
          onClick={() => setShowAdd((v) => !v)}
        >
          <ClipIcon size={18} />
        </button>
        <button type="button" className="cd-send" onClick={onSend} disabled={!canSend}>
          <SendIcon size={17} />
          Verify
        </button>
      </div>

      {attachments.length === 0 && (
        <span className="cd-composer-error" style={{ color: "var(--faint)", fontWeight: 500 }}>
          Add at least one photo — load a case from the right, or attach by path with the clip.
        </span>
      )}
    </div>
  );
}
