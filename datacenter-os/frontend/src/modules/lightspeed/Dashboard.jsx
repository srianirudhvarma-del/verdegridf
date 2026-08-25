import React, { useState, useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { networkTrafficApi } from '../../data/mock/networkTraffic';
import MetricCard from '../../components/shared/MetricCard';
import AlertBadge from '../../components/shared/AlertBadge';

const LightSpeedDashboard = () => {
    const [networkData, setNetworkData] = useState(null);
    const [bottlenecks, setBottlenecks] = useState([]);
    const [suggestedReroutes, setSuggestedReroutes] = useState([]);
    const [maxUtilization, setMaxUtilization] = useState(0);
    const svgRef = useRef(null);

    // D3 graph rendering
    useEffect(() => {
        if (!networkData || !svgRef.current) return;

        const width = svgRef.current.clientWidth;
        const height = 600;

        // Clear previous svg
        d3.select(svgRef.current).selectAll("*").remove();

        // Create simulation
        const simulation = d3.forceSimulation(networkData.nodes)
            .force('link', d3.forceLink(networkData.links).id(d => d.id).distance(150))
            .force('charge', d3.forceManyBody().strength(-400))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('collide', d3.forceCollide(50));

        // Create SVG
        const svg = d3.select(svgRef.current)
            .attr('viewBox', `0 0 ${width} ${height}`)
            .attr('width', '100%')
            .attr('height', height);

        // Add defs for gradients
        const defs = svg.append('defs');
        networkData.links.forEach((d, i) => {
            defs.append('linearGradient')
                .attr('id', `gradient-${i}`)
                .attr('gradientUnits', 'userSpaceOnUse')
                .append('stop')
                .attr('stop-color', d.utilization_percent > 85 ? '#ef4444' : d.utilization_percent > 60 ? '#f59e0b' : '#10b981')
                .attr('stop-opacity', 0.8);
        });

        // Create link elements (edges)
        const links = svg.append('g')
            .selectAll('line')
            .data(networkData.links)
            .enter()
            .append('line')
            .attr('stroke', (d, i) => d.utilization_percent > 85 ? '#ef4444' : d.utilization_percent > 60 ? '#f59e0b' : '#10b981')
            .attr('stroke-width', d => Math.max(2, (d.utilization_percent / 100) * 15))
            .attr('stroke-opacity', 0.8)
            .attr('class', 'transition-all');

        // Create node elements (racks)
        const nodes = svg.append('g')
            .selectAll('circle')
            .data(networkData.nodes)
            .enter()
            .append('circle')
            .attr('r', 40)
            .attr('fill', '#1f2937')
            .attr('stroke', '#10b981')
            .attr('stroke-width', 2)
            .call(d3.drag()
                .on('start', dragStarted)
                .on('drag', dragged)
                .on('end', dragEnded));

        // Add labels
        const labels = svg.append('g')
            .selectAll('text')
            .data(networkData.nodes)
            .enter()
            .append('text')
            .text(d => d.id.replace('Node', ''))
            .attr('font-size', '16px')
            .attr('font-weight', 'bold')
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', '#fff');

        // Update positions on simulation tick
        simulation.on('tick', () => {
            links
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);

            nodes
                .attr('cx', d => d.x)
                .attr('cy', d => d.y);

            labels
                .attr('x', d => d.x)
                .attr('y', d => d.y);
        });

        function dragStarted(event, d) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }

        function dragged(event, d) {
            d.fx = event.x;
            d.fy = event.y;
        }

        function dragEnded(event, d) {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }

        return () => simulation.stop();
    }, [networkData]);

    useEffect(() => {
        const unsubscribe = networkTrafficApi.subscribe((data) => {
            setNetworkData(data);

            // Find bottlenecks (links with > 80% utilization)
            const bottleneckLinks = data.links.filter(link => link.utilization_percent > 80);
            setBottlenecks(bottleneckLinks);

            // Calculate max utilization
            const maxUtil = Math.max(...data.links.map(l => l.utilization_percent));
            setMaxUtilization(maxUtil);

            // Suggest reroutes for congested links
            const suggestions = bottleneckLinks.map(link => ({
                source: link.source.id || link.source,
                target: link.target.id || link.target,
                currentUtil: link.utilization_percent,
                action: link.utilization_percent > 90 
                    ? 'REROUTE IMMEDIATELY' 
                    : 'Consider alternative paths'
            }));
            setSuggestedReroutes(suggestions);
        }, 2000);

        return () => unsubscribe();
    }, []);

    if (!networkData) return <div className="p-8 text-white">Loading network graph...</div>;

    return (
        <div className="p-8 bg-black min-h-screen text-white font-sans overflow-auto h-full">
            <header className="mb-8 flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-black tracking-tight text-yellow-400 mb-2">LightSpeed</h1>
                    <p className="text-gray-400">Inter-rack fiber network latency and utilization optimization.</p>
                </div>
                <button 
                    onClick={() => networkTrafficApi.injectSpike(Math.floor(Math.random() * networkData.links.length))}
                    className="bg-yellow-600 hover:bg-yellow-500 px-4 py-2 rounded-lg font-bold text-sm transition-colors"
                >
                    Inject Traffic Spike
                </button>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <MetricCard 
                    title="Max Link Utilization" 
                    value={maxUtilization.toFixed(1)} 
                    unit="%"
                    trend={maxUtilization > 50 ? 1 : 0}
                />
                <MetricCard 
                    title="Bottleneck Links" 
                    value={bottlenecks.length} 
                    subtext={bottlenecks.length > 3 ? 'Network stress!' : 'Nominal'}
                />
                <MetricCard 
                    title="Total Nodes" 
                    value={networkData.nodes.length} 
                />
            </div>

            {bottlenecks.length > 0 && (
                <AlertBadge 
                    level={bottlenecks.some(b => b.utilization_percent > 90) ? 'critical' : 'warning'}
                    message={`⚠️  ${bottlenecks.length} link(s) experiencing high utilization. Consider rerouting traffic to alternate paths.`}
                />
            )}

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
                {/* D3 Graph */}
                <div className="lg:col-span-2 bg-gray-900 border border-gray-800 rounded-xl p-6">
                    <h3 className="text-lg font-bold mb-4">Network Topology (Force-Directed)</h3>
                    <div className="bg-gray-800 rounded-lg overflow-hidden">
                        <svg 
                            ref={svgRef}
                            style={{ width: '100%', height: '500px', background: '#111827' }}
                        ></svg>
                    </div>
                    <p className="text-xs text-gray-400 mt-3">
                        🟢 Green (0-60%) | 🟡 Yellow (60-85%) | 🔴 Red (85-100%)
                    </p>
                </div>

                {/* Suggested Reroutes */}
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 flex flex-col h-full">
                    <h3 className="text-lg font-bold mb-4">Rerouting Suggestions</h3>
                    <div className="flex-1 overflow-y-auto space-y-3 pr-2">
                        {suggestedReroutes.length === 0 ? (
                            <div className="text-gray-500 text-center py-8">
                                <div className="text-sm">Network operating normally</div>
                                <div className="text-xs text-gray-600 mt-2">No rerouting needed</div>
                            </div>
                        ) : (
                            suggestedReroutes.map((route, i) => (
                                <div key={i} className={`p-3 rounded-lg border ${route.currentUtil > 90 ? 'bg-red-900/30 border-red-700/30' : 'bg-yellow-900/30 border-yellow-700/30'}`}>
                                    <div className="font-bold text-sm">
                                        {route.currentUtil > 90 ? '🔴' : '🟡'} {route.source} → {route.target}
                                    </div>
                                    <div className="text-xs text-gray-300 mt-1">
                                        Utilization: {route.currentUtil.toFixed(1)}%
                                    </div>
                                    <div className={`text-xs font-bold mt-2 ${route.currentUtil > 90 ? 'text-red-400' : 'text-yellow-400'}`}>
                                        {route.action}
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>

            {/* Link Details Table */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                <h3 className="text-lg font-bold mb-6">Link Utilization Details</h3>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead className="border-b border-gray-700">
                            <tr className="text-gray-400 text-xs uppercase">
                                <th className="text-left py-3 px-4">Source</th>
                                <th className="text-left py-3 px-4">Target</th>
                                <th className="text-center py-3 px-4">Capacity (Gbps)</th>
                                <th className="text-center py-3 px-4">Utilization (%)</th>
                                <th className="text-center py-3 px-4">Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {networkData.links.map((link, i) => (
                                <tr key={i} className="border-b border-gray-800 hover:bg-gray-800/50">
                                    <td className="py-3 px-4">{link.source.id || link.source}</td>
                                    <td className="py-3 px-4">{link.target.id || link.target}</td>
                                    <td className="py-3 px-4 text-center">{link.capacity_gbps}</td>
                                    <td className="py-3 px-4 text-center">
                                        <div className="flex items-center gap-2 justify-center">
                                            <div className="w-16 bg-gray-800 rounded h-2">
                                                <div 
                                                    className={`h-2 rounded transition-all ${link.utilization_percent > 85 ? 'bg-red-500' : link.utilization_percent > 60 ? 'bg-yellow-500' : 'bg-green-500'}`}
                                                    style={{ width: `${link.utilization_percent}%` }}
                                                ></div>
                                            </div>
                                            <span>{link.utilization_percent.toFixed(1)}%</span>
                                        </div>
                                    </td>
                                    <td className="py-3 px-4 text-center">
                                        <span className={`px-2 py-1 rounded text-xs font-bold ${link.utilization_percent > 85 ? 'bg-red-900/50 text-red-300' : link.utilization_percent > 60 ? 'bg-yellow-900/50 text-yellow-300' : 'bg-green-900/50 text-green-300'}`}>
                                            {link.utilization_percent > 85 ? 'Critical' : link.utilization_percent > 60 ? 'Warning' : 'Normal'}
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

export default LightSpeedDashboard;
