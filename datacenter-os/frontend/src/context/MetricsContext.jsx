import React, { createContext, useContext, useState } from 'react';

const MetricsContext = createContext();

export const MetricsProvider = ({ children }) => {
  const [metrics, setMetrics] = useState({
    energySaved: 12.4,
    waterSaved: 450,
    co2Avoided: 1.2,
    hotspots: 0,
  });

  const updateMetrics = (updates) => {
    setMetrics((prev) => ({
      ...prev,
      ...updates,
    }));
  };

  return (
    <MetricsContext.Provider value={{ metrics, updateMetrics }}>
      {children}
    </MetricsContext.Provider>
  );
};

// Standard context + hook pattern; splitting the hook into its own file isn't worth it
// eslint-disable-next-line react-refresh/only-export-components
export const useMetrics = () => {
  const context = useContext(MetricsContext);
  if (!context) {
    throw new Error('useMetrics must be used within MetricsProvider');
  }
  return context;
};