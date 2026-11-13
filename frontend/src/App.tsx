import React from 'react';

export default function App(): React.JSX.Element {
  return (
    <div style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
      <h1>AlphaLens</h1>
      <p>Calibrated, evidence-cited equity research assistant (NSE).</p>
      <div style={{ marginTop: '1rem', padding: '1rem', background: '#eef2ff', borderRadius: '4px' }}>
        <strong>Status:</strong> Ready (Vite + React 18 frontend)
      </div>
    </div>
  );
}
