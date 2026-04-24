"use client";

import { useMemo } from "react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useAgentStore } from "../store/useAgentStore";

export function BondChart() {
  const transactions = useAgentStore((state) => state.transactions);

  const data = useMemo(() => {
    const history = [...transactions]
      .filter((tx) => typeof tx.bond_balance_after === "number")
      .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
      .slice(-12)
      .map((tx) => ({
        time: new Date(tx.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        fullTime: new Date(tx.timestamp).toLocaleString([], {
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }),
        value: tx.bond_balance_after as number,
      }));

    if (history.length === 0) {
      return [];
    }

    return history;
  }, [transactions]);

  const yMax = useMemo(() => {
    const maxValue = data.reduce((max, point) => Math.max(max, point.value), 0);
    return Math.max(0.05, Number((maxValue * 1.25 || 0.05).toFixed(4)));
  }, [data]);

  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-4 h-[200px] flex flex-col">
      <h3 className="text-sm font-medium text-neutral-400 mb-4">Bond History</h3>
      <div className="flex-1 w-full min-h-0">
        {data.length === 0 ? (
          <div className="h-full flex items-center justify-center text-sm text-neutral-500">
            Waiting for bond data
          </div>
        ) : (
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 5, right: 0, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <XAxis 
              dataKey="time" 
              hide 
            />
            <YAxis 
              domain={[0, yMax]} 
              hide 
            />
            <Tooltip 
              contentStyle={{ backgroundColor: '#171717', border: '1px solid #262626', borderRadius: '8px', color: '#fff' }}
              itemStyle={{ color: '#10b981' }}
              labelStyle={{ color: '#a3a3a3', marginBottom: '4px' }}
              labelFormatter={(_, payload) => payload?.[0]?.payload?.fullTime ?? ""}
              formatter={(val: number) => [`$${val.toFixed(4)}`, 'Bond Balance']}
            />
            <Area 
              type="stepAfter" 
              dataKey="value" 
              stroke="#10b981" 
              strokeWidth={2}
              fillOpacity={1} 
              fill="url(#colorValue)" 
              isAnimationActive={true}
            />
          </AreaChart>
        </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
