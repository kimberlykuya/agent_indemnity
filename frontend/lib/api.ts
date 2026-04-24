const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const ARC_EXPLORER_TX_BASE_URL =
  process.env.NEXT_PUBLIC_ARC_EXPLORER_TX_BASE_URL || "https://explorer.arc.io/tx";

const parsedSlashPayout = Number(process.env.NEXT_PUBLIC_SLASH_PAYOUT_USDC ?? "1.0");
export const DEFAULT_SLASH_PAYOUT_USDC =
  Number.isFinite(parsedSlashPayout) && parsedSlashPayout > 0 ? parsedSlashPayout : 1.0;

export type ChatResponse = {
  reply: string;
  model: string;
  route_category: string;
  price_usdc: number;
  payment_status: string;
  bond_balance?: number;
  flagged: boolean;
  payment_ref?: string;
  anomaly_reason?: string | null;
  latency_ms?: number;
  timestamp?: string | number;
};

export type TransactionRecord = {
  type: "request_paid" | "bond_slashed" | "bond_topped_up" | "anomaly_flagged";
  amount: number;
  timestamp: string;
  model?: string | null;
  route_category?: string | null;
  status?: string | null;
  payment_ref?: string | null;
  tx_hash?: string | null;
  victim_address?: string | null;
  flagged?: boolean | null;
};

export type BondStatusResponse = {
  balance: number;
  state: string;
  total_paid_requests: number;
};

export async function sendChatMessage(message: string): Promise<ChatResponse> {
  const response = await fetch(`${API_URL}/agent/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, user_id: "demo_user" }),
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
      // Ignore invalid error payloads and fall back to status text.
    }
    throw new Error(message);
  }

  return response.json();
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

export async function slashBond(): Promise<{ success: boolean; hash: string }> {
  // Use the actual backend endpoint and hardcoded victim from the .env or fallback
  const response = await fetch(`${API_URL}/bond/slash`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      victim_address: "0x191cc4e34e54444b9e10f4e3311c87382b0c0654", // Demo victim address
      payout_amount: DEFAULT_SLASH_PAYOUT_USDC,
    }),
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.statusText}`);
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
