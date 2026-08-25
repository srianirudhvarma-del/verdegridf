import React, { useState, useEffect } from 'react';
import { thermalSensorsApi } from '../../data/mock/thermalSensors';
import MetricCard from '../../components/shared/MetricCard';
import AlertBadge from '../../components/shared/AlertBadge';

const ThermalTraceDashboard = () => {
    const [grid, setGrid] = useState([]);
    const [alerts, setAlerts] = useState([]);
    const [predictedMode, setPredictedMode] = useState(false);
    const [maxTemp, setMaxTemp] = useState(0);
    const [avgTemp, setAvgTemp] = useState(0);
    const [hotspots, setHotspots] = useState(0);

    const temperatureToColor = (inlet, outlet) => {
        // Color gradient: blue (cool) -> yellow -> red (hot)
        // Thresholds: < 20°C = blue, 22-26°C = cyan, 26-30°C = yellow, > 30°C = orange/red
        if (inlet < 20) return { color: '#0084ff', label: 'Cold' };
        if (inlet < 24) return { color: '#00d4ff', label: 'Cool' };
        if (inlet < 28) return { color: '#ffff00', label: 'Warm' };
        if (inlet < 32) return { color: '#ff9500', label: 'Hot' };
        return { color: '#ff0000', label: 'Critical' };
    };

    const generatePredictedGrid = (currentGrid) => {
        // TODO: replace with LSTM prediction feed from ML model
        // For now, simulate a 15-minute forward prediction with slight temperature rise
        return currentGrid.map(cell => ({
            ...cell,
            inlet_celsius: cell.inlet_celsius + (Math.random() - 0.3) * 2,
            outlet_celsius: cell.outlet_celsius + (Math.random() - 0.3) * 2,
            isPredicted: true
        }));
    };

    useEffect(() => {
        const unsubscribe = thermalSensorsApi.subscribe((data) => {
            setGrid([...data]);
            
            // Calculate metrics
            const inlets = data.map(c => c.inlet_celsius);
            const maxInlet = Math.max(...inlets);
            const avgInlet = inlets.reduce((a, b) => a + b, 0) / inlets.length;
            
            setMaxTemp(maxInlet);
            setAvgTemp(avgInlet);
            
            // Count hotspots and generate alerts
            const newAlerts = [];
            let spotCount = 0;
            
            data.forEach(cell => {
                const delta = cell.outlet_celsius - cell.inlet_celsius;
                
                if (cell.inlet_celsius > 35) {
                    newAlerts.push({
                        id: `high-${cell.id}`,
                        level: 'critical',
                        message: `🔥 CRITICAL: Cell ${cell.id} inlet at ${cell.inlet_celsius.toFixed(1)}°C. Immediate cooling required!`
                    });
                    spotCount++;
                }
                
                if (delta > 15) {
                    newAlerts.push({
                        id: `delta-${cell.id}`,
                        level: 'warning',
                        message: `⚡ Excessive temperature delta in ${cell.id}: ${delta.toFixed(1)}°C (inlet: ${cell.inlet_celsius.toFixed(1)}°C, outlet: ${cell.outlet_celsius.toFixed(1)}°C)`
                    });
                }
                
                if (cell.inlet_celsius > 30) {
                    spotCount++;
                }
            });
            
            setAlerts(newAlerts);
            setHotspots(spotCount);
        }, 5000);
        
        return () => unsubscribe();
    }, []);

    const renderGrid = (data) => {
        return data.map(cell => {
            const { color } = temperatureToColor(cell.inlet_celsius, cell.outlet_celsius);
            const opacity = Math.min(1, (cell.inlet_celsius - 18) / 20); // Scale opacity from 18°C to 38°C
            
            return (
                <div
                    key={cell.id}
                    className="aspect-square rounded-sm cursor-pointer transition-all hover:ring-2 hover:ring-yellow-400 hover:scale-110"
                    style={{
                        backgroundColor: color,
                        opacity: Math.max(0.3, opacity),
                        boxShadow: `0 0 8px ${color}`
                    }}
                    title={`${cell.id}
In: ${cell.inlet_celsius.toFixed(1)}°C
Out: ${cell.outlet_celsius.toFixed(1)}°C
Δ: ${(cell.outlet_celsius - cell.inlet_celsius).toFixed(1)}°C`}
                ></div>
            );
        });
    };

    if (grid.length === 0) return <div className="p-8 text-white">Loading thermal grid...</div>;

    const currentGridData = predictedMode && grid.length > 0 ? generatePredictedGrid(grid) : grid;

    return (
        <div className="p-8 bg-black min-h-screen text-white font-sans overflow-auto h-full">
            <header className="mb-8 flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-black tracking-tight text-orange-400 mb-2">ThermalTrace</h1>
                    <p className="text-gray-400">Real-time hot/cold aisle monitoring and hotspot detection.</p>
                </div>
                <div className="flex items-center gap-4 bg-gray-900 border border-gray-700 p-3 rounded-lg">
                    <span className="text-sm font-bold uppercase text-gray-400">Predicted (15m)</span>
                    <button 
                        onClick={() => setPredictedMode(!predictedMode)}
                        className={`w-12 h-6 rounded-full transition-colors relative flex items-center ${predictedMode ? 'bg-orange-500' : 'bg-gray-700'}`}
                    >
                        <div className={`w-5 h-5 bg-white rounded-full absolute transition-transform transform ${predictedMode ? 'translate-x-6' : 'translate-x-1'}`}></div>
                    </button>
                </div>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <MetricCard 
                    title="Max Inlet Temp" 
                    value={maxTemp.toFixed(1)} 
                    unit="°C"
                    trend={maxTemp > 30 ? 1 : -1}
                />
                <MetricCard 
                    title="Avg Inlet Temp" 
                    value={avgTemp.toFixed(1)} 
                    unit="°C"
                />
                <MetricCard 
                    title="Hotspot Cells" 
                    value={hotspots} 
                    subtext={hotspots > 5 ? 'Requiring attention' : 'Nominal'}
                />
            </div>

            {alerts.length > 0 && (
                <div className="mb-8 space-y-3">
                    <div className="text-sm font-bold text-red-400 uppercase mb-3">Active Alerts ({alerts.length})</div>
                    {alerts.slice(0, 5).map(alert => (
                        <AlertBadge 
                            key={alert.id}
                            level={alert.level}
                            message={alert.message}
                        />
                    ))}
                    {alerts.length > 5 && (
                        <div className="text-xs text-gray-400 text-center py-2">
                            +{alerts.length - 5} more alerts
                        </div>
                    )}
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                    <h3 className="text-lg font-bold mb-6">
                        {predictedMode ? 'Predicted Thermal Grid (15 min)' : 'Current Thermal Grid (Real-time)'}
                    </h3>
                    <p className="text-xs text-gray-400 mb-4">8×8 Rack Inlet Temperature Matrix | Blue=Cool, Yellow=Warm, Red=Critical</p>
                    <div className="grid grid-cols-8 gap-1 p-4 bg-gray-800 rounded-lg">
                        {renderGrid(currentGridData)}
                    </div>
                </div>

                <div className="space-y-4">
                    {/* Temperature Scale Legend */}
                    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                        <h3 className="text-lg font-bold mb-4">Temperature Scale</h3>
                        <div className="space-y-3">
                            <div className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded" style={{ backgroundColor: '#0084ff' }}></div>
                                <div>
                                    <div className="font-bold">Cold</div>
                                    <div className="text-xs text-gray-400">&lt; 20°C (Excellent)</div>
                                </div>
                            </div>
                            <div className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded" style={{ backgroundColor: '#00d4ff' }}></div>
                                <div>
                                    <div className="font-bold">Cool</div>
                                    <div className="text-xs text-gray-400">20-24°C (Good)</div>
                                </div>
                            </div>
                            <div className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded" style={{ backgroundColor: '#ffff00' }}></div>
                                <div>
                                    <div className="font-bold">Warm</div>
                                    <div className="text-xs text-gray-400">24-28°C (Caution)</div>
                                </div>
                            </div>
                            <div className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded" style={{ backgroundColor: '#ff9500' }}></div>
                                <div>
                                    <div className="font-bold">Hot</div>
                                    <div className="text-xs text-gray-400">28-32°C (Warning)</div>
                                </div>
                            </div>
                            <div className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded" style={{ backgroundColor: '#ff0000' }}></div>
                                <div>
                                    <div className="font-bold">Critical</div>
                                    <div className="text-xs text-gray-400">&gt; 32°C (Urgent)</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* ML Placeholder */}
                    <div className="bg-blue-900/30 border border-blue-700/30 rounded-xl p-6">
                        <div className="font-bold text-blue-400 mb-2">🧠 ML Prediction Layer</div>
                        <div className="text-xs text-blue-300">
                            {/* TODO: replace with LSTM prediction feed */}
                            This section displays ML-based thermal predictions. The LSTM model will be integrated here to forecast temperature hotspots 15 minutes in advance.
                        </div>
                    </div>
                </div>
            </div>

            {/* Backend Route Reference */}
            <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-4 text-xs text-gray-500">
                <code>GET /api/thermaltrace/snapshot</code> — Backend route for fetching latest thermal grid data
            </div>
        </div>
    );
};

export default ThermalTraceDashboard;
