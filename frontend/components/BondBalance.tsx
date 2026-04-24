"use client";

import { useMemo, useState } from "react";
import { ShieldAlert, TrendingDown, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

import { slashBond } from "../lib/api";
import { useAgentStore } from "../store/useAgentStore";
import { cn } from "../lib/utils";

export function BondBalance() {
  const balance = useAgentStore((state) => state.bondBalance);
  const transactions = useAgentStore((state) => state.transactions);
  const [isSlashing, setIsSlashing] = useState(false);
  const [manualVictimAddress, setManualVictimAddress] = useState("");

  const latestBeneficiary = useMemo(
    () =>
      transactions.find((tx) => tx.type === "request_paid" && tx.beneficiary_wallet_address)
        ?.beneficiary_wallet_address ?? "",
    [transactions]
  );

  const effectiveVictimAddress = manualVictimAddress.trim() || latestBeneficiary;

  const handleSlash = async () => {
    if (!effectiveVictimAddress) {
      toast.error("Provide a beneficiary wallet or send a paid request first.");
      return;
    }

    setIsSlashing(true);
    toast.loading("Executing manual on-chain slash...", { id: "slash" });

    try {
      const { hash } = await slashBond(effectiveVictimAddress);
      toast.success(
        <div className="flex flex-col gap-1">
          <span className="font-semibold text-emerald-400">Manual Slash Successful</span>
          <span className="text-xs text-neutral-400 font-mono">{hash.substring(0, 16)}...</span>
        </div>,
        { id: "slash", duration: 5000 }
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to execute slash";
      toast.error(message, { id: "slash" });
    } finally {
      setIsSlashing(false);
    }
  };

  const hasBalance = balance !== null;
  const isHealthy = hasBalance && balance > 0.01;

  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-6 flex flex-col justify-between h-[240px]">
      <div className="flex justify-between items-start gap-4">
        <div className="space-y-1">
          <h2 className="text-neutral-400 text-sm font-medium">Performance Bond</h2>
          <div className="text-4xl font-bold font-mono tracking-tight text-white">
            {hasBalance
              ? `$${balance.toLocaleString("en-US", { minimumFractionDigits: 2 })}`
              : "--"}
          </div>
          <div className="text-xs text-neutral-500 font-mono">Arc Network USDC</div>
        </div>

        <div
          className={cn(
            "px-3 py-1.5 rounded-full flex items-center gap-2 text-xs font-medium",
            hasBalance && isHealthy
              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
              : "bg-red-500/10 text-red-400 border border-red-500/20"
          )}
        >
          {hasBalance && isHealthy ? <ShieldCheck className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
          {hasBalance ? (isHealthy ? "Healthy" : "At Risk") : "Loading"}
        </div>
      </div>

      <div className="space-y-3 mt-4">
        <div>
          <label className="block text-[10px] uppercase tracking-[0.2em] text-neutral-500 mb-2">
            Manual Beneficiary Override
          </label>
          <input
            type="text"
            value={manualVictimAddress}
            onChange={(event) => setManualVictimAddress(event.target.value)}
            placeholder={latestBeneficiary || "0x..."}
            className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-3 py-2 text-xs font-mono text-neutral-200 focus:outline-none focus:border-emerald-500/50"
          />
          <p className="text-[11px] text-neutral-500 mt-2">
            Defaults to the latest paid request wallet when left blank.
          </p>
        </div>

        <button
          onClick={handleSlash}
          disabled={isSlashing || !hasBalance || balance === 0}
          className="w-full flex items-center justify-center gap-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed text-white py-2.5 rounded-lg font-medium transition-colors focus:ring-2 ring-red-500/50 outline-none"
        >
          <ShieldAlert className="w-4 h-4" />
          {isSlashing ? "Executing Manual Slash..." : "Manual Slash Bond"}
        </button>
      </div>
    </div>
  );
}
