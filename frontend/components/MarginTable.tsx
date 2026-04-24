export function MarginTable() {
  const models = [
    { name: "Qwen3-0.6B (General)", route: "general", price: "$0.001", cost: "$0.0005", margin: "50%", desc: "Fast keyword matching" },
    { name: "Qwen3-0.6B (Technical)", route: "technical", price: "$0.003", cost: "$0.0015", margin: "50%", desc: "Code-aware prompt context" },
    { name: "Qwen3-0.6B (Legal)", route: "legal_risk", price: "$0.005", cost: "$0.0020", margin: "60%", desc: "Strict verification gates" },
    { name: "Gemini 3.1 Pro (Complex)", route: "fallback", price: "$0.010", cost: "$0.0075", margin: "25%", desc: "Full cognitive fallback" },
  ];

  const rails = [
    {
      rail: "Ethereum L1",
      cost: "~$0.50–$5.00",
      viability: "✗ Never",
      why: "Gas for a single ERC-20 transfer dwarfs sub-cent pricing.",
      viabilityClass: "text-red-400",
    },
    {
      rail: "Stripe",
      cost: "$0.30 + 2.9%",
      viability: "✗ Never",
      why: "Minimum fee exceeds the charge before percentage fees.",
      viabilityClass: "text-red-400",
    },
    {
      rail: "Arc direct tx",
      cost: "~$0.005",
      viability: "✗ Marginal",
      why: "Still several times above the cheapest $0.001 route.",
      viabilityClass: "text-amber-400",
    },
    {
      rail: "Circle Gateway",
      cost: "~$0.00005",
      viability: "✓ Yes",
      why: "Batched auth + bulk Arc settlement keeps per-action cost tiny.",
      viabilityClass: "text-emerald-400",
    },
  ];

  return (
    <div className="space-y-6">
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
                  <td className="px-4 py-3 text-emerald-400 font-mono">{m.price}</td>
                  <td className="px-4 py-3 text-neutral-500 font-mono">{m.cost}</td>
                  <td className="px-4 py-3 text-blue-400 font-mono">{m.margin}</td>
                  <td className="px-4 py-3 text-neutral-500 text-xs">{m.desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="bg-neutral-900 border border-neutral-800 rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-neutral-800 bg-neutral-950">
          <h3 className="text-sm font-medium text-neutral-200">Why Traditional Rails Fail at Sub-Cent Scale</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm whitespace-nowrap">
            <thead className="bg-neutral-950/50 text-neutral-500 font-medium border-b border-neutral-800">
              <tr>
                <th className="px-4 py-2">Rail</th>
                <th className="px-4 py-2">Per-Action Cost</th>
                <th className="px-4 py-2">Viable at $0.001?</th>
                <th className="px-4 py-2 w-full">Why</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800/50">
              {rails.map((rail) => (
                <tr key={rail.rail} className="hover:bg-neutral-800/20 transition-colors">
                  <td className="px-4 py-3 text-neutral-300 font-medium">{rail.rail}</td>
                  <td className="px-4 py-3 text-neutral-500 font-mono">{rail.cost}</td>
                  <td className={`px-4 py-3 font-mono ${rail.viabilityClass}`}>{rail.viability}</td>
                  <td className="px-4 py-3 text-neutral-500 text-xs">{rail.why}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
