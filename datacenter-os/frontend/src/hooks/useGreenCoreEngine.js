import { useEffect, useCallback } from 'react';
import { useMetrics } from '../context/MetricsContext';

/**
 * useGreenCoreEngine - The synchronized heartbeat of the GreenCore system
 * 
 * Features:
 * - Global pulse that synchronizes all modules (5s interval)
 * - Continuous metrics aggregation and trend calculation
 * - Health checks and anomaly detection
 * - Real-time KPI updates via MetricsContext
 */
export function useGreenCoreEngine() {
  const { updateMetrics, metrics } = useMetrics();

  // Global pulse that fires every 5 seconds
  useEffect(() => {
    let pulseCount = 0;
    let totalEnergySaved = 0;
    let totalWaterSaved = 0;
    let totalCO2Avoided = 0;

    const pulse = async () => {
      pulseCount++;

      // Simulate aggregate data from all modules
      // In production, these would be API calls to fetch system-wide data
      const energyDelta = Math.random() * 5; // 0-5 kWh per pulse
      const waterDelta = Math.random() * 50; // 0-50L per pulse
      const co2Delta = Math.random() * 0.3; // 0-0.3 kg CO2 per pulse

      totalEnergySaved += energyDelta;
      totalWaterSaved += waterDelta;
      totalCO2Avoided += co2Delta;

      // Calculate efficiency score (0-100)
      const efficiencyScore = Math.min(100, 65 + Math.random() * 25 + (pulseCount % 6));

      // Detect anomalies
      const hasAnomalies = Math.random() > 0.8; // 20% chance of anomaly
      const anomalyCount = hasAnomalies ? Math.floor(Math.random() * 3) : 0;

      // Update global metrics
      updateMetrics({
        energySaved: totalEnergySaved,
        waterSaved: totalWaterSaved,
        co2Avoided: totalCO2Avoided,
        efficiencyScore,
        anomalyCount,
        lastPulse: new Date().toISOString(),
        pulseCount,
      });

      // Log health status every 30 seconds
      if (pulseCount % 6 === 0) {
        console.log(`[GreenCore Pulse #${pulseCount}] Energy: ${totalEnergySaved.toFixed(1)}kWh | Water: ${totalWaterSaved.toFixed(0)}L | CO2: ${totalCO2Avoided.toFixed(2)}kg | Efficiency: ${efficiencyScore.toFixed(1)}%`);
      }
    };

    // Fire initial pulse
    pulse();

    // Set up recurring pulse (every 5 seconds)
    const pulseInterval = setInterval(pulse, 5000);

    return () => clearInterval(pulseInterval);
  }, [updateMetrics]);

  // Utility function to calculate carbon intensity category
  const getCarbonCategory = useCallback((intensity) => {
    if (intensity < 200) return 'clean';
    if (intensity < 300) return 'moderate';
    return 'dirty';
  }, []);

  // Utility function for real-time trend analysis
  const calculateTrend = useCallback((currentValue, previousValue) => {
    if (!previousValue) return 0;
    return ((currentValue - previousValue) / previousValue) * 100;
  }, []);

  return {
    getCarbonCategory,
    calculateTrend,
    metrics,
  };
}
