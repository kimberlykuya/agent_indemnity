"use client";

import { useState } from "react";
import { useAgentStore } from "../store/useAgentStore";
import { cn } from "../lib/utils";
import { ChevronDown, ExternalLink } from "lucide-react";

export function TxFeed() {
  const transactions = useAgentStore((state) => state.transactions);
  const [selectedId, setSelectedId] = useState<string | null>(null);

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
            const isExpanded = selectedId === tx.id;
            const anomalyReason =
              "anomaly_reason" in tx ? (tx as { anomaly_reason?: string | null }).anomaly_reason : undefined;
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
            const rowClassName = cn(
              "flex items-start justify-between gap-4 p-3 rounded-md bg-neutral-950 border transition-colors relative",
              tx.type === "bond_slashed"
                ? tx.tx_hash
                  ? "border-red-500/40 hover:border-emerald-500/40 cursor-pointer"
                  : "border-red-500/40 hover:border-red-500/60"
                : tx.tx_hash
                  ? "border-neutral-800/50 hover:border-neutral-700 cursor-pointer"
                  : "border-neutral-800/50 hover:border-neutral-700"
            );
            const rowContent = (
              <>
                {tx.tx_hash && (
                  <ExternalLink className="w-3.5 h-3.5 text-neutral-500 absolute top-3 right-3" />
                )}
                <div className="flex-1 space-y-1 pr-6">
                  <div className="flex items-center gap-2">
                    <span className={cn(
                      "px-1.5 py-0.5 rounded text-[10px] uppercase font-semibold",
                      tx.type === "bond_slashed" ? "bg-red-500/20 text-red-400" :
                      tx.flagged ? "bg-red-500/20 text-red-400" :
                      tx.route_category === "general" ? "bg-blue-500/20 text-blue-400" :
                      tx.route_category === "technical" ? "bg-amber-500/20 text-amber-400" :
                      tx.route_category === "legal" ? "bg-purple-500/20 text-purple-400" :
                      "bg-neutral-500/20 text-neutral-400"
                    )}>
                      {tx.type === "bond_slashed" ? "BOND SLASHED" : badgeLabel}
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
                <div className="text-right flex flex-col gap-1 items-end shrink-0 pr-6">
                  <span className="text-neutral-400">{amountLabel}</span>
                  <span className="text-neutral-600">{statusLabel}</span>
                </div>
                <ChevronDown
                  className={cn(
                    "w-4 h-4 text-neutral-500 absolute right-3 top-1/2 -translate-y-1/2 transition-transform duration-200",
                    isExpanded && "rotate-180"
                  )}
                />
              </>
            );

            const requestTimestamp = new Date(tx.timestamp).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            });
            const bondTimestamp = new Date(tx.timestamp).toLocaleString();
            const truncatedPaymentRef = tx.payment_ref ? `${tx.payment_ref.slice(0, 18)}...` : "N/A";
            const truncatedVictim = tx.victim_address
              ? `${tx.victim_address.slice(0, 8)}...${tx.victim_address.slice(-6)}`
              : "N/A";
            const truncatedHash = tx.tx_hash ? `${tx.tx_hash.slice(0, 12)}...` : "N/A";

            return (
              <div key={tx.id}>
                <div
                  className={rowClassName}
                  onClick={() => setSelectedId(isExpanded ? null : tx.id)}
                >
                  {rowContent}
                </div>
                <div
                  className={cn(
                    "transition-all duration-200 overflow-hidden",
                    isExpanded ? "max-h-[200px]" : "max-h-0"
                  )}
                >
                  <div className="bg-black/40 border-t border-neutral-800/50 px-3 py-3 rounded-b-md">
                    {tx.type === "bond_slashed" ? (
                      <>
                        <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                          <div>
                            <div className="text-neutral-500 text-[10px] uppercase tracking-wider">Timestamp</div>
                            <div className="text-neutral-300 text-xs font-mono">{bondTimestamp}</div>
                          </div>
                          <div>
                            <div className="text-neutral-500 text-[10px] uppercase tracking-wider">Payout</div>
                            <div className="text-neutral-300 text-xs font-mono">${tx.amount.toFixed(3)} USDC</div>
                          </div>
                          <div>
                            <div className="text-neutral-500 text-[10px] uppercase tracking-wider">Victim</div>
                            <div className="text-neutral-300 text-xs font-mono">{truncatedVictim}</div>
                          </div>
                          <div>
                            <div className="text-neutral-500 text-[10px] uppercase tracking-wider">TX Hash</div>
                            <div className="text-neutral-300 text-xs font-mono">{truncatedHash}</div>
                          </div>
                        </div>
                        {tx.tx_hash && (
                          <a
                            href={`https://testnet.arcscan.app/tx/${tx.tx_hash}`}
                            target="_blank"
                            rel="noreferrer"
                            className="bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 border border-emerald-500/20 rounded-md py-2 text-xs font-medium w-full text-center mt-2 block"
                            onClick={(event) => event.stopPropagation()}
                          >
                            View on Arc Explorer →
                          </a>
                        )}
                      </>
                    ) : (
                      <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                        <div>
                          <div className="text-neutral-500 text-[10px] uppercase tracking-wider">Timestamp</div>
                          <div className="text-neutral-300 text-xs font-mono">{requestTimestamp}</div>
                        </div>
                        <div>
                          <div className="text-neutral-500 text-[10px] uppercase tracking-wider">Route</div>
                          <div className="text-neutral-300 text-xs font-mono">{tx.route_category || "N/A"}</div>
                        </div>
                        <div>
                          <div className="text-neutral-500 text-[10px] uppercase tracking-wider">Model</div>
                          <div className="text-neutral-300 text-xs font-mono">{tx.model?.split("/").pop() || "N/A"}</div>
                        </div>
                        <div>
                          <div className="text-neutral-500 text-[10px] uppercase tracking-wider">Price</div>
                          <div className="text-neutral-300 text-xs font-mono">${tx.amount.toFixed(3)} USDC</div>
                        </div>
                        <div>
                          <div className="text-neutral-500 text-[10px] uppercase tracking-wider">Status</div>
                          <div className="text-neutral-300 text-xs font-mono">{tx.status || "N/A"}</div>
                        </div>
                        <div>
                          <div className="text-neutral-500 text-[10px] uppercase tracking-wider">Payment Ref</div>
                          <div className="text-neutral-300 text-xs font-mono">{truncatedPaymentRef}</div>
                        </div>
                        <div>
                          <div className="text-neutral-500 text-[10px] uppercase tracking-wider">Flagged</div>
                          <div className={cn("text-xs font-mono", tx.flagged ? "text-red-400" : "text-emerald-400")}>
                            {tx.flagged ? "Yes" : "No"}
                          </div>
                        </div>
                        {tx.flagged && anomalyReason && (
                          <div>
                            <div className="text-neutral-500 text-[10px] uppercase tracking-wider">Anomaly</div>
                            <div className="text-neutral-300 text-xs font-mono">{anomalyReason}</div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
