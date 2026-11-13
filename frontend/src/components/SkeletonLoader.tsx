import React from 'react';

export function SkeletonLoader(): React.JSX.Element {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-28 bg-slate-200 rounded-lg" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="h-64 bg-slate-200 rounded-lg" />
        <div className="h-64 bg-slate-200 rounded-lg" />
      </div>
      <div className="h-48 bg-slate-200 rounded-lg" />
    </div>
  );
}

