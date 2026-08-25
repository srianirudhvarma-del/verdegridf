import React, { useState, useEffect } from 'react';
import { waterFlowApi } from '../../data/mock/waterFlow';
import MetricCard from '../../components/shared/MetricCard';
import AlertBadge from '../../components/shared/AlertBadge';

const WaterWatchDashboard = () => {
    const [flows, setFlows] = useState([]);
    const [overallWue, setOverallWue] = useState(0);
    const [anomalies, setAnomalies] = useState([]);
    const [reportShown, setReportShown] = useState(false);
    const [report, setReport] = useState('');

    const generateReport = () => {
        const timestamp = new Date().toLocaleString();
        const totalWater = flows.reduce((acc, r) => acc + r.flow_rate_l_hr, 0);
        const totalLoad = flows.reduce((acc, r) => acc + r.it_load_kw, 0);
        
        const benchmarkStatus = overallWue < 1.1 ? 'EXCELLENT (Google-tier)' : 
                               overallWue < 1.8 ? 'GOOD (industry average)' : 
                               'NEEDS IMPROVEMENT';
        
        const recommendations = [];
        if (anomalies.length > 0) {
            recommendations.push(`- URGENT: Investigate ${anomalies.length} cooling loop(s) with abnormal flow rates`);
        }
        if (overallWue > 1.8) {
            recommendations.push('- Consider upgrading to free-cooling system (could reduce WUE by 30-40%)');
            recommendations.push('- Review hot-aisle/cold-aisle separation');
        }
        if (flows.some(f => f.flow_rate_l_hr / f.it_load_kw > 80)) {
            recommendations.push('- Optimize chiller setpoints; some racks are over-cooled');
        }
        
        const newReport = `
═══════════════════════════════════════════════════════════════
    WATERWATCH OPTIMIZATION REPORT
    Generated: ${timestamp}
═══════════════════════════════════════════════════════════════

CURRENT METRICS
  Global WUE: ${overallWue.toFixed(2)} L/kWh
  Total Water Flow: ${totalWater.toFixed(0)} L/hr
  Total IT Load: ${totalLoad.toFixed(1)} kW
  Active Chillers: ${flows.length}
  Anomalies Detected: ${anomalies.length}

BENCHMARK COMPARISON
  Your Datacenter: ${overallWue.toFixed(2)} L/kWh (${benchmarkStatus})
  Google Standard: 1.1 L/kWh
  Industry Average: 1.8 L/kWh
  Poor Efficiency: 3.0+ L/kWh

EFFICIENCY ANALYSIS
  ${overallWue < 1.1 ? '✅ EXCELLENT performance' : overallWue < 1.8 ? '✅ GOOD performance' : '⚠️  POOR performance'}

${recommendations.length > 0 ? 'RECOMMENDED ACTIONS\n' + recommendations.join('\n') : 'No critical issues detected.'}

PER-RACK BREAKDOWN
${flows.map(f => `  ${f.rack_id}: ${f.flow_rate_l_hr.toFixed(0)} L/hr | ${f.it_load_kw.toFixed(1)} kW (WUE: ${(f.flow_rate_l_hr / f.it_load_kw).toFixed(1)})`).join('\n')}

═══════════════════════════════════════════════════════════════
        Report End
═══════════════════════════════════════════════════════════════
        `;
        
        setReport(newReport);
        setReportShown(true);
    };

    useEffect(() => {
        const unsubscribe = waterFlowApi.subscribe((data) => {
            setFlows([...data]);
            
            // Calculate overall WUE: Total Water (L) / Total IT Load (kW)
            const totalWater = data.reduce((acc, r) => acc + r.flow_rate_l_hr, 0);
            const totalLoad = data.reduce((acc, r) => acc + r.it_load_kw, 0);
            const wue = totalLoad > 0 ? (totalWater / totalLoad) : 0;
            // Usually WUE averages 1.8. The mock produces ~800L / ~10kW = 80 per hour. 
            // Scaling down to standard WUE metrics for UI realism (L/kWh)
            setOverallWue(wue / 50); 
            
            // Z-score anomaly mock (detecting sudden spikes)
            const newAnomalies = data.filter(r => r.flow_rate_l_hr > 1100); 
            setAnomalies(newAnomalies);
        }, 3000);
        return () => unsubscribe();
    }, []);

    return (
        <div className="p-8 bg-black min-h-screen text-white font-sans overflow-auto h-full">
            <header className="mb-8 flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-black tracking-tight text-white mb-2 text-blue-400">WaterWatch</h1>
                    <p className="text-gray-400">PUE/WUE correlation and cooling loss detection.</p>
                </div>
                <button onClick={generateReport} className="bg-blue-600 hover:bg-blue-500 px-4 py-2 rounded-lg font-bold text-sm transition-colors">
                    Generate Optimization Report
                </button>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                <MetricCard 
                    title="Current Global WUE" 
                    value={overallWue.toFixed(2)} 
                    unit="L/kWh" 
                    trend={-0.05} 
                />
                <MetricCard 
                    title="Active Chillers" 
                    value={flows.length} 
                />
                <MetricCard 
                    title="Total Flow Rate" 
                    value={flows.reduce((acc, r) => acc + r.flow_rate_l_hr, 0).toFixed(0)} 
                    unit="L/hr"
                />
                <MetricCard 
                    title="Leak Suspicions" 
                    value={anomalies.length} 
                    trend={anomalies.length > 0 ? 1 : 0} 
                />
            </div>

            {anomalies.length > 0 && (
                <div className="mb-8 space-y-3">
                    {anomalies.map((a, i) => (
                        <AlertBadge 
                            key={i} 
                            level="warning" 
                            message={`Anomaly detected in ${a.rack_id} (Cooling Unit: ${a.cooling_unit}). Abnormal flow rate: ${a.flow_rate_l_hr.toFixed(0)} L/hr. Potential loop leak.`} 
                        />
                    ))}
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                    <h3 className="text-lg font-bold mb-6">Per-Rack Flow Heatmap</h3>
                    <div className="space-y-4">
                        {flows.map(r => {
                            const pct = Math.min(100, (r.flow_rate_l_hr / 1500) * 100);
                            return (
                                <div key={r.rack_id}>
                                    <div className="flex justify-between text-sm mb-1">
                                        <span className="font-semibold text-gray-300">{r.rack_id} ({r.cooling_unit})</span>
                                        <span className="text-blue-300">{r.flow_rate_l_hr.toFixed(0)} L/hr</span>
                                    </div>
                                    <div className="w-full bg-gray-800 rounded-full h-2.5 overflow-hidden">
                                        <div 
                                            className={`h-2.5 rounded-full transition-all duration-1000 ${pct > 80 ? 'bg-red-500' : 'bg-blue-500'}`} 
                                            style={{ width: `${pct}%` }}
                                        ></div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>

                <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                    <h3 className="text-lg font-bold mb-6">Industry Benchmarks (WUE)</h3>
                    <div className="space-y-6">
                        <div>
                            <div className="flex justify-between text-sm mb-1 text-gray-400">
                                <span>Google Average</span>
                                <span>1.1 L/kWh</span>
                            </div>
                            <div className="w-full bg-gray-800 rounded-full h-4">
                                <div className="bg-green-500 h-4 rounded-full" style={{ width: '20%' }}></div>
                            </div>
                        </div>
                        <div>
                            <div className="flex justify-between text-sm mb-1 font-bold text-blue-400">
                                <span>Your Datacenter</span>
                                <span>{overallWue.toFixed(2)} L/kWh</span>
                            </div>
                            <div className="w-full bg-gray-800 rounded-full h-4 relative">
                                <div className="bg-blue-500 h-4 rounded-full transition-all" style={{ width: `${(overallWue/3.5)*100}%` }}></div>
                            </div>
                        </div>
                        <div>
                            <div className="flex justify-between text-sm mb-1 text-gray-400">
                                <span>Industry Average</span>
                                <span>1.8 L/kWh</span>
                            </div>
                            <div className="w-full bg-gray-800 rounded-full h-4">
                                <div className="bg-yellow-500 h-4 rounded-full" style={{ width: '40%' }}></div>
                            </div>
                        </div>
                        <div>
                            <div className="flex justify-between text-sm mb-1 text-gray-400">
                                <span>Poor Efficiency</span>
                                <span>3.0+ L/kWh</span>
                            </div>
                            <div className="w-full bg-gray-800 rounded-full h-4">
                                <div className="bg-red-500 h-4 rounded-full" style={{ width: '80%' }}></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {reportShown && (
                <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
                    <div className="bg-gray-900 border border-gray-700 rounded-xl max-w-2xl w-full max-h-[80vh] overflow-y-auto">
                        <div className="sticky top-0 bg-gray-800 border-b border-gray-700 p-6 flex justify-between items-center">
                            <h2 className="text-xl font-bold text-blue-400">Optimization Report</h2>
                            <button 
                                onClick={() => setReportShown(false)}
                                className="text-gray-400 hover:text-white text-2xl"
                            >
                                ✕
                            </button>
                        </div>
                        <div className="p-6">
                            <pre className="text-xs text-gray-300 font-mono whitespace-pre-wrap break-words">
                                {report}
                            </pre>
                        </div>
                        <div className="bg-gray-800 border-t border-gray-700 p-6 flex gap-3">
                            <button 
                                onClick={() => {
                                    navigator.clipboard.writeText(report);
                                    alert('Report copied to clipboard!');
                                }}
                                className="flex-1 bg-green-600 hover:bg-green-500 px-4 py-2 rounded-lg font-bold text-sm transition-colors"
                            >
                                Copy Report
                            </button>
                            <button 
                                onClick={() => setReportShown(false)}
                                className="flex-1 bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded-lg font-bold text-sm transition-colors"
                            >
                                Close
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default WaterWatchDashboard;
