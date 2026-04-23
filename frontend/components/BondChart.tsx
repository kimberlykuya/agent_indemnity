"use client";

import { useEffect, useState } from "react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useAgentStore } from "../store/useAgentStore";

interface DataPoint {
  time: string;
  value: number;
}

export function BondChart() {
  const currentBalance = useAgentStore((state) => state.bondBalance);
  const [data, setData] = useState<DataPoint[]>([]);

  // Initialize historical mock data and subscribe to live balance
  useEffect(() => {
    const history: DataPoint[] = [];
    let val = 10000;
    const now = new Date();
    
    // Generate 20 historical points
    for (let i = 20; i >= 0; i--) {
      const t = new Date(now.getTime() - i * 60000);
      // Small random walk to simulate older slashes
      if (Math.random() > 0.9) val -= 500;
      history.push({
        time: t.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        value: val
      });
    }
    
    // Replace the last point with current real balance to align history and live
    history[history.length - 1].value = currentBalance;
    setData(history);
  }, []);

  // Update chart when live balance drops
  useEffect(() => {
    if (data.length === 0) return;
    
    // Only add a new point if balance actually changed
    const lastPoint = data[data.length - 1];
    if (lastPoint.value !== currentBalance) {
      const t = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      setData(prev => [...prev.slice(1), { time: t, value: currentBalance }]);
    }
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
