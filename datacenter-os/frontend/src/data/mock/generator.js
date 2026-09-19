export function createMockGenerator(initialState, generateUpdate) {
  let state = initialState;
  const subscribers = new Set();
  let intervalId = null;

  const notify = () => {
    subscribers.forEach(callback => callback(state));
  };

  const start = (intervalMs) => {
    if (!intervalId) {
      intervalId = setInterval(() => {
        state = generateUpdate(state);
        notify();
      }, intervalMs);
    }
  };

  const stop = () => {
    if (intervalId) {
      clearInterval(intervalId);
      intervalId = null;
    }
  };

  return {
    getSnapshot: () => state,
    subscribe: (callback, intervalMs = 3000) => {
      subscribers.add(callback);
      if (subscribers.size === 1) {
        start(intervalMs);
      }
      callback(state);
      return () => {
        subscribers.delete(callback);
        if (subscribers.size === 0) stop();
      };
    },
    // Useful for simulating external updates directly
    forceUpdate: (newState) => {
      state = newState;
      notify();
    }
  };
}
