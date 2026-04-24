"use client";

import { useAgentStore } from "../store/useAgentStore";
import { cn } from "../lib/utils";

export function TxFeed() {
  const transactions = useAgentStore((state) => state.transactions);

  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-xl overflow-hidden flex flex-col h-[400px]">
      <div className="px-4 py-3 border-b border-neutral-800 flex justify-between items-center bg-neutral-950">
        <h3 className="text-sm font-medium text-neutral-200">Live Transaction Feed</h3>
        <span className="flex h-2 w-2 relative">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
        </span>
      </div>
      
      <div className="flex-1 overflow-y-auto p-4 space-y-3 font-mono text-xs">
        {transactions.length === 0 ? (
          <div className="text-neutral-500 text-center py-8">Waiting for incoming traffic...</div>
        ) : (
          transactions.map((tx) => {
            const preview =
              tx.type === "bond_slashed"
                ? `Bond slash executed${tx.tx_hash ? ` (${tx.tx_hash.slice(0, 12)}...)` : ""}`
                : tx.payment_ref || "Premium request recorded";
            const amountLabel =
              tx.type === "bond_slashed" ? `$${tx.amount.toFixed(2)} USDC` : `$${tx.amount.toFixed(3)} USDC`;
            const statusLabel =
              tx.type === "bond_slashed"
                ? tx.tx_hash ? "on-chain" : "slash"
                : tx.status || "pending";
            const badgeLabel = tx.type === "bond_slashed" ? "bond" : (tx.route_category || "system");

            return (
              <div 
                key={tx.id} 
                className="flex items-start justify-between gap-4 p-3 rounded-md bg-neutral-950 border border-neutral-800/50 hover:border-neutral-700 transition-colors"
              >
                <div className="flex-1 space-y-1">
                  <div className="flex items-center gap-2">
                    <span className={cn(
                      "px-1.5 py-0.5 rounded text-[10px] uppercase font-semibold",
                      tx.type === "bond_slashed" ? "bg-emerald-500/20 text-emerald-400" :
                      tx.flagged ? "bg-red-500/20 text-red-400" :
                      tx.route_category === "general" ? "bg-blue-500/20 text-blue-400" :
                      tx.route_category === "technical" ? "bg-amber-500/20 text-amber-400" :
                      tx.route_category === "legal" ? "bg-purple-500/20 text-purple-400" :
                      "bg-neutral-500/20 text-neutral-400"
                    )}>
                      {badgeLabel}
                    </span>
                    <span className="text-neutral-500">{tx.model?.split('/').pop() || tx.type}</span>
                  </div>
                  <p className={cn("text-sm", tx.flagged ? "text-red-300" : "text-neutral-300")}>
                    &quot;{preview.substring(0, 60)}{preview.length > 60 ? '...' : ''}&quot;
                  </p>
                  {tx.tx_hash && (
                    <p className="text-neutral-500 text-[10px] font-mono">{tx.tx_hash}</p>
                  )}
                </div>
                <div className="text-right flex flex-col gap-1 items-end shrink-0">
                  <span className="text-neutral-400">{amountLabel}</span>
                  <span className="text-neutral-600">{statusLabel}</span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
