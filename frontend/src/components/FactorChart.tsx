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
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="rgba(255,255,255,0.06)" />
          <XAxis
            type="number"
            domain={[-0.15, 0.2]}
            tickFormatter={(val: number) => `${(val * 100).toFixed(0)}%`}
            stroke="#94a3b8"
            tick={{ fontSize: 11, fill: '#94a3b8' }}
          />
          <YAxis
            type="category"
            dataKey="factor"
            stroke="#94a3b8"
            tick={{ fontSize: 11, fill: '#cbd5e1' }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#0d1322',
              borderColor: 'rgba(255,255,255,0.1)',
              borderRadius: '12px',
              color: '#fff',
              fontSize: '12px',
            }}
            formatter={(value: number) => [`${(Number(value) * 100).toFixed(1)}%`, 'Contribution']}
          />
          <Bar dataKey="contribution" radius={[0, 4, 4, 0]}>
            {factors.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.contribution >= 0 ? '#10b981' : '#f43f5e'}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

