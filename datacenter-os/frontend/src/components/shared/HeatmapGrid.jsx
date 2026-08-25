import React from 'react';

const HeatmapGrid = ({ title, gridData, renderCell }) => {
    return (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 flex flex-col h-full">
            <h3 className="text-lg font-bold mb-4">{title}</h3>
            <div className="flex-1 grid grid-cols-8 gap-1">
                {gridData.map((cell, idx) => renderCell(cell, idx))}
            </div>
        </div>
    );
};

export default HeatmapGrid;
