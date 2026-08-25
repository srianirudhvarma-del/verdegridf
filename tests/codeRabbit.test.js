import { test } from 'node:test';
import assert from 'node:assert/strict';
import path from 'path';
import { fileURLToPath } from 'url';
import codeRabbit from '../plugins/codeRabbit/index.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

test('codeRabbit returns "skipped" when no filePath is given', async () => {
  const result = await codeRabbit.execute({ message: 'no file here' });
  assert.equal(result.status, 'skipped');
});

test('codeRabbit reports a clear error for a missing file', async () => {
  const result = await codeRabbit.execute({ filePath: path.join(__dirname, 'fixtures', 'does-not-exist.js') });
  assert.equal(result.status, 'error');
  assert.match(result.message, /Could not read file/);
});

test('codeRabbit flags console.log, debugger, and TODO comments in a real file', async () => {
  const filePath = path.join(__dirname, 'fixtures', 'sample-for-analysis.js');
  const result = await codeRabbit.execute({ filePath });

  assert.equal(result.status, 'analysis_done');
  const ruleIds = result.analysis.findings.map(f => f.rule);

  assert.ok(ruleIds.includes('no-console'), 'should flag console.log');
  assert.ok(ruleIds.includes('no-debugger'), 'should flag debugger statement');
  assert.ok(ruleIds.includes('todo-comment'), 'should flag TODO comment');
  assert.equal(result.analysis.errorCount, 1, 'debugger is severity: error');
  assert.equal(result.analysis.warningCount, 1, 'console.log is severity: warning');
});

test('codeRabbit reports zero findings for clean code', async () => {
  const filePath = path.join(__dirname, 'fixtures', 'plugins-ok', 'goodPlugin', 'index.js');
  const result = await codeRabbit.execute({ filePath });

  assert.equal(result.status, 'analysis_done');
  assert.equal(result.analysis.findings.length, 0);
  assert.match(result.message, /No issues found/);
});
