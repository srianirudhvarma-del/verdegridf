import React, { useState, useEffect } from 'react';
import { carbonIntensityApi } from '../../data/mock/carbonIntensity';
import MetricCard from '../../components/shared/MetricCard';
import AlertBadge from '../../components/shared/AlertBadge';

const CarbonClockDashboard = () => {
    const [intensity, setIntensity] = useState(null);
    const [jobs, setJobs] = useState([]);
    const [deferredJobs, setDeferredJobs] = useState([]);
    const [executedJobs, setExecutedJobs] = useState([]);
    const [co2Avoided, setCo2Avoided] = useState(0);

    useEffect(() => {
        const unsubscribe = carbonIntensityApi.subscribe((data) => {
            setIntensity(data.intensity);
            setJobs(data.jobs);
            setDeferredJobs(data.deferredJobs);
            setExecutedJobs(data.executedJobs);
            
            // Calculate CO2 avoided by deferring jobs
            const avoided = deferredJobs.reduce((acc, job) => acc + (job.estimatedKwh * 0.5), 0); // Assume 500g CO2 per kWh
            setCo2Avoided(avoided);
        }, 5000);
        return () => unsubscribe();
    }, [deferredJobs]);

    const getIntensityColor = (val) => {
        if (val < 100) return 'text-green-400';
        if (val < 200) return 'text-yellow-400';
        if (val < 300) return 'text-orange-400';
        return 'text-red-500';
    };

    const getIntensityBg = (val) => {
        if (val < 100) return 'from-green-900 to-emerald-900';
        if (val < 200) return 'from-yellow-900 to-amber-900';
        if (val < 300) return 'from-orange-900 to-orange-800';
        return 'from-red-900 to-red-800';
    };

    const getJobStatus = (job) => {
        if (job.status === 'executing') return 'bg-green-900/50 text-green-300';
        if (job.status === 'deferred') return 'bg-yellow-900/50 text-yellow-300';
        if (job.status === 'completed') return 'bg-blue-900/50 text-blue-300';
        return 'bg-gray-800 text-gray-300';
    };

    if (!intensity) return <div className="p-8 text-white">Loading...</div>;

    const pendingJobs = jobs.filter(j => j.status === 'pending');
    const scheduledWindow = intensity.carbonIntensity > 300 ? 'HIGH - Deferring jobs' : intensity.carbonIntensity > 200 ? 'MODERATE - Ready to run' : 'LOW - Optimal window';

    return (
        <div className="p-8 bg-black min-h-screen text-white font-sans overflow-auto h-full">
            <header className="mb-8">
                <h1 className="text-3xl font-black tracking-tight text-emerald-400 mb-2">CarbonClock</h1>
                <p className="text-gray-400">Real-time grid carbon intensity & intelligent job scheduling.</p>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <MetricCard 
                    title="Grid Carbon Intensity" 
                    value={intensity.carbonIntensity} 
                    unit="gCO2/kWh"
                    trend={intensity.carbonIntensity > 250 ? 1 : -1}
                />
                <MetricCard 
                    title="Jobs in Queue" 
                    value={pendingJobs.length} 
                    subtext={`${deferredJobs.length} deferred`}
                />
                <MetricCard 
                    title="CO2 Avoided Today" 
                    value={co2Avoided.toFixed(0)} 
                    unit="kg"
                    trend={deferredJobs.length > 0 ? 1 : 0}
                />
            </div>

            {intensity.carbonIntensity > 300 && (
                <AlertBadge 
                    level="critical" 
                    message="⚠️  High carbon intensity detected! Jobs are being deferred to low-carbon windows to minimize environmental impact."
                />
            )}

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
                {/* Carbon Intensity Gauge */}
                <div className={`lg:col-span-1 bg-gradient-to-br ${getIntensityBg(intensity.carbonIntensity)} border border-${intensity.carbonIntensity > 300 ? 'red' : 'yellow'}-700/30 rounded-xl p-8 shadow-[0_0_20px_rgba(20,184,166,0.1)]`}>
                    <h3 className="text-sm font-bold text-gray-300 tracking-widest uppercase mb-6">Carbon Intensity</h3>
                    <div className="flex flex-col items-center justify-center">
                        <div className={`text-6xl font-black ${getIntensityColor(intensity.carbonIntensity)}`}>
                            {intensity.carbonIntensity}
                        </div>
                        <div className="text-gray-300 text-sm mt-2">grams CO2 per kWh</div>
                        <div className="mt-6 w-full bg-gray-900/50 rounded-full h-3 overflow-hidden">
                            <div 
                                className={`h-3 transition-all duration-500 ${intensity.carbonIntensity < 100 ? 'bg-green-500' : intensity.carbonIntensity < 200 ? 'bg-yellow-500' : intensity.carbonIntensity < 300 ? 'bg-orange-500' : 'bg-red-500'}`}
                                style={{ width: `${Math.min(100, (intensity.carbonIntensity / 400) * 100)}%` }}
                            ></div>
                        </div>
                        <div className="mt-4 text-xs text-gray-400 textcenter">
                            {scheduledWindow}
                        </div>
                    </div>
                </div>

                {/* Current Status */}
                <div className="lg:col-span-2 bg-gray-900 border border-gray-800 rounded-xl p-6">
                    <h3 className="text-lg font-bold mb-6">Scheduling Timeline</h3>
                    <div className="space-y-4">
                        {deferredJobs.length > 0 && (
                            <div className="bg-yellow-900/30 border border-yellow-700/30 rounded-lg p-4">
                                <div className="text-yellow-400 font-bold text-sm uppercase mb-2">Deferred (Waiting for clean grid)</div>
                                <div className="space-y-2 text-xs text-yellow-300">
                                    {deferredJobs.map(job => (
                                        <div key={job.id} className="flex justify-between">
                                            <span>{job.name}</span>
                                            <span>{job.estimatedDuration} min | {job.estimatedKwh} kWh</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                        
                        {pendingJobs.length > 0 && (
                            <div className="bg-green-900/30 border border-green-700/30 rounded-lg p-4">
                                <div className="text-green-400 font-bold text-sm uppercase mb-2">Ready to Execute (Now)</div>
                                <div className="space-y-2 text-xs text-green-300">
                                    {pendingJobs.map(job => (
                                        <div key={job.id} className="flex justify-between">
                                            <span>{job.name}</span>
                                            <span>{job.estimatedDuration} min | {job.estimatedKwh} kWh</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {executedJobs.length > 0 && (
                            <div className="bg-blue-900/30 border border-blue-700/30 rounded-lg p-4">
                                <div className="text-blue-400 font-bold text-sm uppercase mb-2">Recently Executed</div>
                                <div className="space-y-2 text-xs text-blue-300">
                                    {executedJobs.slice(-3).map(job => (
                                        <div key={job.id} className="flex justify-between">
                                            <span>{job.name}</span>
                                            <span>{job.estimatedDuration} min | {job.estimatedKwh} kWh</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Job Queue */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                <h3 className="text-lg font-bold mb-6">All Jobs</h3>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead className="border-b border-gray-700">
                            <tr className="text-gray-400 text-xs uppercase">
                                <th className="text-left py-3 px-4">Job Name</th>
                                <th className="text-left py-3 px-4">Type</th>
                                <th className="text-center py-3 px-4">Duration (min)</th>
                                <th className="text-center py-3 px-4">Est. kWh</th>
                                <th className="text-center py-3 px-4">Deferrable</th>
                                <th className="text-center py-3 px-4">Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {[...jobs, ...deferredJobs, ...executedJobs].map(job => (
                                <tr key={job.id} className="border-b border-gray-800 hover:bg-gray-800/50">
                                    <td className="py-3 px-4">{job.name}</td>
                                    <td className="py-3 px-4 text-gray-400">{job.type}</td>
                                    <td className="py-3 px-4 text-center">{job.estimatedDuration}</td>
                                    <td className="py-3 px-4 text-center">{job.estimatedKwh}</td>
                                    <td className="py-3 px-4 text-center">
                                        <span className={`text-xs font-bold ${job.deferrable ? 'text-green-400' : 'text-red-400'}`}>
                                            {job.deferrable ? '✓' : '✗'}
                                        </span>
                                    </td>
                                    <td className="py-3 px-4 text-center">
                                        <span className={`${getJobStatus(job)} px-2 py-1 rounded text-xs font-bold capitalize`}>
                                            {job.status}
                                        </span>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};

export default CarbonClockDashboard;
