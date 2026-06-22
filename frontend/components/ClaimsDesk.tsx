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
import StatusBar from "./StatusBar";
import Toast from "./Toast";

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
    text: "Pick what was damaged, describe what happened, and add a photo (Browse to upload, or load a case on the right) — then hit Verify.",
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
  const [checking, setChecking] = useState(false);
  const [providers, setProviders] = useState<ProvidersResponse | null>(null);
  const [provider, setProvider] = useState<Provider | undefined>(undefined);

  const [claimObject, setClaimObject] = useState<ClaimObject>("car");
  const [draft, setDraft] = useState("");
  const [attachments, setAttachments] = useState<string[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>(GREETING);
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const [split, setSplit] = useState<"sample" | "test">("sample");
  const [cases, setCases] = useState<SampleCase[]>([]);
  const [casesLoading, setCasesLoading] = useState(true);

  const userIdRef = useRef<string>("web_guest");
  const expectedRef = useRef<Record<string, string> | null>(null);

  const checkHealth = useCallback(() => {
    setChecking(true);
    setHealthError(false);
    api
      .health()
      .then(setHealth)
      .catch(() => setHealthError(true))
      .finally(() => setChecking(false));
  }, []);

  useEffect(() => {
    checkHealth();
    api
      .providers()
      .then((p) => {
        setProviders(p);
        setProvider(p.default_provider);
      })
      .catch(() => {});
  }, [checkHealth]);

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

  const uploadAndAttach = useCallback(
    (files: File[]) => {
      setUploading(true);
      // A device upload is the user's own evidence — it has no labeled answer.
      expectedRef.current = null;
      api
        .uploadImages(files)
        .then((paths) => setAttachments((prev) => [...prev, ...paths.filter((p) => !prev.includes(p))]))
        .catch((e) => setToast(e instanceof ApiError ? e.message : "Couldn't upload that image."))
        .finally(() => setUploading(false));
    },
    []
  );

  const send = useCallback(async () => {
    const claim = draft.trim();
    if (!claim || attachments.length === 0 || busy) return;

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
      setToast(msg);
    } finally {
      setBusy(false);
      expectedRef.current = null;
    }
  }, [draft, attachments, busy, claimObject, provider, push]);

  return (
    <div className="cd-app">
      <Header />

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
            onUpload={uploadAndAttach}
            uploading={uploading}
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

      <StatusBar
        health={health}
        healthError={healthError}
        checking={checking}
        onRecheck={checkHealth}
        providers={providers}
        selected={provider}
        onSelect={setProvider}
      />

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
