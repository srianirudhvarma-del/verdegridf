import React, { useState, useEffect } from 'react';
import { serverClusterApi } from '../../data/mock/serverCluster';
import MetricCard from '../../components/shared/MetricCard';
import SavingsMeter from '../../components/shared/SavingsMeter';

const IdleHunterDashboard = () => {
    const [servers, setServers] = useState([]);
    const [candidates, setCandidates] = useState([]);
    const [isAutoConsolidating, setIsAutoConsolidating] = useState(false);
    
    // We'll track history to determine 'consecutive snapshots' for consolidation.
    // For this simple demo, if it's currently low, it's a candidate.
    
    useEffect(() => {
        const unsubscribe = serverClusterApi.subscribe((data) => {
            setServers([...data]);
            
            // Find candidates: cpu < 15% and ram < 20%
            const cands = data
                .filter(s => s.cpu_util < 15 && s.ram_util < 20)
                .sort((a, b) => b.watts_idle - a.watts_idle);
            setCandidates(cands);
        }, 2000);
        return () => unsubscribe();
    }, []);

    useEffect(() => {
        if (isAutoConsolidating && candidates.length > 0) {
            const timer = setTimeout(() => {
                handleMigrate(candidates[0].id);
            }, 3000);
            return () => clearTimeout(timer);
        }
    }, [isAutoConsolidating, candidates]);

    const handleMigrate = (id) => {
        const currentData = serverClusterApi.getSnapshot();
        const serverToMigrate = currentData.find(s => s.id === id);
        
        // Find least loaded ACTIVE server logic
        const target = currentData
            .filter(s => s.id !== id && s.cpu_util > 0 && s.cpu_util < 70)
            .sort((a, b) => a.cpu_util - b.cpu_util)[0];

        if (target && serverToMigrate) {
            // "Migrate" workload
            target.cpu_util += serverToMigrate.cpu_util;
            target.ram_util += serverToMigrate.ram_util;
            
            // Put source server into deep sleep
            serverToMigrate.cpu_util = 0;
            serverToMigrate.ram_util = 0;
            serverToMigrate.watts_idle = 10; // Deep sleep power
            
            serverClusterApi.updateSnapshot([...currentData]);
        }
    };

    return (
        <div className="p-8 bg-black min-h-screen text-white font-sans overflow-auto h-full">
            <header className="mb-8 flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-black tracking-tight text-white mb-2">IDLEhunter</h1>
                    <p className="text-gray-400">Compute efficiency and zombie server consolidation.</p>
                </div>
                <div className="flex items-center gap-4 bg-gray-900 border border-gray-700 p-3 rounded-lg">
                    <span className="text-sm font-bold uppercase text-gray-400">Auto-Consolidate</span>
                    <button 
                        onClick={() => setIsAutoConsolidating(!isAutoConsolidating)}
                        className={`w-12 h-6 rounded-full transition-colors relative flex items-center ${isAutoConsolidating ? 'bg-green-500' : 'bg-gray-700'}`}
                    >
                        <div className={`w-5 h-5 bg-white rounded-full absolute transition-transform transform ${isAutoConsolidating ? 'translate-x-6' : 'translate-x-1'}`}></div>
                    </button>
                </div>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <MetricCard 
                    title="Active Zombie Nodes" 
                    value={candidates.length} 
                    trend={-2} 
                    subtext="Wasting idle power"
                />
                <MetricCard 
                    title="Avg Cluster CPU" 
                    value={(servers.reduce((acc, s) => acc + s.cpu_util, 0) / (servers.length || 1)).toFixed(1)} 
                    unit="%"
                />
                <SavingsMeter initialKwh={1450.2} ratePerKwh={0.12} isActive={true} />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2 bg-gray-900 border border-gray-800 rounded-xl p-6">
                    <h3 className="text-lg font-bold mb-4">Cluster Grid (Active / Zombie / Sleep)</h3>
                    <div className="grid grid-cols-10 gap-2">
                        {servers.map(s => {
                            let bg = 'bg-gray-700'; // Sleep/Off
                            if (s.cpu_util > 0) bg = 'bg-green-500'; // Active
                            if (s.cpu_util > 0 && s.cpu_util < 15 && s.ram_util < 20) bg = 'bg-yellow-500'; // Zombie
                            if (s.cpu_util > 80) bg = 'bg-red-500'; // Stressed
                            
                            return (
                                <div key={s.id} title={`${s.id} | CPU: ${s.cpu_util.toFixed(1)}%`} className={`aspect-square rounded-sm ${bg} animate-pulse`}></div>
                            );
                        })}
                    </div>
                </div>
                
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 flex flex-col h-[500px]">
                    <h3 className="text-lg font-bold mb-4">Consolidation Queue</h3>
                    <div className="flex-1 overflow-y-auto space-y-3 pr-2">
                        {candidates.length === 0 ? (
                            <div className="text-gray-500 text-center py-8">No zombie servers detected.</div>
                        ) : (
                            candidates.map(c => (
                                <div key={c.id} className="bg-gray-800 p-4 rounded-lg flex justify-between items-center border border-gray-700">
                                    <div>
                                        <div className="font-bold text-sm">{c.id}</div>
                                        <div className="text-xs text-yellow-500 mt-1">Idle: {c.watts_idle}W | CPU: {c.cpu_util.toFixed(1)}%</div>
                                    </div>
                                    <button 
                                        onClick={() => handleMigrate(c.id)}
                                        className="bg-gray-700 hover:bg-green-600 hover:text-white px-3 py-1.5 rounded text-xs font-bold transition-colors"
                                    >
                                        Migrate
                                    </button>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default IdleHunterDashboard;
