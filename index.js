import { PluginManager } from './core/pluginManager.js';

const app = {
  // Application global state or helper functions
  version: '1.0.0',
  data: {},
};

const pluginManager = new PluginManager(app);

async function bootstrap() {
  console.log('--- Initializing Antigravity Plugin Manager ---');
  await pluginManager.loadPlugins('plugins');
}

export async function runPlugins(input) {
  console.log('--- Running Plugins ---');
  const results = await pluginManager.runPlugins(input);
  return results;
}

// Initializing the system
bootstrap().then(() => {
  console.log('--- Antigravity System Ready ---');
  
  // Example usage (can be removed later):
  // filePath lets codeRabbit demonstrate real static analysis on this
  // very file; other plugins just echo the input as before.
  runPlugins({ message: 'Initializing modular system', filePath: './index.js' }).then(results => {
    console.log('Resulting output from all plugins:', results);
  });
}).catch(err => {
  console.error('System initialization failed:', err);
});
