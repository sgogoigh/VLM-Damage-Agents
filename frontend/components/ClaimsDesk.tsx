"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../lib/api";
import type {
  ChatMessage,
  ClaimObject,
  HealthResponse,
  Prediction,
  Provider,
  ProvidersResponse,
  SampleCase,
} from "../lib/types";
import ChatThread from "./ChatThread";
import Composer from "./Composer";
import Header from "./Header";
import SamplePicker from "./SamplePicker";
import { AlertIcon } from "./icons";

let _seq = 0;
const uid = () => `m${++_seq}`;

const GREETING: ChatMessage[] = [
  {
    id: uid(),
    kind: "text",
    role: "agent",
    text: "Hi — I'm your claims assistant. I review the photos behind a damage claim and tell you whether the evidence backs it up.",
  },
  {
    id: uid(),
    kind: "text",
    role: "agent",
    text: "Pick what was damaged, describe what happened, and attach a photo — then hit Verify. New here? Load a case from the library on the right to watch it work.",
  },
];

function summarize(p: Prediction): string {
  const review = p.risk_flags.includes("manual_review_required")
    ? " I've also flagged it for a manual review."
    : "";
  if (p.claim_status === "supported") {
    return `The photos back up the claim — I can see ${p.issue_type.replace(/_/g, " ")} on the ${p.object_part.replace(/_/g, " ")}.${review}`;
  }
  if (p.claim_status === "contradicted") {
    return `The photos don't support the claim. ${p.claim_status_justification}${review}`;
  }
  return `I can't confirm this from the photos alone — there isn't enough usable evidence.${review}`;
}

export default function ClaimsDesk() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState(false);
  const [providers, setProviders] = useState<ProvidersResponse | null>(null);
  const [provider, setProvider] = useState<Provider | undefined>(undefined);

  const [claimObject, setClaimObject] = useState<ClaimObject>("car");
  const [draft, setDraft] = useState("");
  const [attachments, setAttachments] = useState<string[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>(GREETING);
  const [busy, setBusy] = useState(false);
  const [banner, setBanner] = useState<string | null>(null);

  const [split, setSplit] = useState<"sample" | "test">("sample");
  const [cases, setCases] = useState<SampleCase[]>([]);
  const [casesLoading, setCasesLoading] = useState(true);

  const userIdRef = useRef<string>("web_guest");
  const expectedRef = useRef<Record<string, string> | null>(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealthError(true));
    api
      .providers()
      .then((p) => {
        setProviders(p);
        setProvider(p.default_provider);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    let alive = true;
    setCasesLoading(true);
    api
      .samples(split)
      .then((r) => alive && setCases(r.cases))
      .catch(() => alive && setCases([]))
      .finally(() => alive && setCasesLoading(false));
    return () => {
      alive = false;
    };
  }, [split]);

  const push = useCallback(
    (m: ChatMessage) => setMessages((prev) => [...prev, m]),
    []
  );

  const loadCase = useCallback(
    (c: SampleCase) => {
      setClaimObject(c.claim_object);
      setDraft(c.user_claim);
      setAttachments(c.image_paths);
      userIdRef.current = c.user_id || "web_guest";
      expectedRef.current = c.expected || null;
      push({
        id: uid(),
        kind: "text",
        role: "agent",
        text: `Loaded ${c.case_id}. The photos and conversation are staged below — hit Verify when you're ready.`,
      });
    },
    [push]
  );

  const addPath = useCallback(
    (p: string) => setAttachments((prev) => (prev.includes(p) ? prev : [...prev, p])),
    []
  );

  const removePath = useCallback((p: string) => {
    setAttachments((prev) => {
      const next = prev.filter((x) => x !== p);
      if (next.length === 0) expectedRef.current = null;
      return next;
    });
  }, []);

  const send = useCallback(async () => {
    const claim = draft.trim();
    if (!claim || attachments.length === 0 || busy) return;
    setBanner(null);

    const thumbs = [...attachments];
    const imagePaths = [...attachments];
    const expected = expectedRef.current;

    push({ id: uid(), kind: "text", role: "user", text: claim, thumbs });
    const typingId = uid();
    setMessages((prev) => [...prev, { id: typingId, kind: "typing", label: "reviewing evidence" }]);
    setBusy(true);

    try {
      const res = await api.verify({
        user_id: userIdRef.current,
        claim_object: claimObject,
        user_claim: claim,
        image_paths: imagePaths,
        provider,
      });
      setMessages((prev) => prev.filter((m) => m.id !== typingId));
      push({ id: uid(), kind: "text", role: "agent", text: summarize(res.prediction) });
      push({
        id: uid(),
        kind: "verdict",
        provider: res.provider,
        prediction: res.prediction,
        expected,
      });
    } catch (e) {
      setMessages((prev) => prev.filter((m) => m.id !== typingId));
      const msg =
        e instanceof ApiError ? e.message : "Something went wrong while verifying the claim.";
      push({ id: uid(), kind: "text", role: "agent", text: msg });
      setBanner(msg);
    } finally {
      setBusy(false);
      expectedRef.current = null;
    }
  }, [draft, attachments, busy, claimObject, provider, push]);

  const activeModel = providers?.providers.find((p) => p.provider === provider)?.model;

  return (
    <div className="cd-app">
      <Header
        health={health}
        healthError={healthError}
        providers={providers}
        selected={provider}
        onSelect={setProvider}
      />

      {banner && (
        <div className="cd-banner" role="alert">
          <AlertIcon size={18} />
          {banner}
        </div>
      )}

      <div className="cd-workspace">
        <main className="cd-stage">
          <ChatThread messages={messages} />
          <Composer
            claimObject={claimObject}
            onObject={setClaimObject}
            draft={draft}
            onDraft={setDraft}
            attachments={attachments}
            onAddPath={addPath}
            onRemove={removePath}
            busy={busy}
            onSend={send}
          />
        </main>

        <SamplePicker
          cases={cases}
          split={split}
          onSplit={setSplit}
          onPick={loadCase}
          loading={casesLoading}
        />
      </div>

      <footer className="cd-foot">
        Orchestrate · evidence reviewed by{" "}
        <span className="mono" style={{ color: "var(--muted)" }}>
          {provider ?? "—"}
          {activeModel ? ` · ${activeModel}` : ""}
        </span>
      </footer>
    </div>
  );
}
