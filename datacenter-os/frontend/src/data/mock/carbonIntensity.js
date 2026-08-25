// Mock ElectricityMaps API responses for carbon intensity
const generateIntensity = () => {
    // Simulate realistic daily pattern: low at night, peaks mid-day
    const hour = new Date().getHours();
    const baseTrend = Math.sin((hour - 6) * Math.PI / 12) * 150 + 200; // 50-350 baseline
    const noise = (Math.random() - 0.5) * 50;
    const intensity = Math.max(50, Math.min(400, baseTrend + noise));
    
    return {
        carbonIntensity: Math.round(intensity),
        datetime: new Date().toISOString(),
        zone: 'IN-SO',
        status: 'real',
        lastUpdated: new Date().toISOString()
    };
};

export const jobQueue = [
    { id: 'backup-1', name: 'Database Backup', type: 'backup', deferrable: true, estimatedDuration: 120, estimatedKwh: 50, createdAt: new Date(Date.now() - 10 * 60000), status: 'pending' },
    { id: 'etl-2', name: 'Batch ETL Job', type: 'batch_etl', deferrable: true, estimatedDuration: 240, estimatedKwh: 200, createdAt: new Date(Date.now() - 5 * 60000), status: 'pending' },
    { id: 'train-1', name: 'Model Training', type: 'model_training', deferrable: true, estimatedDuration: 360, estimatedKwh: 500, createdAt: new Date(Date.now() - 2 * 60000), status: 'pending' },
    { id: 'archive-1', name: 'Log Archival', type: 'log_archival', deferrable: true, estimatedDuration: 60, estimatedKwh: 20, createdAt: new Date(), status: 'pending' },
];

let currentIntensity = generateIntensity();
let subscribers = [];
let deferredJobs = [];
let executedJobs = [];

// Simulate job execution
const processJobs = (intensity) => {
    const newQueue = [...jobQueue];
    const newDeferred = [...deferredJobs];
    
    // Check if any deferred jobs should now run (carbon intensity dropped)
    deferredJobs = deferredJobs.filter(job => {
        if (intensity < 200) {
            // Carbon intensity is good, execute deferred job
            executedJobs.push({ ...job, executedAt: new Date().toISOString() });
            return false;
        }
        return true;
    });
};

const fluctuate = () => {
    const oldIntensity = currentIntensity.carbonIntensity;
    currentIntensity = generateIntensity();
    
    // Simulate Job scheduling logic
    if (currentIntensity.carbonIntensity > 300) {
        // High carbon intensity - defer jobs
        jobQueue.forEach(job => {
            if (job.deferrable && job.status === 'pending' && Math.random() < 0.3) {
                job.status = 'deferred';
                deferredJobs.push({ ...job, deferredAt: new Date().toISOString() });
            }
        });
    } else if (currentIntensity.carbonIntensity < 200) {
        // Low carbon intensity - run deferred jobs
        deferredJobs.forEach(job => {
            job.status = 'executing';
            executedJobs.push({ ...job, executedAt: new Date().toISOString() });
        });
        deferredJobs = [];
    }
    
    subscribers.forEach(cb => cb({
        intensity: currentIntensity,
        jobs: jobQueue,
        deferredJobs: deferredJobs,
        executedJobs: executedJobs
    }));
};

export const carbonIntensityApi = {
    getSnapshot: () => ({
        intensity: currentIntensity,
        jobs: jobQueue,
        deferredJobs: deferredJobs,
        executedJobs: executedJobs
    }),
    subscribe: (callback, intervalMs = 5000) => {
        subscribers.push(callback);
        callback({
            intensity: currentIntensity,
            jobs: jobQueue,
            deferredJobs: deferredJobs,
            executedJobs: executedJobs
        });
        const timer = setInterval(fluctuate, intervalMs);
        return () => {
            clearInterval(timer);
            subscribers = subscribers.filter(s => s !== callback);
        };
    }
};
