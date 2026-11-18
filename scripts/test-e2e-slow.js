const { spawnSync } = require('node:child_process');
const path = require('node:path');

const projectRoot = path.resolve(__dirname, '..');
const playwrightCli = path.join(projectRoot, 'node_modules', '@playwright', 'test', 'cli.js');
const result = spawnSync(
  process.execPath,
  [playwrightCli, 'test', '--headed', '--workers=1'],
  {
    cwd: projectRoot,
    env: { ...process.env, PLAYWRIGHT_SLOW_MO: '700' },
    stdio: 'inherit',
  },
);

if (result.error) throw result.error;
process.exit(result.status === null ? 1 : result.status);
