import { useAgentStore } from '../store/useAgentStore';

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";

let socket: WebSocket | null = null;

export function connectSocket() {
  if (socket) return; // Already connected

  socket = new WebSocket(WS_URL);

  socket.onopen = () => {
    console.log("WebSocket connected to", WS_URL);
  };

  socket.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      if (payload.event === "request_paid") {
        const data = payload.data;
        useAgentStore.getState().addTransaction({
          type: "request_paid",
          amount: data.amount,
          timestamp: data.timestamp,
          model: data.model,
          route_category: data.route_category,
          status: data.payment_status,
          payment_ref: data.payment_ref,
          flagged: data.flagged,
        });
        if (typeof data.bond_balance === "number") {
          useAgentStore.getState().setBondBalance(data.bond_balance);
        }
      } else if (payload.event === "bond_slashed") {
        const data = payload.data;
        useAgentStore.getState().addTransaction({
          type: "bond_slashed",
          amount: data.payout,
          timestamp: data.timestamp,
          tx_hash: data.tx_hash,
          victim_address: data.victim_address,
        });
        useAgentStore.getState().setBondBalance(data.new_balance);
      }
    } catch (e) {
      console.error("Failed to parse WebSocket message", e);
    }
  };

  socket.onclose = () => {
    console.log("WebSocket disconnected");
    socket = null;
    // Basic reconnect
    setTimeout(() => {
      connectSocket();
    }, 5000);
  };
}

export function disconnectSocket() {
  if (socket) {
    socket.close();
    socket = null;
  }
}
