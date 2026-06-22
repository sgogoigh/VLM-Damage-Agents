import type { HealthResponse, Provider, ProvidersResponse } from "../lib/types";
import { RefreshIcon } from "./icons";

interface Props {
  health: HealthResponse | null;
  healthError: boolean;
  checking: boolean;
  onRecheck: () => void;
  providers: ProvidersResponse | null;
  selected: Provider | undefined;
  onSelect: (p: Provider) => void;
}

export default function StatusBar({
  health,
  healthError,
  checking,
  onRecheck,
  providers,
  selected,
  onSelect,
}: Props) {
  const live = !!health && !healthError;
  const label = checking ? "checking" : healthError ? "offline" : live ? "live" : "connecting";
  const model = providers?.providers.find((p) => p.provider === selected)?.model;

  return (
    <footer className="cd-statusbar">
      <button
        type="button"
        className={`cd-statusbtn ${live ? "is-live" : healthError ? "is-down" : ""}`}
        onClick={onRecheck}
        title="Backend connection — click to re-check"
      >
        <span className={`cd-dot ${live ? "is-live" : healthError ? "is-down" : ""}`} />
        backend · {label}
        <RefreshIcon size={13} className={checking ? "cd-spin" : ""} />
      </button>

      <span className="cd-statusbar-spacer" />

      {providers && selected && (
        <label className="cd-provider">
          <span>provider</span>
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
        </label>
      )}
      {model && <span className="cd-statusbar-model mono">{model}</span>}
    </footer>
  );
}
