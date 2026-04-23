import { create } from 'zustand';
import { ChatResponse } from '../lib/api';

export type Transaction = ChatResponse & {
  id: string;
  timestamp: number;
};

interface AgentState {
  transactions: Transaction[];
  bondBalance: number;
  anomaliesCount: number;
  routeCounts: Record<string, number>;
  addTransaction: (tx: ChatResponse) => void;
  slashBond: (amount: number) => void;
  setBondBalance: (balance: number) => void;
}

const INITIAL_BOND = 10000;

export const useAgentStore = create<AgentState>((set) => ({
  transactions: [],
  bondBalance: INITIAL_BOND,
  anomaliesCount: 0,
  routeCounts: {
    general: 0,
    technical: 0,
    legal_risk: 0,
    fallback_complex: 0,
  },
  
  addTransaction: (tx) => set((state) => {
    const newTx: Transaction = {
      ...tx,
      id: Math.random().toString(36).substring(7),
      timestamp: Date.now(),
    };
    
    return {
      transactions: [newTx, ...state.transactions].slice(0, 100), // Keep last 100
      anomaliesCount: state.anomaliesCount + (tx.flagged ? 1 : 0),
      routeCounts: {
        ...state.routeCounts,
        [tx.route_category]: (state.routeCounts[tx.route_category] || 0) + 1,
      }
    };
  }),

  slashBond: (amount) => set((state) => ({
    bondBalance: Math.max(0, state.bondBalance - amount),
  })),

  setBondBalance: (balance) => set({ bondBalance: balance }),
}));
