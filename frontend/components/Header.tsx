import { ShieldIcon } from "./icons";

/** Full-width, centered page title (not boxed). */
export default function Header() {
  return (
    <header className="cd-title">
      <h1>
        <span className="cd-title-mark" aria-hidden>
          <ShieldIcon size={26} />
        </span>
        Orchestrate Claims Desk
      </h1>
      <p>Multi-modal damage-claim evidence review</p>
    </header>
  );
}
