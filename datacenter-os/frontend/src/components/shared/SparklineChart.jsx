import React from 'react';
import { AreaChart, Area, ResponsiveContainer, YAxis } from 'recharts';

const SparklineChart = ({ data, dataKey, color = "var(--accent-green)" }) => {
    return (
        <div className="h-20 w-full mt-4 transform-gpu">
            <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data}>
                    <defs>
                        <linearGradient id={`glow-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor={color} stopOpacity={0.2} />
                            <stop offset="100%" stopColor={color} stopOpacity={0} />
                        </linearGradient>
                    </defs>
                    <YAxis domain={['auto', 'auto']} hide />
                    <Area 
                        type="monotone" 
                        dataKey={dataKey} 
                        stroke={color} 
                        strokeWidth={1} 
                        fill={`url(#glow-${dataKey})`}
                        dot={false}
                        isAnimationActive={true}
                        animationDuration={2000}
                    />
                </AreaChart>
            </ResponsiveContainer>
        </div>
    );
};

export default SparklineChart;
