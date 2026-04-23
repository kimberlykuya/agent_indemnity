const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type ChatResponse = {
  reply: string;
  model: string;
  route_category: string;
  price_usdc: number;
  payment_status: string;
  flagged: boolean;
  payment_ref?: string;
  timestamp?: string;
};

export async function sendChatMessage(message: string): Promise<ChatResponse> {
  const response = await fetch(`${API_URL}/agent/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, user_id: "demo_user" }),
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.statusText}`);
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
      payout_amount: 500.0,
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
