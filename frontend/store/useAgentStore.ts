import { create } from 'zustand';
import { TransactionRecord } from '../lib/api';

export type Transaction = TransactionRecord & {
  id: string;
};

type TransactionContext = {
  prompt?: string | null;
  reply?: string | null;
};

interface AgentState {
  transactions: Transaction[];
  bondBalance: number | null;
  bondAlertFloor: number | null;
  bondWarning: string | null;
  anomaliesCount: number;
  routeCounts: Record<string, number>;
  transactionContextByRef: Record<string, TransactionContext>;
  setTransactions: (transactions: TransactionRecord[]) => void;
  addTransaction: (tx: TransactionRecord) => void;
  setTransactionContext: (reference: string, context: TransactionContext) => void;
  slashBond: (amount: number) => void;
  setBondBalance: (balance: number) => void;
  setBondAlert: (alertFloor: number | null, warning: string | null) => void;
}

const routeKeys = ["general", "technical", "legal", "fallback"] as const;

const emptyRouteCounts = () => ({
  general: 0,
  technical: 0,
  legal: 0,
  fallback: 0,
});

const getTransactionReference = (tx: TransactionRecord) => tx.payment_ref ?? tx.tx_hash ?? null;

const mergeTransactionContext = (
  tx: TransactionRecord,
  transactionContextByRef: Record<string, TransactionContext>
): Transaction => {
  const reference = getTransactionReference(tx);
  const context = reference ? transactionContextByRef[reference] : undefined;

  return {
    ...tx,
    prompt: tx.prompt ?? context?.prompt ?? null,
    reply: tx.reply ?? context?.reply ?? null,
    id: `${tx.type}-${tx.timestamp}-${tx.payment_ref ?? tx.tx_hash ?? tx.amount}`,
  };
};

const summarizeTransactions = (transactions: Transaction[]) => {
  const routeCounts = emptyRouteCounts();
  let anomaliesCount = 0;

  for (const tx of transactions) {
    if (tx.type === "request_paid" && tx.route_category && routeKeys.includes(tx.route_category as (typeof routeKeys)[number])) {
      routeCounts[tx.route_category as keyof typeof routeCounts] += 1;
    }
    if ((tx.type === "request_paid" || tx.type === "anomaly_flagged") && tx.flagged) {
      anomaliesCount += 1;
    }
  }

  return { routeCounts, anomaliesCount };
};

export const useAgentStore = create<AgentState>((set) => ({
  transactions: [],
  bondBalance: null,
  bondAlertFloor: null,
  bondWarning: null,
  anomaliesCount: 0,
  routeCounts: emptyRouteCounts(),
  transactionContextByRef: {},

  setTransactions: (transactions) => set((state) => {
    const normalized = transactions.map((tx) => mergeTransactionContext(tx, state.transactionContextByRef));
    const { routeCounts, anomaliesCount } = summarizeTransactions(normalized);

    return {
      transactions: normalized,
      anomaliesCount,
      routeCounts,
    };
  }),

  addTransaction: (tx) => set((state) => {
    const newTx = mergeTransactionContext(tx, state.transactionContextByRef);
    const deduped = [newTx, ...state.transactions.filter((existing) => existing.id !== newTx.id)].slice(0, 100);
    const { routeCounts, anomaliesCount } = summarizeTransactions(deduped);

    return {
      transactions: deduped,
      anomaliesCount,
      routeCounts,
    };
  }),

  setTransactionContext: (reference, context) => set((state) => {
    if (!reference.trim()) {
      return state;
    }

    const transactionContextByRef = {
      ...state.transactionContextByRef,
      [reference]: {
        ...state.transactionContextByRef[reference],
        ...context,
      },
    };

    const transactions = state.transactions.map((tx) =>
      getTransactionReference(tx) === reference
        ? {
            ...tx,
            prompt: tx.prompt ?? context.prompt ?? null,
            reply: tx.reply ?? context.reply ?? null,
          }
        : tx
    );

    return {
      transactionContextByRef,
      transactions,
    };
  }),

  slashBond: (amount) => set((state) => ({
    bondBalance: state.bondBalance === null ? null : Math.max(0, state.bondBalance - amount),
  })),

  setBondBalance: (balance) => set({ bondBalance: balance }),
  setBondAlert: (alertFloor, warning) => set({ bondAlertFloor: alertFloor, bondWarning: warning }),
}));
