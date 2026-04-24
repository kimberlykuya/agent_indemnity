export function MarginTable() {
  const models = [
    { name: "General Route", route: "general", charge: 0.001, modelCost: 0.0005, desc: "Fast, low-risk prompts" },
    { name: "Technical Route", route: "technical", charge: 0.003, modelCost: 0.0015, desc: "Higher context + troubleshooting" },
    { name: "Legal/Risk Route", route: "legal_risk", charge: 0.005, modelCost: 0.0020, desc: "Policy-safe escalation handling" },
    { name: "Fallback Complex Route", route: "fallback", charge: 0.010, modelCost: 0.0075, desc: "Deep reasoning fallback" },
  ];
  const traditionalCostLow = 0.02;
  const traditionalCostHigh = 0.2;
  const avgCharge = models.reduce((sum, row) => sum + row.charge, 0) / models.length;
  const marginAtLow = avgCharge - traditionalCostLow;
  const marginAtHigh = avgCharge - traditionalCostHigh;

  const money = (v: number) => `$${v.toFixed(4)}`;

  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-neutral-800 bg-neutral-950">
        <h3 className="text-sm font-medium text-neutral-200">Unit Economics & Routing Margins</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm whitespace-nowrap">
          <thead className="bg-neutral-950/50 text-neutral-500 font-medium border-b border-neutral-800">
            <tr>
              <th className="px-4 py-2">Model / Route</th>
              <th className="px-4 py-2">Charge (USDC)</th>
              <th className="px-4 py-2">Base Cost</th>
              <th className="px-4 py-2">Margin</th>
              <th className="px-4 py-2 w-full">Logic</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-800/50">
            {models.map((m) => (
              <tr key={m.route} className="hover:bg-neutral-800/20 transition-colors">
                <td className="px-4 py-3 text-neutral-300 font-medium">{m.name}</td>
                <td className="px-4 py-3 text-emerald-400 font-mono">{money(m.charge)}</td>
                <td className="px-4 py-3 text-neutral-500 font-mono">{money(m.modelCost)}</td>
                <td className="px-4 py-3 text-blue-400 font-mono">
                  {((1 - m.modelCost / m.charge) * 100).toFixed(0)}%
                </td>
                <td className="px-4 py-3 text-neutral-500 text-xs">{m.desc}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="border-t border-neutral-800 p-4 bg-neutral-950/70">
        <h4 className="text-xs font-semibold text-neutral-300 uppercase tracking-wide">
          Why Traditional Per-Action Settlement Fails
        </h4>
        <p className="text-xs text-neutral-400 mt-2 leading-relaxed">
          If each action were settled directly with a traditional per-transaction cost floor of{" "}
          <span className="text-neutral-200 font-mono">{money(traditionalCostLow)}</span>, average margin would be{" "}
          <span className="text-red-300 font-mono">{money(marginAtLow)}</span> per action. Under a congested-cost case
          of <span className="text-neutral-200 font-mono">{money(traditionalCostHigh)}</span>, average margin drops to{" "}
          <span className="text-red-300 font-mono">{money(marginAtHigh)}</span> per action. This is why nanopayments + batched
          settlement are required for sub-cent pricing.
        </p>
      </div>
    </div>
  );
}
