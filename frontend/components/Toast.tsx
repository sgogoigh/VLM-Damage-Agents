import { useEffect } from "react";
import { AlertIcon, CloseIcon } from "./icons";

interface Props {
  message: string;
  onClose: () => void;
  /** auto-dismiss delay in ms (default 5000) */
  duration?: number;
}

export default function Toast({ message, onClose, duration = 5000 }: Props) {
  useEffect(() => {
    const t = setTimeout(onClose, duration);
    return () => clearTimeout(t);
  }, [message, duration, onClose]);

  return (
    <div className="cd-toast" role="alert">
      <span className="cd-toast-icon">
        <AlertIcon size={18} />
      </span>
      <span className="cd-toast-msg">{message}</span>
      <button type="button" className="cd-toast-x" onClick={onClose} aria-label="Dismiss">
        <CloseIcon size={15} />
      </button>
      <span className="cd-toast-bar" style={{ animationDuration: `${duration}ms` }} />
    </div>
  );
}
