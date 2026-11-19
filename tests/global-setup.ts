import { execFileSync } from 'node:child_process';
import { existsSync, rmSync, unlinkSync } from 'node:fs';
import { resolve } from 'node:path';

export default async function globalSetup() {
  const projectRoot = resolve(__dirname, '..');
  const databasePath = resolve(projectRoot, '.playwright-e2e.sqlite3');
  const python = process.env.PYTHON || 'python';

  if (existsSync(databasePath)) {
    unlinkSync(databasePath);
  }
  rmSync(resolve(projectRoot, '.playwright-emails'), { recursive: true, force: true });

  const env = {
    ...process.env,
    DJANGO_SETTINGS_MODULE: 'config.e2e_settings',
  };
  const manage = (args: string[]) => {
    execFileSync(
      python,
      ['manage.py', ...args, '--settings=config.e2e_settings'],
      { cwd: projectRoot, env, stdio: 'inherit' },
    );
  };

  manage(['migrate', '--noinput']);
  manage(['loaddata', 'playwright_catalog']);
}
