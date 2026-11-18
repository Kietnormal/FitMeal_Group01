import { expect, test } from '@playwright/test';

test('tìm món và quản lý giỏ hàng trên giao diện', async ({ page }) => {
  await test.step('Mở thực đơn và tìm món', async () => {
    await page.goto('/products/');

    const product = page.locator('[data-product][data-name="Playwright Whey"]');
    await expect(product).toBeVisible();

    const search = page.getByRole('searchbox', { name: 'Tìm sản phẩm' });
    await search.fill('Playwright Whey');
    await expect(product).toBeVisible();
    await expect(page.locator('[data-product]:visible')).toHaveCount(1);

    await search.fill('khong-co-mon-nay');
    await expect(page.locator('[data-empty-results]')).toBeVisible();
    await expect(page.locator('[data-product]:visible')).toHaveCount(0);

    await search.clear();
    await expect(product).toBeVisible();
  });

  await test.step('Thêm món và kiểm tra giỏ hàng', async () => {
    await page.locator('[data-product][data-name="Playwright Whey"]')
      .getByRole('button', { name: 'Thêm Playwright Whey vào giỏ' })
      .click();
    await expect(page.locator('[data-cart-drawer]')).toBeVisible();
    await expect(page.locator('[data-cart-drawer] [data-cart-line-count]')).toHaveText('1 món');

    await page.goto('/cart/');
    const cartItems = page.locator('[data-cart-items]');
    await expect(cartItems.getByRole('heading', { name: 'Playwright Whey' })).toBeVisible();
    const subtotal = page.locator('.order-summary [data-cart-subtotal]');
    await expect(subtotal).toContainText('120.000');

    await cartItems.getByRole('button', { name: 'Tăng số lượng' }).click();
    await expect(cartItems.locator('.quantity-control span')).toHaveText('2');
    await expect(subtotal).toContainText('240.000');

    await cartItems.getByRole('button', { name: 'Xóa Playwright Whey' }).click();
    await expect(page.locator('[data-cart-empty]')).toBeVisible();
    await expect(subtotal).toContainText('0');
  });
});

test('đăng ký tài khoản rồi đặt đơn COD', async ({ page }) => {
  const email = 'playwright.customer@example.com';
  const orderName = 'Đơn thử Playwright';

  await test.step('Tạo tài khoản khách hàng', async () => {
    await page.goto('/account/#register');
    const registrationForm = page.locator('[data-account-form="register"]');
    await expect(registrationForm).toBeVisible();
    await registrationForm.locator('[name="name"]').fill('Khách Playwright');
    await registrationForm.locator('[name="email"]').fill(email);
    await registrationForm.locator('[name="phone"]').fill('0905550001');
    await registrationForm.locator('[name="password"]').fill('E2e-Playwright-2026!');
    await registrationForm.locator('[name="password_confirm"]').fill('E2e-Playwright-2026!');
    await registrationForm.getByRole('button', { name: 'Tạo tài khoản' }).click();

    await expect(page).toHaveURL(/\/$/);
    await page.goto('/account/');
    await expect(page.locator('[data-account-profile]')).toBeVisible();
    await expect(page.locator('[data-account-profile]')).toContainText(email);
  });

  await test.step('Thêm món và mở thanh toán', async () => {
    await page.goto('/products/');
    const product = page.locator('[data-product][data-name="Playwright Whey"]');
    await expect(product).toBeVisible();
    await product.getByRole('button', { name: 'Thêm Playwright Whey vào giỏ' }).click();
    await page.locator('[data-cart-drawer] [data-checkout-link]').click();

    await expect(page.locator('[data-checkout-form]')).toBeVisible();
  });

  await test.step('Nhập địa chỉ và đặt đơn COD', async () => {
    const checkoutForm = page.locator('[data-checkout-form]');
    await checkoutForm.locator('[name="address"]').fill('12 Đường Kiểm Thử');
    await checkoutForm.locator('[name="district"]').fill('Quận 1');
    await checkoutForm.locator('[name="city"]').fill('TP Hồ Chí Minh');
    await checkoutForm.locator('[name="note"]').fill(orderName);
    await checkoutForm.locator('[name="accept_policy"]').check();
    await expect(checkoutForm.locator('[name="payment"][value="cod"]')).toBeChecked();

    const orderResponse = page.waitForResponse((response) =>
      response.url().endsWith('/api/orders/')
      && response.request().method() === 'POST'
    );
    await checkoutForm.locator('button[type="submit"]').click();
    const response = await orderResponse;
    expect(response.status()).toBe(201);
    const order = await response.json();
    expect(order.payment_method).toBe('cod');
    expect(order.status).toBe('pending');
    expect(order.order_number).toMatch(/^FM-\d{4}-[A-F0-9]{8}$/);

    await expect(page.locator('[data-checkout-success]')).toBeVisible();
    await page.locator('[data-order-history-link]').click();
    await expect(page.getByRole('heading', { name: 'Đơn hàng của tôi' })).toBeVisible();
    await expect(page.locator('.customer-order-card').first()).toContainText(order.order_number);
  });
});
