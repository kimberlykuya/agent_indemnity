"use client";

import { AgentChat } from "../../components/AgentChat";
import { PayoutAlert } from "../../components/PayoutAlert";
import { ShieldCheck, LayoutDashboard } from "lucide-react";
import Link from "next/link";
import { Toaster } from "sonner";

export default function CustomerDemo() {
  return (
    <div className="min-h-screen bg-black text-neutral-200 p-4 md:p-8 font-sans selection:bg-emerald-500/30 flex justify-center items-center">
      <Toaster theme="dark" position="top-right" />
      
      <div className="w-full max-w-2xl mx-auto space-y-6">
        
        <header className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20">
              <ShieldCheck className="w-5 h-5 text-emerald-500" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white tracking-tight">Agent Support</h1>
              <p className="text-neutral-500 text-xs mt-0.5">Protected by AgentIndemnity</p>
            </div>
          </div>
          
          <Link 
            href="/" 
            className="px-3 py-1.5 bg-neutral-900 border border-neutral-800 hover:bg-neutral-800 text-xs font-medium rounded-md transition-colors flex items-center gap-1.5 text-neutral-400"
          >
            <LayoutDashboard className="w-3.5 h-3.5" />
            Compliance View
          </Link>
        </header>

        <main>
          <AgentChat />
          <PayoutAlert />
        </main>
        
        <footer className="text-center text-xs text-neutral-600 mt-8">
          <p>Demo environment • Micro-charges simulate live routing costs</p>
        </footer>
      </div>
    </div>
  );
}
