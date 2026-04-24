"use client";

import { useEffect, useRef, useState } from "react";
import { Bot, CreditCard, Send, ShieldAlert, User, Wallet } from "lucide-react";

import { PaymentChallengeResponse, sendChatMessage } from "../lib/api";
import { useAgentStore } from "../store/useAgentStore";
import { cn } from "../lib/utils";

interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  price?: number;
  route?: string;
  flagged?: boolean;
  anomalySignal?: string;
  slashMode?: string;
}

type PendingPayment = {
  originalMessage: string;
  challenge: PaymentChallengeResponse;
};

const DEMO_USER_ID = "demo_user";
const DEMO_WALLET = "0x191cc4e34e54444b9e10f4e3311c87382b0c0654";

export function AgentChat() {
  const setTransactionContext = useAgentStore((state) => state.setTransactionContext);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      role: "assistant",
      content: "Hello. Every request now requires a wallet-bound x402 payment challenge before the agent replies.",
    },
  ]);
  const [input, setInput] = useState("");
  const [walletAddress, setWalletAddress] = useState(DEMO_WALLET);
  const [isLoading, setIsLoading] = useState(false);
  const [isPaying, setIsPaying] = useState(false);
  const [pendingPayment, setPendingPayment] = useState<PendingPayment | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, pendingPayment]);

  const appendAssistantMessage = (message: Message) => {
    setMessages((prev) => [...prev, message]);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!input.trim() || isLoading || isPaying) return;

    const trimmedWallet = walletAddress.trim();
    if (!trimmedWallet) {
      appendAssistantMessage({
        id: `${Date.now()}-wallet`,
        role: "system",
        content: "Enter a beneficiary wallet address before requesting service.",
      });
      return;
    }

    const userMsg = input.trim();
    setInput("");
    setPendingPayment(null);
    setMessages((prev) => [...prev, { id: Date.now().toString(), role: "user", content: userMsg }]);
    setIsLoading(true);

    try {
      const result = await sendChatMessage({
        message: userMsg,
        userId: DEMO_USER_ID,
        userWalletAddress: trimmedWallet,
      });

      if (result.kind === "payment_required") {
        setPendingPayment({ originalMessage: userMsg, challenge: result });
        appendAssistantMessage({
          id: `${Date.now()}-challenge`,
          role: "system",
          content: `Payment challenge received: ${result.route_category} route, $${result.price_usdc.toFixed(3)} USDC, expires ${new Date(result.expires_at).toLocaleTimeString()}.`,
          price: result.price_usdc,
          route: result.route_category,
        });
        return;
      }

      setTransactionContext(result.payment_ref, {
        prompt: userMsg,
        reply: result.reply,
      });
      appendAssistantMessage({
        id: `${Date.now()}-reply`,
        role: "assistant",
        content: result.reply,
        price: result.price_usdc,
        route: result.route_category,
        flagged: result.flagged,
        anomalySignal: result.anomaly_signal,
        slashMode: result.slash_mode,
      });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Sorry, a network error occurred.";
      appendAssistantMessage({
        id: `${Date.now()}-error`,
        role: "assistant",
        content: errorMessage,
        flagged: true,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handlePayChallenge = async () => {
    if (!pendingPayment || isPaying) return;

    const trimmedWallet = walletAddress.trim();
    if (!trimmedWallet) {
      appendAssistantMessage({
        id: `${Date.now()}-wallet-required`,
        role: "system",
        content: "A wallet address is required to complete the challenge.",
      });
      return;
    }

    setIsPaying(true);
    try {
      const result = await sendChatMessage({
        message: pendingPayment.originalMessage,
        userId: DEMO_USER_ID,
        userWalletAddress: trimmedWallet,
        paymentChallengeToken: pendingPayment.challenge.payment_challenge_token,
        paymentProof: {
          proof_token: pendingPayment.challenge.payment_challenge_token,
          payer_wallet_address: trimmedWallet,
          facilitator_tx_ref: `demo-${Date.now()}`,
        },
      });

      if (result.kind === "payment_required") {
        setPendingPayment({ originalMessage: pendingPayment.originalMessage, challenge: result });
        appendAssistantMessage({
          id: `${Date.now()}-challenge-refresh`,
          role: "system",
          content: "The original payment challenge expired. A fresh challenge has been issued.",
        });
        return;
      }

      setTransactionContext(result.payment_ref, {
        prompt: pendingPayment.originalMessage,
        reply: result.reply,
      });
      appendAssistantMessage({
        id: `${Date.now()}-paid`,
        role: "system",
        content: `Payment confirmed from ${result.payer_wallet_address.slice(0, 8)}...${result.payer_wallet_address.slice(-6)}.`,
        price: result.price_usdc,
        route: result.route_category,
      });
      appendAssistantMessage({
        id: `${Date.now()}-answer`,
        role: "assistant",
        content: result.reply,
        price: result.price_usdc,
        route: result.route_category,
        flagged: result.flagged,
        anomalySignal: result.anomaly_signal,
        slashMode: result.slash_mode,
      });
      setPendingPayment(null);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Payment verification failed.";
      appendAssistantMessage({
        id: `${Date.now()}-payment-error`,
        role: "system",
        content: errorMessage,
        flagged: true,
      });
    } finally {
      setIsPaying(false);
    }
  };

  return (
    <div className="flex flex-col h-[680px] bg-neutral-900 border border-neutral-800 rounded-xl overflow-hidden shadow-2xl">
      <div className="px-4 py-3 border-b border-neutral-800 bg-neutral-950 flex justify-between items-center">
        <h3 className="font-medium text-neutral-200 flex items-center gap-2">
          <Bot className="w-4 h-4 text-emerald-500" />
          Customer Support
        </h3>
        <span className="text-xs text-neutral-500">x402 Challenge Flow</span>
      </div>

      <div className="px-4 py-4 border-b border-neutral-800 bg-neutral-950/60">
        <label className="block text-[10px] uppercase tracking-[0.2em] text-neutral-500 mb-2">
          Request Wallet / Beneficiary
        </label>
        <div className="relative">
          <Wallet className="w-4 h-4 text-neutral-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={walletAddress}
            onChange={(event) => setWalletAddress(event.target.value)}
            className="w-full bg-neutral-900 border border-neutral-800 rounded-xl pl-10 pr-4 py-3 text-sm font-mono text-neutral-200 focus:outline-none focus:border-emerald-500/50"
            placeholder="0x..."
            disabled={isLoading || isPaying}
          />
        </div>
        <p className="text-xs text-neutral-500 mt-2">
          This wallet pays for the request and receives any automatic slash payout for this session.
        </p>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={cn(
              "flex gap-3 max-w-[88%]",
              message.role === "user" ? "ml-auto flex-row-reverse" : ""
            )}
          >
            <div
              className={cn(
                "w-8 h-8 rounded-full flex items-center justify-center shrink-0",
                message.role === "user"
                  ? "bg-neutral-800"
                  : message.role === "system"
                    ? "bg-amber-500/10 text-amber-400"
                    : "bg-emerald-500/20 text-emerald-400"
              )}
            >
              {message.role === "user" ? (
                <User className="w-4 h-4 text-neutral-400" />
              ) : message.role === "system" ? (
                <CreditCard className="w-4 h-4" />
              ) : (
                <Bot className="w-4 h-4" />
              )}
            </div>

            <div className="flex flex-col gap-1">
              <div
                className={cn(
                  "px-4 py-2.5 rounded-2xl text-sm",
                  message.role === "user"
                    ? "bg-neutral-800 text-neutral-200 rounded-tr-sm"
                    : message.role === "system"
                      ? "bg-amber-500/10 border border-amber-500/20 text-amber-100 rounded-tl-sm"
                      : message.flagged
                        ? "bg-red-500/10 border border-red-500/20 text-red-200 rounded-tl-sm"
                        : "bg-neutral-950 border border-neutral-800 text-neutral-300 rounded-tl-sm"
                )}
              >
                {message.content}
              </div>

              {message.role !== "user" && message.price !== undefined && (
                <div className="flex items-center gap-2 px-1 flex-wrap">
                  <span
                    className={cn(
                      "text-[10px] uppercase font-bold tracking-wider",
                      message.flagged ? "text-red-400" : "text-emerald-500"
                    )}
                  >
                    {message.flagged ? "Blocked" : `$${message.price.toFixed(3)} USDC`}
                  </span>
                  {message.route && <span className="text-[10px] text-neutral-500">{message.route} route</span>}
                  {message.anomalySignal && message.anomalySignal !== "none" && (
                    <span className="text-[10px] text-amber-400">{message.anomalySignal}</span>
                  )}
                  {message.slashMode && message.slashMode !== "none" && (
                    <span className="text-[10px] text-red-400">{message.slashMode.toUpperCase()} slash</span>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}

        {pendingPayment && (
          <div className="border border-emerald-500/20 bg-emerald-500/5 rounded-2xl p-4 space-y-3">
            <div className="flex items-start gap-3">
              <div className="bg-emerald-500/10 p-2 rounded-xl">
                <CreditCard className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="space-y-1">
                <div className="text-sm font-medium text-white">Payment challenge pending</div>
                <div className="text-xs text-neutral-400">
                  {pendingPayment.challenge.payment_network} • ${pendingPayment.challenge.price_usdc.toFixed(3)} USDC
                </div>
                <div className="text-xs text-neutral-500 font-mono break-all">
                  {pendingPayment.challenge.payment_challenge_token}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="bg-black/20 rounded-xl border border-neutral-800 px-3 py-2">
                <div className="text-neutral-500 uppercase tracking-wider mb-1">Route</div>
                <div className="text-neutral-200 font-mono">{pendingPayment.challenge.route_category}</div>
              </div>
              <div className="bg-black/20 rounded-xl border border-neutral-800 px-3 py-2">
                <div className="text-neutral-500 uppercase tracking-wider mb-1">Expires</div>
                <div className="text-neutral-200 font-mono">
                  {new Date(pendingPayment.challenge.expires_at).toLocaleTimeString()}
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={handlePayChallenge}
              disabled={isPaying}
              className="w-full flex items-center justify-center gap-2 bg-emerald-500 hover:bg-emerald-600 disabled:bg-neutral-800 text-white py-3 rounded-xl transition-colors"
            >
              <ShieldAlert className="w-4 h-4" />
              {isPaying ? "Submitting Payment Proof..." : "Complete Payment and Continue"}
            </button>
          </div>
        )}

        {(isLoading || isPaying) && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-emerald-500/20 flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="px-4 py-3 rounded-2xl bg-neutral-950 border border-neutral-800 rounded-tl-sm flex gap-1">
              <div className="w-1.5 h-1.5 bg-neutral-600 rounded-full animate-bounce"></div>
              <div
                className="w-1.5 h-1.5 bg-neutral-600 rounded-full animate-bounce"
                style={{ animationDelay: "150ms" }}
              ></div>
              <div
                className="w-1.5 h-1.5 bg-neutral-600 rounded-full animate-bounce"
                style={{ animationDelay: "300ms" }}
              ></div>
            </div>
          </div>
        )}
      </div>

      <div className="p-4 bg-neutral-950 border-t border-neutral-800">
        <form onSubmit={handleSubmit} className="relative">
          <input
            type="text"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Type your message..."
            className="w-full bg-neutral-900 border border-neutral-800 rounded-full pl-4 pr-12 py-3 text-sm text-neutral-200 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/50 transition-all placeholder:text-neutral-600"
            disabled={isLoading || isPaying}
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading || isPaying}
            className="absolute right-2 top-2 p-1.5 bg-emerald-500 hover:bg-emerald-600 disabled:bg-neutral-800 text-white rounded-full transition-colors flex items-center justify-center"
          >
            <Send className="w-4 h-4 -ml-0.5" />
          </button>
        </form>
      </div>
    </div>
  );
}
