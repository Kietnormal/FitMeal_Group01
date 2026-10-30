const demoProducts = {
  "banana-whey": { name: "Banana Whey", price: 59000, category: "drink", description: "Chuối · Sữa tươi · Whey", icon: "🍌" },
  "mocha-whey": { name: "Mocha Cafe Whey", price: 65000, category: "drink", description: "Cafe · Cacao · Chuối · Whey", icon: "✳" },
  "berry-protein": { name: "Berry Protein", price: 62000, category: "drink", description: "Dâu tây · Sữa chua · Whey", icon: "✿" },
  "chicken-sous-vide": { name: "Ức gà Sous-vide", price: 89000, category: "meal", description: "Ức gà · Tiêu đen thảo mộc", icon: "F" },
  "protein-brownie": { name: "Protein Brownie", price: 39000, category: "snack", description: "Cacao · Yến mạch · Whey", icon: "FM" },
  "granola-crunch": { name: "Granola Crunch", price: 45000, category: "snack", description: "Yến mạch · Hạt · Mật ong", icon: "FM" },
};

const cartStorageKey = "fitmeal-demo-cart";
const currency = new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND", maximumFractionDigits: 0 });

function readCart() {
  try {
    const saved = JSON.parse(localStorage.getItem(cartStorageKey) || "[]");
    if (!Array.isArray(saved)) {
      throw new TypeError("Giỏ hàng minh họa không đúng định dạng.");
    }

    return saved
      .filter((item) => item && demoProducts[item.id] && Number.isInteger(item.quantity) && item.quantity > 0)
      .map((item) => ({ id: item.id, quantity: item.quantity }));
  } catch (error) {
    console.error("Không thể đọc giỏ hàng minh họa trong trình duyệt.", error);
    return [];
  }
}

function writeCart(cart) {
  localStorage.setItem(cartStorageKey, JSON.stringify(cart));
  updateCartCounts(cart);
}

function updateCartCounts(cart = readCart()) {
  const count = cart.reduce((sum, item) => sum + item.quantity, 0);
  document.querySelectorAll("[data-cart-count]").forEach((badge) => {
    badge.textContent = String(count);
  });
}

function showToast(message) {
  const toast = document.querySelector("[data-toast]");
  if (!toast) return;

  toast.textContent = message;
  toast.classList.add("is-visible");
  window.clearTimeout(showToast.timeoutId);
  showToast.timeoutId = window.setTimeout(() => toast.classList.remove("is-visible"), 2400);
}

function renderCart() {
  const cartItems = document.querySelector("[data-cart-items]");
  const checkoutItems = document.querySelector("[data-checkout-items]");
  if (!cartItems && !checkoutItems) return;

  const cart = readCart();
  const subtotal = cart.reduce((sum, item) => sum + demoProducts[item.id].price * item.quantity, 0);
  const lineCount = cart.reduce((sum, item) => sum + item.quantity, 0);

  document.querySelectorAll("[data-cart-subtotal]").forEach((element) => {
    element.textContent = currency.format(subtotal);
  });
  document.querySelectorAll("[data-cart-total]").forEach((element) => {
    element.textContent = currency.format(subtotal);
  });
  document.querySelectorAll("[data-cart-line-count]").forEach((element) => {
    element.textContent = `${lineCount} món`;
  });
  document.querySelectorAll("[data-shipping-fee]").forEach((element) => {
    element.textContent = cart.length ? "Tính sau" : "—";
  });

  const emptyState = document.querySelector("[data-cart-empty]");
  if (emptyState) emptyState.hidden = cart.length > 0;
  if (cartItems) {
    cartItems.replaceChildren();
    cartItems.hidden = cart.length === 0;
    cart.forEach((item) => {
      const product = demoProducts[item.id];
      const row = document.createElement("article");
      row.className = "cart-line";
      row.innerHTML = `
        <div class="cart-line-info">
          <span class="mini-product-art" data-category="${product.category}" aria-hidden="true">${product.icon}</span>
          <div><h3></h3><p></p></div>
        </div>
        <div class="quantity-control" aria-label="Số lượng">
          <button type="button" data-cart-change="-1" data-product-id="${item.id}" aria-label="Giảm số lượng">−</button>
          <span>${item.quantity}</span>
          <button type="button" data-cart-change="1" data-product-id="${item.id}" aria-label="Tăng số lượng">＋</button>
        </div>
        <strong class="cart-line-price">${currency.format(product.price * item.quantity)}</strong>
        <button class="remove-item" type="button" data-cart-remove="${item.id}" aria-label="Xóa ${product.name}">×</button>`;
      row.querySelector("h3").textContent = product.name;
      row.querySelector(".cart-line-info p").textContent = product.description;
      cartItems.append(row);
    });

    const checkoutLink = document.querySelector("[data-checkout-link]");
    if (checkoutLink) {
      checkoutLink.setAttribute("aria-disabled", String(cart.length === 0));
      checkoutLink.setAttribute("tabindex", cart.length ? "0" : "-1");
    }
  }

  if (checkoutItems) {
    checkoutItems.replaceChildren();
    cart.forEach((item) => {
      const product = demoProducts[item.id];
      const row = document.createElement("div");
      row.className = "checkout-item";
      const name = document.createElement("span");
      name.textContent = `${product.name} × ${item.quantity}`;
      const price = document.createElement("span");
      price.textContent = currency.format(product.price * item.quantity);
      row.append(name, price);
      checkoutItems.append(row);
    });
    if (!cart.length) {
      const emptyMessage = document.createElement("p");
      emptyMessage.className = "checkout-item";
      emptyMessage.textContent = "Chưa có sản phẩm trong giỏ.";
      checkoutItems.append(emptyMessage);
    }
  }
}

function initializeCatalog() {
  const productGrid = document.querySelector("[data-product-grid]");
  if (!productGrid) return;

  let selectedCategory = "all";
  const search = document.querySelector("[data-product-search]");
  const sort = document.querySelector("[data-product-sort]");
  const emptyResults = document.querySelector("[data-empty-results]");
  const products = [...productGrid.querySelectorAll("[data-product]")];

  function filterProducts() {
    const searchTerm = search.value.trim().toLocaleLowerCase("vi");
    products.forEach((product) => {
      const matchesCategory = selectedCategory === "all" || product.dataset.category === selectedCategory;
      const matchesSearch = `${product.dataset.name} ${product.dataset.search}`.toLocaleLowerCase("vi").includes(searchTerm);
      product.hidden = !(matchesCategory && matchesSearch);
    });
    emptyResults.hidden = products.some((product) => !product.hidden);

    const sortOrder = sort.value;
    const orderedProducts = [...products];
    if (sortOrder !== "featured") {
      orderedProducts.sort((left, right) => {
        const difference = Number(left.dataset.price) - Number(right.dataset.price);
        return sortOrder === "price-desc" ? -difference : difference;
      });
    }
    orderedProducts.forEach((product) => productGrid.append(product));
  }

  document.querySelectorAll(".filter-chip[data-category]").forEach((button) => {
    button.addEventListener("click", () => {
      selectedCategory = button.dataset.category;
      document.querySelectorAll(".filter-chip").forEach((chip) => {
        chip.classList.toggle("is-active", chip === button);
      });
      filterProducts();
    });
  });

  search.addEventListener("input", filterProducts);
  sort.addEventListener("change", filterProducts);
  productGrid.addEventListener("click", (event) => {
    const button = event.target.closest("[data-add-to-cart]");
    if (!button) return;

    const productCard = button.closest("[data-product]");
    const cart = readCart();
    const existing = cart.find((item) => item.id === productCard.dataset.id);
    if (existing) existing.quantity += 1;
    else cart.push({ id: productCard.dataset.id, quantity: 1 });
    writeCart(cart);
    showToast(`${productCard.dataset.name} đã được thêm vào giỏ.`);
  });
}

function initializeCart() {
  const cartItems = document.querySelector("[data-cart-items]");
  if (!cartItems) return;

  cartItems.addEventListener("click", (event) => {
    const removeButton = event.target.closest("[data-cart-remove]");
    const changeButton = event.target.closest("[data-cart-change]");
    const productId = removeButton?.dataset.cartRemove || changeButton?.dataset.productId;
    if (!productId) return;

    let cart = readCart();
    if (removeButton) {
      cart = cart.filter((item) => item.id !== productId);
    } else {
      const item = cart.find((entry) => entry.id === productId);
      if (item) item.quantity += Number(changeButton.dataset.cartChange);
      cart = cart.filter((entry) => entry.quantity > 0);
    }
    writeCart(cart);
    renderCart();
  });

  document.querySelector("[data-checkout-link]")?.addEventListener("click", (event) => {
    if (!readCart().length) {
      event.preventDefault();
      showToast("Thêm ít nhất một món vào giỏ trước nhé.");
    }
  });
}

function initializeCheckout() {
  const form = document.querySelector("[data-checkout-form]");
  if (!form) return;

  const modal = document.querySelector("[data-order-modal]");
  const closeModal = () => {
    modal.hidden = true;
    document.querySelector("[data-checkout-form] input")?.focus();
  };

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!readCart().length) {
      showToast("Giỏ hàng đang trống. Hãy thêm sản phẩm trước khi đặt.");
      return;
    }

    const orderId = `FM-DEMO-${Date.now().toString().slice(-6)}`;
    localStorage.setItem("fitmeal-demo-last-order", orderId);
    document.querySelector("[data-demo-order-id]").textContent = orderId;
    modal.hidden = false;
    writeCart([]);
    renderCart();
    document.querySelector("[data-close-modal]").focus();
  });

  document.querySelector("[data-close-modal]").addEventListener("click", closeModal);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeModal();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) closeModal();
  });
}

function initializeTracking() {
  const form = document.querySelector("[data-tracking-form]");
  if (!form) return;

  const lastDemoOrder = localStorage.getItem("fitmeal-demo-last-order");
  if (lastDemoOrder) form.elements.order.value = lastDemoOrder;

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const orderId = new FormData(form).get("order").toString().trim();
    if (!orderId) return;
    document.querySelector("[data-tracking-order]").textContent = orderId;
    showToast("Đang hiển thị tiến trình đơn hàng mẫu.");
  });
}

function initializeAccount() {
  const tabs = document.querySelectorAll("[data-account-tab]");
  if (!tabs.length) return;

  function activateAccountTab(activeForm) {
    tabs.forEach((tab) => {
      const isActive = tab.dataset.accountTab === activeForm;
      tab.classList.toggle("is-active", isActive);
      tab.setAttribute("aria-selected", String(isActive));
    });
    document.querySelectorAll("[data-account-form]").forEach((form) => {
      form.hidden = form.dataset.accountForm !== activeForm;
    });
  }

  const initialTab = window.location.hash === "#register" ? "register" : "login";
  activateAccountTab(initialTab);

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const activeForm = tab.dataset.accountTab;
      activateAccountTab(activeForm);
      window.history.replaceState(null, "", `#${activeForm}`);
    });
  });

  document.querySelectorAll("[data-account-form]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const feedback = form.querySelector("[data-account-feedback]");
      feedback.textContent = "Đây là prototype giao diện; chức năng tài khoản chưa được kết nối.";
    });
  });

  document.querySelector("[data-account-forgot]")?.addEventListener("click", () => {
    document.querySelector('[data-account-form="login"] [data-account-feedback]').textContent =
      "Chức năng khôi phục mật khẩu sẽ được kết nối khi triển khai backend.";
  });
}

function initializeAdmin() {
  const tabs = document.querySelectorAll("[data-admin-tab]");
  if (!tabs.length) return;

  const toast = document.querySelector("[data-admin-toast]");
  function notify(message) {
    toast.textContent = message;
    toast.classList.add("is-visible");
    window.clearTimeout(notify.timeoutId);
    notify.timeoutId = window.setTimeout(() => toast.classList.remove("is-visible"), 2400);
  }

  function activateTab(name) {
    tabs.forEach((tab) => tab.classList.toggle("is-active", tab.dataset.adminTab === name));
    document.querySelectorAll("[data-admin-view]").forEach((view) => {
      const isActive = view.dataset.adminView === name;
      view.classList.toggle("is-active", isActive);
      view.hidden = !isActive;
    });
    document.querySelector(".admin-topbar h1").textContent = {
      overview: "Bảng điều khiển",
      orders: "Đơn hàng",
      products: "Sản phẩm",
      customers: "Khách hàng",
      payments: "Thanh toán",
      shipping: "Vận chuyển",
      security: "Bảo mật",
      operations: "Vận hành hệ thống",
    }[name];
  }

  tabs.forEach((tab) => tab.addEventListener("click", () => activateTab(tab.dataset.adminTab)));
  document.querySelectorAll("[data-open-tab]").forEach((button) => {
    button.addEventListener("click", () => activateTab(button.dataset.openTab));
  });
  document.querySelectorAll("[data-admin-search]").forEach((input) => {
    input.addEventListener("input", () => {
      const term = input.value.trim().toLocaleLowerCase("vi");
      const rows = input.closest(".admin-panel").querySelectorAll("tbody tr");
      rows.forEach((row) => {
        row.hidden = !row.textContent.toLocaleLowerCase("vi").includes(term);
      });
    });
  });
  document.querySelectorAll(".status-select").forEach((select) => {
    select.addEventListener("change", () => notify(`Trạng thái minh họa: ${select.value}. Chưa lưu vào hệ thống.`));
  });
  document.querySelector("[data-demo-action]")?.addEventListener("click", () => {
    notify("Màn hình thêm sản phẩm sẽ được kết nối ở giai đoạn backend.");
  });
}

function initializeMobileNavigation() {
  const toggle = document.querySelector(".store-menu-toggle");
  const navigation = document.querySelector(".store-mobile-nav");
  if (!toggle || !navigation) return;

  toggle.addEventListener("click", () => {
    const isExpanded = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!isExpanded));
    toggle.setAttribute("aria-label", isExpanded ? "Mở điều hướng" : "Đóng điều hướng");
    navigation.classList.toggle("is-open", !isExpanded);
  });
}

function initializeLanguages() {
  document.querySelectorAll("[data-language]").forEach((button) => {
    button.addEventListener("click", () => {
      const languageGroup = button.closest("[aria-label='Ngôn ngữ giao diện']");
      const status = languageGroup?.querySelector("[data-language-status]");
      if (button.dataset.language === "en") {
        if (status) status.textContent = "Phiên bản tiếng Anh chưa có. Giao diện hiện vẫn hiển thị tiếng Việt.";
        return;
      }

      languageGroup.querySelectorAll("[data-language]").forEach((languageButton) => {
        const isActive = languageButton === button;
        languageButton.classList.toggle("is-active", isActive);
        languageButton.setAttribute("aria-pressed", String(isActive));
      });
      if (status) status.textContent = "Giao diện hiện hiển thị tiếng Việt.";
    });
  });
}

updateCartCounts();
renderCart();
initializeCatalog();
initializeCart();
initializeCheckout();
initializeTracking();
initializeAccount();
initializeAdmin();
initializeMobileNavigation();
initializeLanguages();
