import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

export interface FactorData {
  factor: string;
  contribution: number;
  score: number;
}

export function FactorChart({ factors }: { factors: FactorData[] }): React.JSX.Element {
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          layout="vertical"
          data={factors}
          margin={{ top: 10, right: 30, left: 40, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" domain={[-0.15, 0.2]} tickFormatter={(val: number) => `${(val * 100).toFixed(0)}%`} />
          <YAxis type="category" dataKey="factor" tick={{ fontSize: 12 }} />
          <Tooltip
            formatter={(value: number) => [`${(Number(value) * 100).toFixed(1)}%`, 'Contribution']}
          />
          <Bar dataKey="contribution">
            {factors.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.contribution >= 0 ? '#10b981' : '#ef4444'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

