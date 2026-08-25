import fs from 'fs/promises';

// ─── Simple static-analysis rules ──────────────────────────────────────────
// Each rule scans the file's lines and returns an array of findings.
// Kept intentionally lightweight (no AST parsing) so this has zero deps.

const RULES = [
  {
    id: 'no-console',
    pattern: /\bconsole\.(log|debug)\s*\(/,
    message: 'console.log/debug left in code',
    severity: 'warning',
  },
  {
    id: 'no-debugger',
    pattern: /\bdebugger\b/,
    message: 'debugger statement left in code',
    severity: 'error',
  },
  {
    id: 'todo-comment',
    pattern: /\/\/\s*(TODO|FIXME)/i,
    message: 'unresolved TODO/FIXME comment',
    severity: 'info',
  },
];

const MAX_LINE_LENGTH = 120;

function analyzeSource(source) {
  const lines = source.split('\n');
  const findings = [];

  lines.forEach((line, idx) => {
    const lineNumber = idx + 1;

    if (line.length > MAX_LINE_LENGTH) {
      findings.push({ line: lineNumber, rule: 'long-line', message: `line exceeds ${MAX_LINE_LENGTH} characters`, severity: 'info' });
    }

    for (const rule of RULES) {
      if (rule.pattern.test(line)) {
        findings.push({ line: lineNumber, rule: rule.id, message: rule.message, severity: rule.severity });
      }
    }
  });

  return {
    totalLines: lines.length,
    findings,
    errorCount: findings.filter(f => f.severity === 'error').length,
    warningCount: findings.filter(f => f.severity === 'warning').length,
    infoCount: findings.filter(f => f.severity === 'info').length,
  };
}

export default {
  name: 'codeRabbit',
  init(app) {
    console.log(`Plugin '${this.name}' initialized.`);
    this.app = app;
  },

  /**
   * @param {object} input
   * @param {string} [input.filePath] - Path to a JS/JSX file to analyze.
   *   If omitted, returns a message describing how to use the plugin
   *   rather than performing an analysis (there is nothing to analyze).
   */
  async execute(input) {
    const filePath = input?.filePath;

    if (!filePath) {
      return {
        status: 'skipped',
        type: 'feedback',
        message: 'codeRabbit requires input.filePath pointing at a file to analyze.',
      };
    }

    let source;
    try {
      source = await fs.readFile(filePath, 'utf-8');
    } catch (error) {
      return {
        status: 'error',
        type: 'feedback',
        message: `Could not read file at ${filePath}: ${error.message}`,
      };
    }

    const analysis = analyzeSource(source);

    return {
      status: 'analysis_done',
      type: 'feedback',
      filePath,
      message: analysis.findings.length === 0
        ? `No issues found in ${filePath} (${analysis.totalLines} lines).`
        : `Found ${analysis.findings.length} issue(s) in ${filePath}: ${analysis.errorCount} error(s), ${analysis.warningCount} warning(s), ${analysis.infoCount} info.`,
      analysis,
    };
  },
};
