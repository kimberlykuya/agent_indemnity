const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const ARC_EXPLORER_TX_BASE_URL =
  process.env.NEXT_PUBLIC_ARC_EXPLORER_TX_BASE_URL || "https://testnet.arcscan.app/tx";

export type PaymentProof = {
  proof_token: string;
  payer_wallet_address: string;
  facilitator_tx_ref: string;
  payment_tx_hash?: string;
};

export type ChatResponse = {
  kind: "chat_response";
  reply: string;
  model: string;
  route_category: string;
  route_confidence?: number | null;
  price_usdc: number;
  payment_status: string;
  bond_balance?: number;
  flagged: boolean;
  payment_ref: string;
  anomaly_reason?: string | null;
  slash_executed?: boolean;
  slash_tx_hash?: string | null;
  slash_payout?: number | null;
  slash_victim_address?: string | null;
  payer_wallet_address: string;
  beneficiary_wallet_address: string;
  anomaly_signal: "none" | "rule" | "embedding" | "rule+embedding";
  slash_mode: "none" | "auto" | "manual";
  slash_error?: string | null;
  latency_ms?: number;
  timestamp?: string | number;
};

export type PaymentChallengeResponse = {
  kind: "payment_required";
  message: string;
  route_category: string;
  route_confidence?: number | null;
  price_usdc: number;
  payment_challenge_token: string;
  expires_at: string;
  payment_network: string;
  facilitator_url?: string | null;
  payment_instructions: Record<string, unknown>;
};

export type SendChatResult = ChatResponse | PaymentChallengeResponse;

export type TransactionRecord = {
  type: "request_paid" | "bond_slashed" | "bond_topped_up" | "anomaly_flagged";
  amount: number;
  timestamp: string;
  bond_balance_after?: number | null;
  model?: string | null;
  route_category?: string | null;
  status?: string | null;
  payment_ref?: string | null;
  tx_hash?: string | null;
  victim_address?: string | null;
  beneficiary_wallet_address?: string | null;
  payer_wallet_address?: string | null;
  anomaly_reason?: string | null;
  anomaly_signal?: "none" | "rule" | "embedding" | "rule+embedding" | null;
  slash_mode?: "none" | "auto" | "manual" | null;
  flagged?: boolean | null;
  prompt?: string | null;
  reply?: string | null;
};

export type BondStatusResponse = {
  balance: number;
  state: string;
  total_paid_requests: number;
  alert_floor_usdc: number;
  is_below_alert_floor: boolean;
  warning_message?: string | null;
};

type SendChatMessageInput = {
  message: string;
  userId: string;
  userWalletAddress: string;
  paymentChallengeToken?: string;
  paymentProof?: PaymentProof;
  signal?: AbortSignal;
};

export async function sendChatMessage({
  message,
  userId,
  userWalletAddress,
  paymentChallengeToken,
  paymentProof,
  signal,
}: SendChatMessageInput): Promise<SendChatResult> {
  const response = await fetch(`${API_URL}/agent/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      user_id: userId,
      user_wallet_address: userWalletAddress,
      payment_challenge_token: paymentChallengeToken,
      payment_proof: paymentProof,
    }),
    signal,
  });

  if (response.status === 402) {
    const payload = (await response.json()) as Omit<PaymentChallengeResponse, "kind"> & { kind?: "payment_required" };
    return {
      kind: "payment_required",
      ...payload,
    };
  }

  if (!response.ok) {
    let message = `API error: ${response.statusText}`;
    try {
      const payload = await response.json();
      const detail = payload?.detail?.message;
      if (typeof detail === "string" && detail.trim()) {
        message = detail;
      }
    } catch {
      // Ignore invalid error payloads and fall back to status text.
    }
    throw new Error(message);
  }

  const payload = (await response.json()) as Omit<ChatResponse, "kind">;
  return {
    kind: "chat_response",
    ...payload,
  };
}

export async function getTransactions(): Promise<TransactionRecord[]> {
  const response = await fetch(`${API_URL}/transactions`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Failed to load transactions: ${response.statusText}`);
  }

  return response.json();
}

export async function getBondStatus(): Promise<BondStatusResponse> {
  const response = await fetch(`${API_URL}/bond/status`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Failed to load bond status: ${response.statusText}`);
  }

  return response.json();
}

export async function slashBond(victimAddress: string): Promise<{ success: boolean; hash: string }> {
  const response = await fetch(`${API_URL}/bond/slash`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      victim_address: victimAddress,
      payout_amount: 0.01,
    }),
  });

  if (!response.ok) {
    let message = `API error: ${response.statusText}`;
    try {
      const payload = await response.json();
      const detail = payload?.detail?.message;
      if (typeof detail === "string" && detail.trim()) {
        message = detail;
      }
    } catch {
      // fall back to status text
    }
    throw new Error(message);
  }

  const data = await response.json();
  return {
    success: true,
    hash: data.tx_hash,
  };
}

export function getArcExplorerTxUrl(txHash: string): string {
  return `${ARC_EXPLORER_TX_BASE_URL.replace(/\/$/, "")}/${txHash}`;
}
