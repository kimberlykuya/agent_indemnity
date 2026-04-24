"use client";

import { useMemo } from "react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useAgentStore } from "../store/useAgentStore";

export function BondChart() {
  const currentBalance = useAgentStore((state) => state.bondBalance);

  const data = useMemo(() => {
    const now = new Date();
    const step = (10000 - currentBalance) / 6;

    return Array.from({ length: 7 }, (_, index) => {
      const pointTime = new Date(now.getTime() - (6 - index) * 60000);
      const value = index === 6 ? currentBalance : Math.max(currentBalance, Math.round(10000 - step * index));
      return {
        time: pointTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        value,
      };
    });
  }, [currentBalance]);

  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-4 h-[200px] flex flex-col">
      <h3 className="text-sm font-medium text-neutral-400 mb-4">Bond History</h3>
      <div className="flex-1 w-full min-h-0">
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
              domain={[0, 10000]} 
              hide 
            />
            <Tooltip 
              contentStyle={{ backgroundColor: '#171717', border: '1px solid #262626', borderRadius: '8px', color: '#fff' }}
              itemStyle={{ color: '#10b981' }}
              labelStyle={{ color: '#a3a3a3', marginBottom: '4px' }}
              formatter={(val: number) => [`$${val.toLocaleString()}`, 'Bond Balance']}
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
      </div>
    </div>
  );
}
