import { create } from 'zustand';
import { TransactionRecord } from '../lib/api';

export type Transaction = TransactionRecord & {
  id: string;
};

interface AgentState {
  transactions: Transaction[];
  bondBalance: number;
  anomaliesCount: number;
  routeCounts: Record<string, number>;
  setTransactions: (transactions: TransactionRecord[]) => void;
  addTransaction: (tx: TransactionRecord) => void;
  slashBond: (amount: number) => void;
  setBondBalance: (balance: number) => void;
}

const parsedInitialBond = Number(process.env.NEXT_PUBLIC_INITIAL_BOND_USDC ?? "1.0");
const INITIAL_BOND =
  Number.isFinite(parsedInitialBond) && parsedInitialBond > 0 ? parsedInitialBond : 1.0;

export const useAgentStore = create<AgentState>((set) => ({
  transactions: [],
  bondBalance: INITIAL_BOND,
  anomaliesCount: 0,
  routeCounts: {
    general: 0,
    technical: 0,
    legal: 0,
    fallback: 0,
  },

  setTransactions: (transactions) => set(() => {
    const normalized = transactions.map((tx) => ({
      ...tx,
      id: `${tx.type}-${tx.timestamp}-${tx.payment_ref ?? tx.tx_hash ?? tx.amount}`,
    }));

    const routeCounts = {
      general: 0,
      technical: 0,
      legal: 0,
      fallback: 0,
    };

    let anomaliesCount = 0;
    for (const tx of normalized) {
      if (tx.type === "request_paid" && tx.route_category && tx.route_category in routeCounts) {
        routeCounts[tx.route_category as keyof typeof routeCounts] += 1;
      }
      if ((tx.type === "request_paid" || tx.type === "anomaly_flagged") && tx.flagged) {
        anomaliesCount += 1;
      }
    }

    return {
      transactions: normalized,
      anomaliesCount,
      routeCounts,
    };
  }),

  addTransaction: (tx) => set((state) => {
    const newTx: Transaction = {
      ...tx,
      id: `${tx.type}-${tx.timestamp}-${tx.payment_ref ?? tx.tx_hash ?? tx.amount}`,
    };

    const deduped = [newTx, ...state.transactions.filter((existing) => existing.id !== newTx.id)].slice(0, 100);
    const routeCounts = {
      general: 0,
      technical: 0,
      legal: 0,
      fallback: 0,
    };

    let anomaliesCount = 0;
    for (const item of deduped) {
      if (item.type === "request_paid" && item.route_category && item.route_category in routeCounts) {
        routeCounts[item.route_category as keyof typeof routeCounts] += 1;
      }
      if ((item.type === "request_paid" || item.type === "anomaly_flagged") && item.flagged) {
        anomaliesCount += 1;
      }
    }

    return {
      transactions: deduped,
      anomaliesCount,
      routeCounts,
    };
  }),

  slashBond: (amount) => set((state) => ({
    bondBalance: Math.max(0, state.bondBalance - amount),
  })),

  setBondBalance: (balance) => set({ bondBalance: balance }),
}));
