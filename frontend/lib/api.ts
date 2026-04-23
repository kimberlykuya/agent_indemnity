// Mock data to simulate backend response
const MOCK_ROUTES = ["general", "technical", "legal_risk", "fallback_complex"];
const MOCK_MODELS: Record<string, string> = {
  general: "mistralai/Mistral-7B-Instruct-v0.3",
  technical: "mistralai/Mistral-7B-Instruct-v0.3",
  legal_risk: "mistralai/Mistral-7B-Instruct-v0.3",
  fallback_complex: "gemini-3.1-pro-preview",
};
const MOCK_PRICES: Record<string, number> = {
  general: 0.001,
  technical: 0.003,
  legal_risk: 0.005,
  fallback_complex: 0.010,
};

export type ChatResponse = {
  reply: string;
  model: string;
  route_category: string;
  route_confidence: number;
  price_usdc: number;
  payment_status: string;
  flagged: boolean;
  anomaly_reason: string | null;
  latency_ms: number;
};

export async function sendChatMessage(message: string): Promise<ChatResponse> {
  // Simulate network latency (200ms - 800ms)
  const latency = Math.floor(Math.random() * 600) + 200;
  await new Promise((resolve) => setTimeout(resolve, latency));

  // Mock routing logic based on keywords for demo purposes
  let route = "general";
  if (message.toLowerCase().includes("error") || message.toLowerCase().includes("bug")) {
    route = "technical";
  } else if (message.toLowerCase().includes("refund") || message.toLowerCase().includes("sue")) {
    route = "legal_risk";
  } else if (message.toLowerCase().includes("confused")) {
    route = "fallback_complex";
  }

  // Mock anomaly detection
  let flagged = false;
  let anomaly_reason = null;
  if (message.toLowerCase().includes("ignore previous") || message.toLowerCase().includes("bypass")) {
    flagged = true;
    anomaly_reason = "Jailbreak attempt detected";
  }

  return {
    reply: flagged 
      ? "I cannot process that request due to a security policy violation."
      : "Thank you for your message. This is a mocked response from the frontend.",
    model: MOCK_MODELS[route],
    route_category: route,
    route_confidence: 0.85,
    price_usdc: MOCK_PRICES[route],
    payment_status: flagged ? "flagged" : "priced",
    flagged,
    anomaly_reason,
    latency_ms: latency,
  };
}

export async function slashBond(): Promise<{ success: boolean; hash: string }> {
  // Simulate blockchain latency
  await new Promise((resolve) => setTimeout(resolve, 1500));
  return {
    success: true,
    hash: "0x" + Array(64).fill(0).map(() => Math.floor(Math.random() * 16).toString(16)).join(""),
  };
}
