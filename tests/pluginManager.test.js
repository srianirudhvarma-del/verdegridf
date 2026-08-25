import { test } from 'node:test';
import assert from 'node:assert/strict';
import path from 'path';
import { fileURLToPath } from 'url';
import { PluginManager } from '../core/pluginManager.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function fixturePath(name) {
  return path.join(__dirname, 'fixtures', name);
}

test('loadPlugins registers a well-formed plugin and calls init()', async () => {
  const app = { version: 'test' };
  const manager = new PluginManager(app);

  await manager.loadPlugins(fixturePath('plugins-ok'));

  const plugin = manager.getPlugin('goodPlugin');
  assert.ok(plugin, 'goodPlugin should be registered');
  assert.equal(plugin.initialized, true, 'init() should have run and set state on the plugin');
});

test('registerPlugin rejects a plugin missing init/execute without throwing', () => {
  const manager = new PluginManager({});
  const malformed = { name: 'badPlugin' }; // no init/execute

  assert.doesNotThrow(() => manager.registerPlugin(malformed));
  assert.equal(manager.getPlugin('badPlugin'), undefined, 'malformed plugin should not be registered');
});

test('loadPlugins isolates a plugin that fails to load and still registers the others', async () => {
  // plugins-invalid contains only a malformed plugin; loadPlugins should not throw,
  // and no plugin should end up registered.
  const manager = new PluginManager({});
  await assert.doesNotReject(() => manager.loadPlugins(fixturePath('plugins-invalid')));
  assert.equal(manager.getPlugin('badPlugin'), undefined);
});

test('runPlugins isolates a plugin whose execute() throws — other plugins still run', async () => {
  const manager = new PluginManager({});
  await manager.loadPlugins(fixturePath('plugins-mixed'));

  assert.ok(manager.getPlugin('goodPlugin'));
  assert.ok(manager.getPlugin('throwingPlugin'));

  const results = await manager.runPlugins({ hello: 'world' });

  assert.equal(results.goodPlugin.ok, true);
  assert.deepEqual(results.goodPlugin.echoed, { hello: 'world' });

  assert.equal(results.throwingPlugin.ok, false);
  assert.match(results.throwingPlugin.error, /deliberate failure/);
});

test('runPlugins wraps non-object plugin return values instead of crashing', async () => {
  const manager = new PluginManager({});
  manager.registerPlugin({
    name: 'primitiveReturner',
    init() {},
    async execute() {
      return 42; // not an object — runPlugins must not try to spread this unsafely
    },
  });

  const results = await manager.runPlugins({});
  assert.equal(results.primitiveReturner.ok, true);
  assert.equal(results.primitiveReturner.result, 42);
});

test('loadPlugins on a nonexistent directory does not throw', async () => {
  const manager = new PluginManager({});
  await assert.doesNotReject(() => manager.loadPlugins(fixturePath('does-not-exist')));
  assert.equal(manager.plugins.size, 0);
});
