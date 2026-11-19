import { expect, test } from '@playwright/test';
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';

const emailDir = resolve(__dirname, '..', '.playwright-emails');

function latestResetCode(email: string): string | undefined {
  if (!existsSync(emailDir)) return undefined;
  const files = readdirSync(emailDir)
    .map((name) => join(emailDir, name))
    .sort((a, b) => statSync(b).mtimeMs - statSync(a).mtimeMs);
  for (const file of files) {
    const content = readFileSync(file, 'utf8');
    if (!content.includes(`To: ${email}`)) continue;
    const match = content.match(/FitMeal của bạn là: (\d{6})/);
    if (match) return match[1];
  }
  return undefined;
}

test('quên mật khẩu: nhận mã OTP qua email rồi đặt mật khẩu mới', async ({ page }) => {
  const email = 'playwright.forgot@example.com';
  const oldPassword = 'E2e-Old-Password-2026!';
  const newPassword = 'E2e-New-Password-2026!';

  await test.step('Tạo tài khoản rồi đăng xuất', async () => {
    await page.goto('/account/#register');
    const registrationForm = page.locator('[data-account-form="register"]');
    await registrationForm.locator('[name="name"]').fill('Khách Quên Mật Khẩu');
    await registrationForm.locator('[name="email"]').fill(email);
    await registrationForm.locator('[name="phone"]').fill('0905550002');
    await registrationForm.locator('[name="password"]').fill(oldPassword);
    await registrationForm.locator('[name="password_confirm"]').fill(oldPassword);
    await registrationForm.getByRole('button', { name: 'Tạo tài khoản' }).click();
    await expect(page).toHaveURL(/\/$/);
    await page.context().clearCookies();
  });

  await test.step('Bấm "Quên mật khẩu?" và nhập email', async () => {
    await page.goto('/account/');
    await page.locator('[data-forgot-password-link]').click();
    const requestForm = page.locator('[data-password-reset-request]');
    await expect(requestForm).toBeVisible();
    await requestForm.locator('[name="email"]').fill(email);
    await requestForm.getByRole('button', { name: 'Gửi mã xác nhận' }).click();
    await expect(page.locator('[data-password-reset-confirm]')).toBeVisible();
    await expect(page.locator('.account-messages')).toContainText('mã xác nhận đã được gửi');
  });

  await test.step('Nhập mã OTP và mật khẩu mới', async () => {
    await expect.poll(() => latestResetCode(email)).toMatch(/^\d{6}$/);
    const code = latestResetCode(email)!;
    const confirmForm = page.locator('[data-password-reset-confirm]');
    await confirmForm.locator('[name="code"]').fill(code);
    await confirmForm.locator('[name="new_password1"]').fill(newPassword);
    await confirmForm.locator('[name="new_password2"]').fill(newPassword);
    await confirmForm.getByRole('button', { name: 'Đặt lại mật khẩu' }).click();
    await expect(page.locator('.account-messages')).toContainText('Đặt lại mật khẩu thành công');
  });

  await test.step('Đăng nhập bằng mật khẩu mới', async () => {
    const loginForm = page.locator('[data-account-form="login"]');
    await loginForm.locator('[name="login"]').fill(email);
    await loginForm.locator('[name="password"]').fill(newPassword);
    await loginForm.getByRole('button', { name: 'Đăng nhập' }).click();
    await expect(page).toHaveURL(/\/$/);
    await page.goto('/account/');
    await expect(page.locator('[data-account-profile]')).toContainText(email);
  });
});
