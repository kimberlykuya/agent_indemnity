"use client";

import { AlertCircle, ExternalLink } from "lucide-react";
import { useAgentStore } from "../store/useAgentStore";

export function PayoutAlert() {
  const bondBalance = useAgentStore((state) => state.bondBalance);
  
  // If bond is less than 10000, it means it was slashed
  if (bondBalance >= 10000) return null;

  return (
    <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-4 flex items-start gap-3 mt-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="bg-emerald-500/20 p-2 rounded-full shrink-0">
        <AlertCircle className="w-5 h-5 text-emerald-400" />
      </div>
      <div>
        <h4 className="text-emerald-400 font-medium text-sm">Consumer Protection Payout Initiated</h4>
        <p className="text-neutral-400 text-sm mt-1">
          An automated payout of $500 USDC has been triggered due to a detected policy violation by the agent.
        </p>
        <a 
          href="#" 
          className="inline-flex items-center gap-1.5 text-xs text-emerald-500 hover:text-emerald-400 mt-2 font-medium transition-colors"
          onClick={(e) => {
            e.preventDefault();
            alert("This would link to the Arc block explorer in production.");
          }}
        >
          View Transaction on Arc Explorer
          <ExternalLink className="w-3 h-3" />
        </a>
      </div>
    </div>
  );
}
