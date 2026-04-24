"use client";

import { useEffect } from "react";
import { connectSocket, disconnectSocket } from "../lib/socket";
import { useAgentStore } from "../store/useAgentStore";
import { getBondStatus, getTransactions } from "../lib/api";
import { TxFeed } from "../components/TxFeed";
import { BondBalance } from "../components/BondBalance";
import { BondChart } from "../components/BondChart";
import { MarginTable } from "../components/MarginTable";
import { Copy, Terminal, ShieldAlert, BarChart3, Activity } from "lucide-react";
import { Toaster, toast } from "sonner";
import Link from "next/link";

export default function ComplianceDashboard() {
  const anomaliesCount = useAgentStore((state) => state.anomaliesCount);
  const routeCounts = useAgentStore((state) => state.routeCounts);
  const transactions = useAgentStore((state) => state.transactions);
  const setTransactions = useAgentStore((state) => state.setTransactions);
  const setBondBalance = useAgentStore((state) => state.setBondBalance);
  
  useEffect(() => {
    let isActive = true;

    const bootstrap = async () => {
      try {
        const [transactions, bondStatus] = await Promise.all([
          getTransactions(),
          getBondStatus(),
        ]);
        if (!isActive) return;
        setTransactions(transactions);
        setBondBalance(bondStatus.balance);
      } catch (error) {
        console.error("Failed to bootstrap dashboard state", error);
      }
    };

    bootstrap();
    connectSocket();
    return () => {
      isActive = false;
      disconnectSocket();
    };
  }, [setBondBalance, setTransactions]);

  const snippet = `curl -X POST https://api.agentindemnity.com/v1/chat \\
  -H "Authorization: Bearer sk-live-..." \\
  -d '{"message": "I need a refund for my last invoice"}'`;

  const copyToClipboard = () => {
    navigator.clipboard.writeText(snippet);
    toast("Snippet copied to clipboard");
  };

  const totalTxs = Math.max(1, transactions.length);
  const safeTxs = transactions.filter(t => !t.flagged).length;

  return (
    <div className="min-h-screen bg-black text-neutral-200 p-4 md:p-8 font-sans selection:bg-emerald-500/30">
      <Toaster theme="dark" position="top-right" />
      
      <div className="max-w-6xl mx-auto space-y-8">
        {/* Header & Nav */}
        <header className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
              <ShieldAlert className="w-6 h-6 text-emerald-500" />
              Agent Indemnity
            </h1>
            <p className="text-neutral-500 text-sm mt-1">Compliance & Economics Dashboard</p>
          </div>
          <Link 
            href="/demo" 
            className="px-4 py-2 bg-neutral-900 border border-neutral-800 hover:bg-neutral-800 text-sm font-medium rounded-lg transition-colors flex items-center gap-2"
          >
            <Terminal className="w-4 h-4" />
            Switch to Customer Chat View
          </Link>
        </header>

        {/* Developer Integration View */}
        <section className="bg-neutral-900 border border-neutral-800 rounded-xl p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-sm font-medium text-neutral-400">Developer Integration</h2>
          </div>
          <div className="relative group">
            <pre className="bg-black border border-neutral-800 p-4 rounded-lg font-mono text-sm text-emerald-400 overflow-x-auto">
              <code>{snippet}</code>
            </pre>
            <button 
              onClick={copyToClipboard}
              className="absolute top-3 right-3 p-2 bg-neutral-800 hover:bg-neutral-700 rounded-md text-neutral-400 transition-colors"
              title="Copy snippet"
            >
              <Copy className="w-4 h-4" />
            </button>
          </div>
        </section>

        {/* Core Dashboard Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          
          {/* Left Column: Bond & Metrics */}
          <div className="space-y-6">
            <BondBalance />
            
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-4">
                <div className="text-neutral-500 text-xs font-medium mb-1 flex items-center gap-1.5">
                  <Activity className="w-3.5 h-3.5" /> Safety Score
                </div>
                <div className="text-2xl font-bold text-white">
                  {Math.round((safeTxs / totalTxs) * 100)}%
                </div>
              </div>
              <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-4">
                <div className="text-neutral-500 text-xs font-medium mb-1 flex items-center gap-1.5">
                  <ShieldAlert className="w-3.5 h-3.5 text-red-500" /> Anomalies Blocked
                </div>
                <div className="text-2xl font-bold text-white">
                  {anomaliesCount}
                </div>
              </div>
            </div>

            <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-4">
              <div className="text-neutral-500 text-xs font-medium mb-3 flex items-center gap-1.5">
                <BarChart3 className="w-3.5 h-3.5" /> Routing Distribution
              </div>
              <div className="space-y-3">
                {[
                  { label: "General", key: "general", color: "bg-blue-500" },
                  { label: "Technical", key: "technical", color: "bg-amber-500" },
                  { label: "Legal/Risk", key: "legal", color: "bg-purple-500" },
                  { label: "Fallback", key: "fallback", color: "bg-neutral-500" },
                ].map((route) => {
                  const count = routeCounts[route.key] || 0;
                  const pct = (count / totalTxs) * 100;
                  return (
                    <div key={route.key} className="space-y-1.5">
                      <div className="flex justify-between text-xs">
                        <span className="text-neutral-400">{route.label}</span>
                        <span className="text-neutral-500">{Math.round(pct)}%</span>
                      </div>
                      <div className="w-full bg-black rounded-full h-1.5">
                        <div 
                          className={`h-1.5 rounded-full ${route.color}`} 
                          style={{ width: `${pct}%`, transition: 'width 0.5s ease' }}
                        ></div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
            
            <BondChart />
          </div>

          {/* Right Column: Feed & Margins */}
          <div className="md:col-span-2 space-y-6 flex flex-col">
            <TxFeed />
            <MarginTable />
          </div>
        </div>
      </div>
    </div>
  );
}
