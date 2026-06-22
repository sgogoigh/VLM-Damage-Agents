import { imageUrl } from "../lib/api";
import type { Prediction, Provider } from "../lib/types";
import { CheckIcon, CrossIcon, QuestionIcon } from "./icons";

interface Props {
  prediction: Prediction;
  provider: Provider;
  expected?: Record<string, string> | null;
}

const VERDICT = {
  supported: { cls: "v-supported", word: "Supported", Icon: CheckIcon },
  contradicted: { cls: "v-contradicted", word: "Contradicted", Icon: CrossIcon },
  not_enough_information: { cls: "v-nei", word: "Not enough info", Icon: QuestionIcon },
} as const;

const SEV_LEVEL: Record<string, number> = { none: 0, unknown: 0, low: 1, medium: 2, high: 3 };

function idFromPath(p: string): string {
  const file = p.split("/").pop() || p;
  return file.replace(/\.[^.]+$/, "");
}

function Field({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <div className="cd-field">
      <span className="cd-field-k">{k}</span>
      <span className="cd-field-v">{children}</span>
    </div>
  );
}

export default function VerdictDossier({ prediction: p, provider, expected }: Props) {
  const v = VERDICT[p.claim_status] ?? VERDICT.not_enough_information;
  const sev = SEV_LEVEL[p.severity] ?? 0;
  const supporting = new Set(p.supporting_image_ids);
  const flags = p.risk_flags.length ? p.risk_flags : ["none"];

  const diffRows = expected
    ? [
        { k: "status", exp: expected.claim_status, got: p.claim_status },
        { k: "issue", exp: expected.issue_type, got: p.issue_type },
        { k: "part", exp: expected.object_part, got: p.object_part },
        { k: "severity", exp: expected.severity, got: p.severity },
        {
          k: "evidence",
          exp: expected.evidence_standard_met,
          got: String(p.evidence_standard_met),
        },
      ].filter((r) => r.exp !== undefined)
    : [];

  return (
    <div className={`cd-dossier ${v.cls}`}>
      <div className="cd-dossier-top">
        <span className="cd-verdict-seal">
          <v.Icon size={26} />
        </span>
        <span className="cd-verdict-head">
          <span className="cd-verdict-label">Verdict</span>
          <span className="cd-verdict-word">{v.word}</span>
        </span>
        <span className="cd-verdict-meta">
          <span className={`cd-tag ${p.evidence_standard_met ? "is-ok" : "is-bad"}`}>
            {p.evidence_standard_met ? "evidence met" : "evidence short"}
          </span>
          <span className={`cd-tag ${p.valid_image ? "is-ok" : "is-bad"}`}>
            {p.valid_image ? "image usable" : "image unusable"}
          </span>
          <span className="cd-tag">{provider}</span>
        </span>
      </div>

      <div className="cd-dossier-grid">
        <Field k="Issue type">
          <span className="mono">{p.issue_type}</span>
        </Field>
        <Field k="Object part">
          <span className="mono">{p.object_part}</span>
        </Field>
        <Field k="Severity">
          <span className="cd-sev">
            {[1, 2, 3].map((n) => (
              <i key={n} className={n <= sev ? "on" : ""} />
            ))}
            <span>{p.severity}</span>
          </span>
        </Field>
        <Field k="Object">
          <span className="mono">{p.claim_object}</span>
        </Field>
      </div>

      <div className="cd-justify">
        <span className="cd-field-k">Why</span>
        {p.claim_status_justification || "—"}
      </div>

      <div className="cd-flags">
        <span className="cd-field-k" style={{ marginRight: 4 }}>
          Risk flags
        </span>
        {flags.map((f) => (
          <span key={f} className={`cd-flag ${f === "none" ? "is-none" : ""}`}>
            {f}
          </span>
        ))}
      </div>

      {p.image_paths.length > 0 && (
        <div className="cd-evidence">
          <span className="cd-field-k">
            Evidence{" "}
            {supporting.size > 0 && (
              <span style={{ color: "var(--ok)" }}>· {supporting.size} supporting</span>
            )}
          </span>
          <div className="cd-evidence-grid">
            {p.image_paths.map((path) => {
              const id = idFromPath(path);
              const isSupport = supporting.has(id);
              return (
                <figure key={path} className={`cd-ev ${isSupport ? "is-support" : ""}`}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={imageUrl(path)} alt={id} loading="lazy" />
                  <figcaption className="cd-ev-cap">
                    <span className="mono">{id}</span>
                    {isSupport && <span className="mono is-support">✓ cited</span>}
                  </figcaption>
                </figure>
              );
            })}
          </div>
        </div>
      )}

      {diffRows.length > 0 && (
        <div className="cd-diff">
          <span className="cd-field-k">Predicted vs. labeled (sample case)</span>
          <div className="cd-diff-rows">
            {diffRows.map((r) => {
              const match =
                (r.exp || "").trim().toLowerCase() === (r.got || "").trim().toLowerCase();
              return (
                <div key={r.k} className={`cd-diff-row ${match ? "match" : "miss"}`}>
                  <span className="k">{r.k}</span>
                  <span className="exp">exp: {r.exp}</span>
                  <span className="got">got: {r.got}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
