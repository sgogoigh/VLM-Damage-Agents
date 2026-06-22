import { imageUrl } from "../lib/api";
import type { ChatMessage } from "../lib/types";
import { SparkIcon } from "./icons";
import VerdictDossier from "./VerdictDossier";

/** Render a single chat row: agent/user text, the typing indicator, or a verdict. */
export default function MessageBubble({ msg }: { msg: ChatMessage }) {
  if (msg.kind === "verdict") {
    return (
      <div className="cd-row is-agent is-wide">
        <span className="cd-avatar is-agent" aria-hidden>
          <SparkIcon size={16} />
        </span>
        <VerdictDossier
          prediction={msg.prediction}
          provider={msg.provider}
          expected={msg.expected}
        />
      </div>
    );
  }

  if (msg.kind === "typing") {
    return (
      <div className="cd-row is-agent">
        <span className="cd-avatar is-agent" aria-hidden>
          <SparkIcon size={16} />
        </span>
        <div className="cd-bubble cd-typing" role="status" aria-label="Reviewing evidence">
          <i /><i /><i />
          {msg.label && <span className="cd-typing-label">{msg.label}</span>}
        </div>
      </div>
    );
  }

  const isAgent = msg.role === "agent";
  return (
    <div className={`cd-row ${isAgent ? "is-agent" : "is-user"}`}>
      <span className={`cd-avatar ${isAgent ? "is-agent" : "is-user"}`} aria-hidden>
        {isAgent ? <SparkIcon size={16} /> : "you"}
      </span>
      <div className="cd-bubble">
        {msg.text.split("\n\n").map((para, i) => (
          <p key={i}>{para}</p>
        ))}
        {msg.thumbs && msg.thumbs.length > 0 && (
          <div className="cd-bubble-thumbs">
            {msg.thumbs.map((path) => (
              // eslint-disable-next-line @next/next/no-img-element
              <img key={path} src={imageUrl(path)} alt="attached evidence" loading="lazy" />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
