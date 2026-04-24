"use client";

import { useAgentStore } from "../store/useAgentStore";
import { DEFAULT_SLASH_PAYOUT_USDC, slashBond } from "../lib/api";
import { ShieldAlert, TrendingDown, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { cn } from "../lib/utils";

export function BondBalance() {
  const balance = useAgentStore((state) => state.bondBalance);
  const [isSlashing, setIsSlashing] = useState(false);
  const minHealthyBond = Number(process.env.NEXT_PUBLIC_MIN_HEALTHY_BOND_USDC ?? "1.0");

  const handleSlash = async () => {
    setIsSlashing(true);
    toast.loading("Executing on-chain slash...", { id: "slash" });
    
    try {
      const { hash } = await slashBond();
      toast.success(
        <div className="flex flex-col gap-1">
          <span className="font-semibold text-emerald-400">Slash Successful</span>
          <span className="text-xs text-neutral-400 font-mono">{hash.substring(0,16)}...</span>
        </div>, 
        { id: "slash", duration: 5000 }
      );
    } catch {
      toast.error("Failed to execute slash", { id: "slash" });
    } finally {
      setIsSlashing(false);
    }
  };

  const isHealthy = Number.isFinite(minHealthyBond) ? balance >= minHealthyBond : balance > 0;

  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-6 flex flex-col justify-between h-[200px]">
      <div className="flex justify-between items-start">
        <div className="space-y-1">
          <h2 className="text-neutral-400 text-sm font-medium">Performance Bond</h2>
          <div className="text-4xl font-bold font-mono tracking-tight text-white">
            ${balance.toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </div>
          <div className="text-xs text-neutral-500 font-mono">Arc Network USDC</div>
        </div>
        
        <div className={cn(
          "px-3 py-1.5 rounded-full flex items-center gap-2 text-xs font-medium",
          isHealthy ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-red-500/10 text-red-400 border border-red-500/20"
        )}>
          {isHealthy ? <ShieldCheck className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
          {isHealthy ? "Healthy" : "At Risk"}
        </div>
      </div>

      <button
        onClick={handleSlash}
        disabled={isSlashing || balance === 0}
        className="w-full mt-4 flex items-center justify-center gap-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed text-white py-2.5 rounded-lg font-medium transition-colors focus:ring-2 ring-red-500/50 outline-none"
      >
        <ShieldAlert className="w-4 h-4" />
        {isSlashing
          ? "Executing Manual Slash..."
          : `Manual Slash Bond ($${DEFAULT_SLASH_PAYOUT_USDC.toFixed(2)})`}
      </button>
    </div>
  );
}
