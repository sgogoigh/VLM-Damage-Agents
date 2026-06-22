export type Provider = "gemini" | "claude";

export type ClaimObject = "car" | "laptop" | "package";

export type ClaimStatus = "supported" | "contradicted" | "not_enough_information";

export interface Prediction {
  user_id: string;
  image_paths: string[];
  user_claim: string;
  claim_object: string;
  evidence_standard_met: boolean;
  evidence_standard_met_reason: string;
  risk_flags: string[];
  issue_type: string;
  object_part: string;
  claim_status: ClaimStatus;
  claim_status_justification: string;
  supporting_image_ids: string[];
  valid_image: boolean;
  severity: "none" | "low" | "medium" | "high" | "unknown";
}

export interface VerifyResponse {
  provider: Provider;
  prediction: Prediction;
}

export interface VerifyRequest {
  user_id: string;
  claim_object: ClaimObject;
  user_claim: string;
  image_paths: string[];
  provider?: Provider;
}

export interface ProviderInfo {
  provider: Provider;
  model: string;
  mock: boolean;
  operational: boolean;
  is_default: boolean;
}

export interface ProvidersResponse {
  default_provider: Provider;
  providers: ProviderInfo[];
}

export interface HealthResponse {
  status: string;
  reference_data: { users: number; requirement_rules: number };
  config: Record<string, unknown>;
}

export interface SampleCase {
  case_id: string;
  split: "sample" | "test";
  user_id: string;
  claim_object: ClaimObject;
  user_claim: string;
  image_paths: string[];
  labeled: boolean;
  expected: Record<string, string> | null;
}

export interface SamplesResponse {
  split: string;
  count: number;
  cases: SampleCase[];
}

export type ChatMessage =
  | { id: string; kind: "text"; role: "agent" | "user"; text: string; thumbs?: string[] }
  | { id: string; kind: "typing"; label?: string }
  | {
      id: string;
      kind: "verdict";
      provider: Provider;
      prediction: Prediction;
      expected?: Record<string, string> | null;
    };
