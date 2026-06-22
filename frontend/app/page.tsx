"use client";

import { useMemo, useState } from "react";

type Message = {
  role: "user" | "assistant";
  text: string;
};

type VerifyResponse = {
  provider: "gemini" | "claude";
  prediction: {
    user_id: string;
    image_paths: string[];
    user_claim: string;
    claim_object: string;
    evidence_standard_met: boolean;
    evidence_standard_met_reason: string;
    risk_flags: string[];
    issue_type: string;
    object_part: string;
    claim_status: string;
    claim_status_justification: string;
    supporting_image_ids: string[];
    valid_image: boolean;
    severity: string;
  };
};

const defaultProvider = "gemini";

export default function HomePage() {
  const [userId, setUserId] = useState("");
  const [claimObject, setClaimObject] = useState("car");
  const [userClaim, setUserClaim] = useState("");
  const [imagePaths, setImagePaths] = useState("");
  const [provider, setProvider] = useState(defaultProvider);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const previewPaths = useMemo(
    () => imagePaths.split(";").map((p) => p.trim()).filter(Boolean),
    [imagePaths]
  );

  const addMessage = (message: Message) => {
    setMessages((prev) => [...prev, message]);
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);

    if (!userId || !claimObject || !userClaim || previewPaths.length === 0) {
      setError("Please fill all fields and provide at least one image path.");
      return;
    }

    const request = {
      user_id: userId,
      claim_object: claimObject,
      user_claim: userClaim,
      image_paths: previewPaths,
      provider,
    };

    addMessage({ role: "user", text: JSON.stringify(request, null, 2) });
    setIsLoading(true);

    try {
      const response = await fetch("http://localhost:8000/api/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const errorBody = await response.text();
        throw new Error(`API error ${response.status}: ${errorBody}`);
      }

      const result: VerifyResponse = await response.json();
      addMessage({
        role: "assistant",
        text: JSON.stringify(result, null, 2),
      });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="page-shell">
      <section className="hero">
        <h1>Orchestrate Claim Verifier</h1>
        <p>Submit claim details and image paths to verify visual evidence.</p>
      </section>

      <section className="form-card">
        <form onSubmit={handleSubmit}>
          <label>
            User ID
            <input
              value={userId}
              onChange={(event) => setUserId(event.target.value)}
              placeholder="test_user"
            />
          </label>

          <label>
            Claim Object
            <select
              value={claimObject}
              onChange={(event) => setClaimObject(event.target.value)}
            >
              <option value="car">car</option>
              <option value="laptop">laptop</option>
              <option value="package">package</option>
            </select>
          </label>

          <label>
            User Claim
            <textarea
              value={userClaim}
              onChange={(event) => setUserClaim(event.target.value)}
              rows={4}
            />
          </label>

          <label>
            Image Paths (semicolon-separated)
            <textarea
              value={imagePaths}
              onChange={(event) => setImagePaths(event.target.value)}
              rows={3}
            />
          </label>

          <label>
            Provider
            <select
              value={provider}
              onChange={(event) => setProvider(event.target.value)}
            >
              <option value="gemini">Gemini</option>
              <option value="claude">Claude</option>
            </select>
          </label>

          <button type="submit" disabled={isLoading}>
            {isLoading ? "Verifying…" : "Verify Claim"}
          </button>

          {error ? <p className="error">{error}</p> : null}
        </form>
      </section>

      <section className="chat-log">
        <h2>Conversation</h2>
        {messages.length === 0 ? (
          <p>No messages yet. Submit a claim to see the result.</p>
        ) : (
          <div className="messages">
            {messages.map((message, index) => (
              <div key={index} className={`message ${message.role}`}>
                <span className="message-role">{message.role}</span>
                <pre>{message.text}</pre>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
