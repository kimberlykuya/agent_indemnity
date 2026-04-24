"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User } from "lucide-react";
import { sendChatMessage } from "../lib/api";
import { cn } from "../lib/utils";
import { useAgentStore } from "../store/useAgentStore";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  price?: number;
  route?: string;
  flagged?: boolean;
}

export function AgentChat() {
  const setTransactionContext = useAgentStore((state) => state.setTransactionContext);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      role: "assistant",
      content: "Hello. I am the Agent Indemnity automated support assistant. How can I help you today?",
    }
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMsg = input.trim();
    setInput("");
    setMessages(prev => [...prev, { id: Date.now().toString(), role: "user", content: userMsg }]);
    setIsLoading(true);

    try {
      const result = await sendChatMessage(userMsg);
      setTransactionContext(result.payment_ref, {
        prompt: userMsg,
        reply: result.reply,
      });

      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: result.reply,
        price: result.price_usdc,
        route: result.route_category,
        flagged: result.flagged
      }]);
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : "Sorry, a network error occurred.";
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: errorMessage,
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[600px] bg-neutral-900 border border-neutral-800 rounded-xl overflow-hidden shadow-2xl">
      <div className="px-4 py-3 border-b border-neutral-800 bg-neutral-950 flex justify-between items-center">
        <h3 className="font-medium text-neutral-200 flex items-center gap-2">
          <Bot className="w-4 h-4 text-emerald-500" />
          Customer Support
        </h3>
        <span className="text-xs text-neutral-500">Live Session</span>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((m) => (
          <div key={m.id} className={cn("flex gap-3 max-w-[85%]", m.role === "user" ? "ml-auto flex-row-reverse" : "")}>
            <div className={cn(
              "w-8 h-8 rounded-full flex items-center justify-center shrink-0",
              m.role === "user" ? "bg-neutral-800" : "bg-emerald-500/20 text-emerald-400"
            )}>
              {m.role === "user" ? <User className="w-4 h-4 text-neutral-400" /> : <Bot className="w-4 h-4" />}
            </div>
            
            <div className="flex flex-col gap-1">
              <div className={cn(
                "px-4 py-2.5 rounded-2xl text-sm",
                m.role === "user" 
                  ? "bg-neutral-800 text-neutral-200 rounded-tr-sm" 
                  : m.flagged 
                    ? "bg-red-500/10 border border-red-500/20 text-red-200 rounded-tl-sm"
                    : "bg-neutral-950 border border-neutral-800 text-neutral-300 rounded-tl-sm"
              )}>
                {m.content}
              </div>
              
              {m.role === "assistant" && m.price !== undefined && (
                <div className="flex items-center gap-2 px-1">
                  <span className={cn(
                    "text-[10px] uppercase font-bold tracking-wider",
                    m.flagged ? "text-red-400" : "text-emerald-500"
                  )}>
                    {m.flagged ? "Blocked" : `$${m.price.toFixed(3)} USDC`}
                  </span>
                  <span className="text-[10px] text-neutral-500">{m.route} route</span>
                </div>
              )}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-emerald-500/20 flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="px-4 py-3 rounded-2xl bg-neutral-950 border border-neutral-800 rounded-tl-sm flex gap-1">
              <div className="w-1.5 h-1.5 bg-neutral-600 rounded-full animate-bounce"></div>
              <div className="w-1.5 h-1.5 bg-neutral-600 rounded-full animate-bounce" style={{ animationDelay: "150ms" }}></div>
              <div className="w-1.5 h-1.5 bg-neutral-600 rounded-full animate-bounce" style={{ animationDelay: "300ms" }}></div>
            </div>
          </div>
        )}
      </div>

      <div className="p-4 bg-neutral-950 border-t border-neutral-800">
        <form onSubmit={handleSubmit} className="relative">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message..."
            className="w-full bg-neutral-900 border border-neutral-800 rounded-full pl-4 pr-12 py-3 text-sm text-neutral-200 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/50 transition-all placeholder:text-neutral-600"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="absolute right-2 top-2 p-1.5 bg-emerald-500 hover:bg-emerald-600 disabled:bg-neutral-800 text-white rounded-full transition-colors flex items-center justify-center"
          >
            <Send className="w-4 h-4 -ml-0.5" />
          </button>
        </form>
      </div>
    </div>
  );
}
