import { useAgentStore } from '../store/useAgentStore';
import { ChatResponse } from './api';

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";

let socket: WebSocket | null = null;

export function connectMockSocket() {
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
          reply: "",
          model: data.model,
          route_category: data.route_category,
          price_usdc: data.amount,
          payment_status: data.payment_status,
          flagged: data.flagged,
          payment_ref: data.payment_ref,
          timestamp: data.timestamp,
        } as unknown as ChatResponse);
      } else if (payload.event === "bond_slashed") {
        const data = payload.data;
        useAgentStore.getState().slashBondLocal(data.payout);
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
      connectMockSocket();
    }, 5000);
  };
}

export function disconnectMockSocket() {
  if (socket) {
    socket.close();
    socket = null;
  }
}
