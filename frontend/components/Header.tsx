import { ShieldIcon } from "./icons";
import type { ProvidersResponse, Provider, HealthResponse } from "../lib/types";

interface Props {
  health: HealthResponse | null;
  healthError: boolean;
  providers: ProvidersResponse | null;
  selected: Provider | undefined;
  onSelect: (p: Provider) => void;
}

export default function Header({ health, healthError, providers, selected, onSelect }: Props) {
  const live = !!health && !healthError;
  const statusLabel = healthError ? "offline" : live ? "live" : "connecting";

  return (
    <header className="cd-header">
      <div className="cd-brand">
        <span className="cd-mark">
          <ShieldIcon size={22} />
        </span>
        <span className="cd-brand-text">
          <h1>Orchestrate Claims Desk</h1>
          <span>Multi-modal evidence review</span>
        </span>
      </div>

      <div className="cd-header-spacer" />

      <div className="cd-header-tools">
        <span className="cd-pill" title={live ? "Backend reachable" : "Backend unreachable"}>
          <span className={`cd-dot ${live ? "is-live" : healthError ? "is-down" : ""}`} />
          {statusLabel}
        </span>

        {providers && selected && (
          <select
            className="cd-select"
            value={selected}
            onChange={(e) => onSelect(e.target.value as Provider)}
            aria-label="Verification provider"
          >
            {providers.providers.map((p) => (
              <option key={p.provider} value={p.provider}>
                {p.provider}
                {p.mock ? " · mock" : ""}
              </option>
            ))}
          </select>
        )}
      </div>
    </header>
  );
}
