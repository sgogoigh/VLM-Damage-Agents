import { imageUrl } from "../lib/api";
import type { SampleCase } from "../lib/types";
import { ImageIcon } from "./icons";

interface Props {
  cases: SampleCase[];
  split: "sample" | "test";
  onSplit: (s: "sample" | "test") => void;
  onPick: (c: SampleCase) => void;
  loading: boolean;
}

export default function SamplePicker({ cases, split, onSplit, onPick, loading }: Props) {
  return (
    <aside className="cd-rail">
      <div className="cd-card cd-lib">
        <div className="cd-card-head">
          <ImageIcon size={17} />
          <h2>Case library</h2>
          <span className="cd-count mono">{loading ? "…" : `${cases.length}`}</span>
        </div>

        <div style={{ padding: "10px 12px 0" }}>
          <div className="cd-seg" role="tablist" aria-label="Case split">
            <button
              role="tab"
              aria-selected={split === "sample"}
              className={split === "sample" ? "is-active" : ""}
              onClick={() => onSplit("sample")}
            >
              labeled
            </button>
            <button
              role="tab"
              aria-selected={split === "test"}
              className={split === "test" ? "is-active" : ""}
              onClick={() => onSplit("test")}
            >
              test set
            </button>
          </div>
        </div>

        <div className="cd-caselist">
          {loading && <div className="cd-rail-empty">Loading cases…</div>}
          {!loading && cases.length === 0 && (
            <div className="cd-rail-empty">No cases found. Is the dataset mounted?</div>
          )}
          {cases.map((c) => (
            <button key={c.case_id} className="cd-case" onClick={() => onPick(c)}>
              {c.image_paths[0] ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  className="cd-case-thumb"
                  src={imageUrl(c.image_paths[0])}
                  alt={c.case_id}
                  loading="lazy"
                />
              ) : (
                <span className="cd-case-thumb" />
              )}
              <span className="cd-case-body">
                <span className="cd-case-top">
                  <span className="cd-case-id">{c.case_id}</span>
                  <span className="cd-case-obj">{c.claim_object}</span>
                </span>
                <span className="cd-case-claim">{c.user_claim}</span>
              </span>
            </button>
          ))}
        </div>
      </div>

      <div className="cd-card cd-tip">
        <b>How it works.</b> Pick a case to load its photos and conversation, then
        hit <b>Verify</b>. The model inspects each image, checks it against the
        claim, weighs user history, and returns a verdict with cited evidence.
      </div>
    </aside>
  );
}
