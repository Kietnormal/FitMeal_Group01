const catalogProducts = Object.create(null);
const cartStorageKey = "fitmeal-demo-cart";
const orderStorageKey = "fitmeal-demo-orders";
const currency = new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND", maximumFractionDigits: 0 });
let catalogInventory = [];
let productModalController = null;
let cartDrawerController = null;

function applyInventory(products) {
  catalogInventory = products;
  Object.keys(catalogProducts).forEach((id) => delete catalogProducts[id]);
  products.forEach((product) => {
    catalogProducts[product.id] = product;
  });
}

function categoryName(category) {
  return { dry_goods: "Đồ khô", drink: "Thức uống", meal: "Bữa ăn", snack: "Ăn nhẹ", rice: "Cơm", salad: "Salad", combo: "Combo" }[category];
}

const foodImageBase = document.querySelector("[data-food-images]")?.dataset.foodImages || "/static/img/food/";
const foodImageCategories = ["dry_goods", "drink", "meal", "snack", "rice", "salad", "combo"];

function productFallbackImage(category) {
  return `${foodImageBase}${foodImageCategories.includes(category) ? category : "meal"}.webp`;
}

function productImage(product) {
  return product.image || productFallbackImage(product.category);
}

function fillProductArt(art, product) {
  art.replaceChildren();
  const image = document.createElement("img");
  image.src = productImage(product);
  image.alt = "";
  image.loading = "lazy";
  if (product.image) {
    image.addEventListener("error", () => {
      image.src = productFallbackImage(product.category);
    }, { once: true });
  }
  art.append(image);
}

function getOrders() {
  try {
    const orders = JSON.parse(localStorage.getItem(orderStorageKey) || "[]");
    if (!Array.isArray(orders)) throw new TypeError("Lịch sử đơn demo không đúng định dạng.");
    return orders;
  } catch (error) {
    console.error("Không thể đọc lịch sử đơn demo trong trình duyệt.", error);
    return [];
  }
}

function saveOrders(orders) {
  localStorage.setItem(orderStorageKey, JSON.stringify(orders));
}

function normalizeLocation(value) {
  return value.trim().toLocaleLowerCase("vi")
    .replace(/đ/g, "d")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]/g, "");
}

function isHoChiMinhCity(value) {
  return ["hcm", "tphcm", "tphochiminh", "hochiminh", "thanhphohochiminh", "saigon", "thanhphosaigon", "hochiminhcity"]
    .includes(normalizeLocation(value));
}

function dryGoodsOnly(cart) {
  return cart.length > 0 && cart.every((item) => catalogProducts[item.id]?.category === "dry_goods");
}

function shippingFeeFor(subtotal, cart = readCart(), city = "") {
  if (!subtotal || !cart.length) return 0;
  if (dryGoodsOnly(cart)) {
    const weight = cart.reduce((sum, item) =>
      sum + (catalogProducts[item.id]?.shippingWeightGrams || 0) * item.quantity, 0);
    const local = !city || isHoChiMinhCity(city);
    const base = local ? 20000 : 30000;
    const extra = local ? 5000 : 10000;
    return base + Math.max(0, Math.ceil((weight - 1000) / 500)) * extra;
  }
  return subtotal >= 300000 ? 0 : 20000;
}

// Delivery dates are validated by the server in the shop's timezone (Django TIME_ZONE),
// not the browser's. The checkout template renders the allowed range as data attributes;
// the Intl-based fallback only exists for pages that lack them.
const shopTimeZone = "Asia/Ho_Chi_Minh";

function addDaysToIsoDate(isoDate, days) {
  const [year, month, day] = isoDate.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day + days)).toISOString().slice(0, 10);
}

function shopTodayIsoDate() {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", { timeZone: shopTimeZone, year: "numeric", month: "2-digit", day: "2-digit" })
      .formatToParts(new Date())
      .map((part) => [part.type, part.value]),
  );
  return `${parts.year}-${parts.month}-${parts.day}`;
}

function checkoutDeliveryDateBounds(dateInput) {
  const min = dateInput.dataset.minDate || addDaysToIsoDate(shopTodayIsoDate(), 1);
  const dryGoodsMax = dateInput.dataset.dryGoodsMaxDate || addDaysToIsoDate(min, 4);
  return { min, dryGoodsMax };
}

function updateCheckoutDeliveryFields(cart = readCart()) {
  const form = document.querySelector("[data-checkout-form]");
  if (!form) return;
  const dryOnly = dryGoodsOnly(cart);
  const dateInput = form.elements["delivery-date"];
  const slotSelect = form.elements["delivery-slot"];
  const cityInput = form.elements.city;
  const note = document.querySelector("[data-delivery-mode]");
  const warning = document.querySelector("[data-delivery-area-warning]");
  const deliveryDates = checkoutDeliveryDateBounds(dateInput);
  dateInput.min = deliveryDates.min;
  if (dryOnly) {
    dateInput.max = deliveryDates.dryGoodsMax;
    if (!dateInput.value || dateInput.value < dateInput.min || dateInput.value > dateInput.max) {
      dateInput.value = dateInput.min;
    }
    [...slotSelect.options].forEach((option) => {
      option.disabled = option.value !== "courier";
      option.hidden = option.value !== "courier";
    });
    slotSelect.value = "courier";
    if (note) note.textContent = "Đồ khô giao toàn quốc, dự kiến 1–5 ngày. Đơn vị vận chuyển tự sắp xếp thời gian giao.";
    if (warning) warning.hidden = true;
  } else {
    dateInput.removeAttribute("max");
    if (dateInput.value < dateInput.min) dateInput.value = dateInput.min;
    [...slotSelect.options].forEach((option) => {
      option.disabled = option.value === "courier";
      option.hidden = option.value === "courier";
    });
    if (slotSelect.value === "courier") slotSelect.value = "08:00–10:00";
    if (note) note.textContent = "Đồ ăn và thức uống tươi chỉ giao trong TP. Hồ Chí Minh theo khung giờ.";
    if (warning) {
      warning.hidden = !cityInput.value || isHoChiMinhCity(cityInput.value);
      warning.textContent = "Đồ ăn và thức uống tươi chỉ giao trong khu vực TP. Hồ Chí Minh.";
    }
  }
}

function readCart() {
  try {
    const saved = JSON.parse(localStorage.getItem(cartStorageKey) || "[]");
    if (!Array.isArray(saved)) {
      throw new TypeError("Giỏ hàng minh họa không đúng định dạng.");
    }

    return saved
      .filter((item) => item && catalogProducts[item.id] && catalogProducts[item.id].available !== false && Number.isInteger(item.quantity) && item.quantity > 0)
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
  const drawerItems = document.querySelector("[data-cart-drawer-items]");
  const drawerEmpty = document.querySelector("[data-cart-drawer-empty]");
  if (!cartItems && !checkoutItems && !drawerItems) return;

  const cart = readCart();
  const subtotal = cart.reduce((sum, item) => sum + catalogProducts[item.id].price * item.quantity, 0);
  const destinationCity = document.querySelector('[data-checkout-form] [name="city"]')?.value || "";
  const shipping = shippingFeeFor(subtotal, cart, destinationCity);
  const total = subtotal + shipping;
  const lineCount = cart.reduce((sum, item) => sum + item.quantity, 0);
  updateCheckoutDeliveryFields(cart);

  document.querySelectorAll("[data-cart-subtotal]").forEach((element) => {
    element.textContent = currency.format(subtotal);
  });
  document.querySelectorAll("[data-cart-total]").forEach((element) => {
    element.textContent = currency.format(total);
  });
  document.querySelectorAll("[data-cart-line-count]").forEach((element) => {
    element.textContent = `${lineCount} món`;
  });
  document.querySelectorAll("[data-shipping-fee]").forEach((element) => {
    element.textContent = cart.length ? (shipping ? currency.format(shipping) : "Miễn phí") : "—";
  });
  document.querySelectorAll("[data-checkout-link]").forEach((checkoutLink) => {
    checkoutLink.setAttribute("aria-disabled", String(cart.length === 0));
    checkoutLink.setAttribute("tabindex", cart.length ? "0" : "-1");
  });

  const emptyState = document.querySelector("[data-cart-empty]");
  if (emptyState) emptyState.hidden = cart.length > 0;
  if (drawerItems) {
    drawerItems.replaceChildren();
    drawerItems.hidden = cart.length === 0;
    cart.forEach((item) => {
      const product = catalogProducts[item.id];
      const row = document.createElement("article");
      row.className = "cart-drawer-line";

      const art = document.createElement("span");
      art.className = "mini-product-art";
      art.dataset.category = product.category;
      art.setAttribute("aria-hidden", "true");
      fillProductArt(art, product);

      const info = document.createElement("div");
      info.className = "cart-drawer-item-info";
      const name = document.createElement("h3");
      name.textContent = product.name;
      const description = document.createElement("p");
      description.textContent = product.calories ? `${product.calories} Calo` : product.description;
      const price = document.createElement("strong");
      price.className = "cart-drawer-item-price";
      price.textContent = currency.format(product.price * item.quantity);
      info.append(name, description, price);

      const removeButton = document.createElement("button");
      removeButton.className = "cart-drawer-remove";
      removeButton.type = "button";
      removeButton.dataset.cartRemove = item.id;
      removeButton.setAttribute("aria-label", `Xóa ${product.name} khỏi giỏ`);
      removeButton.append(createIcon("fm-x"));

      const quantity = document.createElement("div");
      quantity.className = "cart-drawer-quantity";
      quantity.setAttribute("aria-label", `Số lượng ${product.name}`);
      const decrease = document.createElement("button");
      decrease.type = "button";
      decrease.dataset.cartChange = "-1";
      decrease.dataset.productId = item.id;
      decrease.setAttribute("aria-label", `Giảm số lượng ${product.name}`);
      decrease.append(createIcon("fm-minus"));
      const count = document.createElement("span");
      count.textContent = String(item.quantity);
      const increase = document.createElement("button");
      increase.type = "button";
      increase.dataset.cartChange = "1";
      increase.dataset.productId = item.id;
      increase.setAttribute("aria-label", `Tăng số lượng ${product.name}`);
      increase.append(createIcon("fm-plus"));
      quantity.append(decrease, count, increase);
      row.append(art, info, removeButton, quantity);
      drawerItems.append(row);
    });
  }
  if (drawerEmpty) drawerEmpty.hidden = cart.length > 0;
  if (cartItems) {
    cartItems.replaceChildren();
    cartItems.hidden = cart.length === 0;
    cart.forEach((item) => {
      const product = catalogProducts[item.id];
      const row = document.createElement("article");
      row.className = "cart-line";
      row.innerHTML = `
        <div class="cart-line-info">
          <span class="mini-product-art" data-category="${product.category}" aria-hidden="true"></span>
          <div><h3></h3><p></p></div>
        </div>
        <div class="quantity-control" aria-label="Số lượng">
          <button type="button" data-cart-change="-1" data-product-id="${item.id}" aria-label="Giảm số lượng">−</button>
          <span>${item.quantity}</span>
          <button type="button" data-cart-change="1" data-product-id="${item.id}" aria-label="Tăng số lượng">＋</button>
        </div>
        <strong class="cart-line-price">${currency.format(product.price * item.quantity)}</strong>
        <button class="remove-item" type="button" data-cart-remove="${item.id}" aria-label="Xóa ${product.name}">×</button>`;
      const productArt = row.querySelector(".mini-product-art");
      fillProductArt(productArt, product);
      row.querySelector("h3").textContent = product.name;
      row.querySelector(".cart-line-info p").textContent = product.description;
      cartItems.append(row);
    });

  }

  if (checkoutItems) {
    checkoutItems.replaceChildren();
    cart.forEach((item) => {
      const product = catalogProducts[item.id];
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

function createCatalogCard(product) {
  const card = document.createElement("article");
  card.className = "catalog-card";
  card.dataset.product = "";
  card.dataset.id = product.id;
  card.dataset.category = product.category;

  const art = document.createElement("div");
  art.className = "catalog-art";
  const tag = document.createElement("span");
  tag.className = "catalog-tag";
  tag.textContent = categoryName(product.category) || "FitMeal";
  art.append(tag);

  const details = document.createElement("div");
  details.className = "catalog-details";
  const info = document.createElement("div");
  const name = document.createElement("h3");
  const description = document.createElement("p");
  const deliveryNote = document.createElement("small");
  deliveryNote.className = "catalog-delivery-note";
  info.append(name, description, deliveryNote);

  const macros = document.createElement("dl");
  macros.className = "catalog-macros";
  [["protein", "protein"], ["calories", "kcal"], ["carbs", "carb"], ["fat", "béo"]].forEach(([key, label]) => {
    const cell = document.createElement("div");
    cell.dataset.macro = key;
    const term = document.createElement("dt");
    term.textContent = label;
    const value = document.createElement("dd");
    cell.append(term, value);
    macros.append(cell);
  });
  const detailButton = document.createElement("button");
  detailButton.className = "product-detail-link";
  detailButton.type = "button";
  detailButton.dataset.productDetails = product.id;
  detailButton.textContent = "Xem thành phần và dinh dưỡng";
  details.append(info, macros, detailButton);

  const buy = document.createElement("div");
  buy.className = "catalog-buy";
  const price = document.createElement("strong");
  const button = document.createElement("button");
  button.type = "button";
  button.dataset.addToCart = "";
  button.className = "catalog-cart-button";
  buy.append(price, button);
  card.append(art, details, buy);
  return card;
}

function createIcon(symbol) {
  const namespace = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(namespace, "svg");
  svg.setAttribute("class", "fm-i");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  const use = document.createElementNS(namespace, "use");
  use.setAttribute("href", `#${symbol}`);
  svg.append(use);
  return svg;
}

function formatGrams(value) {
  const number = Number(value || 0);
  return `${Number.isInteger(number) ? number : number.toLocaleString("vi-VN", { maximumFractionDigits: 1 })}g`;
}

function initializeHomeProducts() {
  const home = document.querySelector("[data-home-products]");
  if (!home) return;
  home.addEventListener("click", (event) => {
    const button = event.target.closest("[data-add-to-cart-id]");
    if (!button) return;
    const productId = button.dataset.addToCartId;
    if (!catalogProducts[productId]) {
      showToast("Thực đơn đang tải, vui lòng thử lại sau giây lát.");
      return;
    }
    addProductToCart(productId);
  });
}

function renderCatalogInventory() {
  const grid = document.querySelector("[data-product-grid]");
  if (!grid) return;

  const cards = new Map([...grid.querySelectorAll("[data-product]")].map((card) => [card.dataset.id, card]));
  catalogInventory.forEach((product) => {
    let card = cards.get(product.id);
    if (!card) {
      card = createCatalogCard(product);
      grid.append(card);
    }
    card.hidden = false;
    card.dataset.name = product.name;
    card.dataset.search = `${product.name} ${product.description}`;
    card.dataset.category = product.category;
    card.dataset.price = String(product.price);
    card.querySelector(".catalog-details h3").textContent = product.name;
    card.querySelector(".catalog-details p").textContent = product.description;
    let deliveryNote = card.querySelector(".catalog-delivery-note");
    if (!deliveryNote) {
      deliveryNote = document.createElement("small");
      deliveryNote.className = "catalog-delivery-note";
      card.querySelector(".catalog-details > div").insertBefore(
        deliveryNote,
        card.querySelector(".product-detail-link"),
      );
    }
    if (product.category === "dry_goods") {
      const details = ["Giao toàn quốc, dự kiến 1–5 ngày"];
      if (product.shippingWeightGrams) details.push(`${product.shippingWeightGrams} g`);
      if (product.expiryDate) {
        details.push(`HSD ${new Date(`${product.expiryDate}T00:00:00`).toLocaleDateString("vi-VN")}`);
      }
      deliveryNote.textContent = details.join(", ");
    } else {
      deliveryNote.textContent = "Chỉ giao tại TP. Hồ Chí Minh";
    }
    card.querySelector(".catalog-buy > strong").textContent = currency.format(product.price);
    let photo = card.querySelector(".catalog-product-photo");
    if (!photo) {
      photo = document.createElement("img");
      photo.className = "catalog-product-photo";
      photo.alt = "";
      photo.loading = "lazy";
      photo.addEventListener("error", () => {
        photo.src = productFallbackImage(card.dataset.category);
      }, { once: true });
      card.querySelector(".catalog-art").prepend(photo);
    }
    photo.src = productImage(product);
    card.querySelector(".catalog-art").classList.toggle("has-product-image", Boolean(product.image));
    const detailButton = card.querySelector("[data-product-details]");
    if (detailButton) detailButton.dataset.productDetails = product.id;
    card.querySelectorAll("[data-macro]").forEach((cell) => {
      const value = product[cell.dataset.macro];
      cell.querySelector("dd").textContent = cell.dataset.macro === "calories"
        ? String(Number(value || 0))
        : formatGrams(value);
    });

    const tag = card.querySelector(".catalog-tag");
    if (!tag.dataset.defaultTag) tag.dataset.defaultTag = tag.textContent;
    const button = card.querySelector("[data-add-to-cart]");
    const soldOut = !product.available;
    card.classList.toggle("is-sold-out", soldOut);
    tag.textContent = soldOut ? "TẠM HẾT MÓN" : tag.dataset.defaultTag;
    button.disabled = false;
    button.hidden = false;
    button.classList.toggle("is-sold-out-button", soldOut);
    button.classList.add("catalog-cart-button");
    button.setAttribute("aria-label", soldOut ? `${product.name} tạm hết món` : `Thêm ${product.name} vào giỏ`);
    button.replaceChildren();
    if (soldOut) button.textContent = "Tạm hết món";
    else button.append(createIcon("fm-plus"), document.createTextNode("Thêm"));
  });

  cards.forEach((card, id) => {
    if (!catalogInventory.some((product) => product.id === id)) card.hidden = true;
  });
}

function addProductToCart(productId, openDrawer = true) {
  const product = catalogProducts[productId];
  if (!product || !product.available) {
    showToast("Món này đang tạm hết.");
    return false;
  }
  const cart = readCart();
  const existing = cart.find((item) => item.id === productId);
  if (existing) existing.quantity += 1;
  else cart.push({ id: productId, quantity: 1 });
  writeCart(cart);
  renderCart();
  if (openDrawer) {
    if (cartDrawerController) cartDrawerController.open();
    else showToast(`${product.name} đã được thêm vào giỏ.`);
  }
  return true;
}

async function loadServerCatalog(refreshCatalog) {
  try {
    const response = await fetch("/api/products/", {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) throw new Error(`Catalog API returned ${response.status}.`);
    const payload = await response.json();
    if (!payload || !Array.isArray(payload.results)) {
      throw new TypeError("Catalog API response has an invalid shape.");
    }
    const products = payload.results.map((product) => ({
      id: product.slug,
      sku: product.sku,
      name: product.name,
      price: Number(product.price),
      category: product.category,
      shippingWeightGrams: Number(product.shipping_weight_grams || 0),
      expiryDate: product.expiry_date || "",
      description: product.description,
      image: product.image,
      available: product.available,
      featured: product.featured,
      calories: Number(product.calories),
      protein: Number(product.protein),
      carbs: Number(product.carbs),
      fat: Number(product.fat),
      ingredients: product.ingredients,
      allergens: product.allergens,
      serving: product.serving,
    }));
    if (products.some((product) =>
      typeof product.id !== "string" || typeof product.name !== "string"
      || !Number.isFinite(product.price) || typeof product.available !== "boolean"
    )) {
      throw new TypeError("Catalog API returned invalid product data.");
    }

    applyInventory(products);
    renderCatalogInventory();
    refreshCatalog?.();
    renderCart();
    updateCartCounts();
    applyPendingReorder();
    const status = document.querySelector("[data-catalog-status]");
    if (status) {
      status.hidden = products.length > 0;
      status.textContent = products.length
        ? ""
        : "Hiện chưa có sản phẩm trong hệ thống.";
    }
  } catch (error) {
    console.error("Không thể tải danh sách sản phẩm từ máy chủ.", error);
    const status = document.querySelector("[data-catalog-status]");
    if (status) {
      status.hidden = false;
      status.textContent = "Không thể tải thực đơn từ máy chủ. Vui lòng tải lại trang hoặc thử lại sau.";
    }
  }
}

function initializeCatalog() {
  const productGrid = document.querySelector("[data-product-grid]");
  if (!productGrid) return null;

  renderCatalogInventory();
  let selectedCategory = "all";
  const search = document.querySelector("[data-product-search]");
  const sort = document.querySelector("[data-product-sort]");
  const proteinFilter = document.querySelector("[data-protein-filter]");
  const calorieFilter = document.querySelector("[data-calorie-filter]");
  const priceMin = document.querySelector("[data-price-min]");
  const priceMax = document.querySelector("[data-price-max]");
  const emptyResults = document.querySelector("[data-empty-results]");
  function filterProducts() {
    const products = [...productGrid.querySelectorAll("[data-product]")];
    const searchTerm = search.value.trim().toLocaleLowerCase("vi");
    products.forEach((product) => {
      const matchesCategory = selectedCategory === "all" || product.dataset.category === selectedCategory;
      const matchesSearch = `${product.dataset.name} ${product.dataset.search}`.toLocaleLowerCase("vi").includes(searchTerm);
      const nutrition = catalogProducts[product.dataset.id];
      const matchesProtein = Number(nutrition?.protein || 0) >= Number(proteinFilter?.value || 0);
      const maxCalories = Number(calorieFilter?.value || 0);
      const matchesCalories = !maxCalories || Number(nutrition?.calories || 0) <= maxCalories;
      const minPrice = Number(priceMin?.value || 0);
      const maxPrice = Number(priceMax?.value || 0);
      const matchesPrice = Number(product.dataset.price) >= minPrice && (!maxPrice || Number(product.dataset.price) <= maxPrice);
      product.hidden = !(matchesCategory && matchesSearch && matchesProtein && matchesCalories && matchesPrice);
    });
    emptyResults.hidden = products.some((product) => !product.hidden);

    const sortOrder = sort.value;
    const orderedProducts = [...products];
    if (sortOrder === "featured") {
      orderedProducts.sort((left, right) =>
        Number(catalogProducts[right.dataset.id]?.featured)
        - Number(catalogProducts[left.dataset.id]?.featured)
      );
    } else {
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
        chip.setAttribute("aria-pressed", String(chip === button));
      });
      filterProducts();
    });
  });

  const params = new URLSearchParams(window.location.search);
  const requestedCategory = params.get("category");
  const categoryButton = requestedCategory
    ? document.querySelector(`.filter-chip[data-category="${CSS.escape(requestedCategory)}"]`)
    : null;
  if (categoryButton) {
    selectedCategory = requestedCategory;
    document.querySelectorAll(".filter-chip").forEach((chip) => {
      chip.classList.toggle("is-active", chip === categoryButton);
      chip.setAttribute("aria-pressed", String(chip === categoryButton));
    });
  }
  const presetSelect = (select, value) => {
    if (select && value && [...select.options].some((option) => option.value === value)) select.value = value;
  };
  presetSelect(proteinFilter, params.get("protein"));
  presetSelect(calorieFilter, params.get("calories"));
  if (params.get("q")) search.value = params.get("q");

  search.addEventListener("input", filterProducts);
  sort.addEventListener("change", filterProducts);
  proteinFilter?.addEventListener("change", filterProducts);
  calorieFilter?.addEventListener("change", filterProducts);
  priceMin?.addEventListener("input", filterProducts);
  priceMax?.addEventListener("input", filterProducts);
  productGrid.addEventListener("click", (event) => {
    const detailButton = event.target.closest("[data-product-details]");
    if (detailButton) {
      showProductDetails(detailButton.dataset.productDetails);
      return;
    }
    const button = event.target.closest("[data-add-to-cart]");
    if (!button || button.disabled) return;

    const productCard = button.closest("[data-product]");
    addProductToCart(productCard.dataset.id);
  });
  return filterProducts;
}

function showProductDetails(productId) {
  const product = catalogProducts[productId];
  const modal = document.querySelector("[data-product-modal]");
  if (!product || !modal) return;
  const photo = modal.querySelector("[data-detail-image]");
  if (photo) {
    photo.src = productImage(product);
    photo.hidden = false;
    photo.alt = product.image ? product.name : "";
  }
  modal.querySelector("[data-detail-name]").textContent = product.name;
  modal.querySelector("[data-detail-description]").textContent = `${categoryName(product.category)} · ${product.description}`;
  modal.querySelector("[data-detail-ingredients]").textContent = product.ingredients || product.description;
  modal.querySelector("[data-detail-allergens]").textContent = product.allergens || "Vui lòng kiểm tra thành phần";
  modal.querySelector("[data-detail-serving]").textContent = product.serving || "1 khẩu phần";
  const nutrition = modal.querySelector("[data-detail-nutrition]");
  nutrition.replaceChildren();
  [
    ["calories", "Calo", "kcal"],
    ["protein", "Protein", "g"],
    ["carbs", "Carb", "g"],
    ["fat", "Chất béo", "g"],
  ].forEach(([key, label, unit]) => {
    const item = document.createElement("div");
    const amount = document.createElement("strong");
    const title = document.createElement("span");
    amount.textContent = String(product[key] || 0) + unit;
    title.textContent = label;
    item.append(amount, title);
    nutrition.append(item);
  });
  modal.querySelector("[data-detail-add]").dataset.productId = product.id;
  productModalController.open();
}

function createDialogController(modal, initialFocusSelector) {
  let returnFocus = null;
  const open = () => {
    returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    modal.hidden = false;
    modal.querySelector(initialFocusSelector).focus();
  };
  const close = () => {
    modal.hidden = true;
    if (returnFocus?.isConnected) returnFocus.focus();
    returnFocus = null;
  };

  modal.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = [...modal.querySelectorAll(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    )].filter((element) => !element.hidden && element.getAttribute("aria-hidden") !== "true" && element.getClientRects().length);
    if (!focusable.length) {
      event.preventDefault();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && (document.activeElement === first || !modal.contains(document.activeElement))) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && (document.activeElement === last || !modal.contains(document.activeElement))) {
      event.preventDefault();
      first.focus();
    }
  });
  return { open, close };
}

function initializeProductModal() {
  const modal = document.querySelector("[data-product-modal]");
  if (!modal) return;
  productModalController = createDialogController(modal, "[data-close-product-modal]");
  const { close } = productModalController;
  modal.querySelector("[data-close-product-modal]").addEventListener("click", close);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) close();
  });
  modal.querySelector("[data-detail-add]").addEventListener("click", (event) => {
    const productId = event.currentTarget.dataset.productId;
    if (!addProductToCart(productId, false)) return;
    close();
    if (cartDrawerController) cartDrawerController.open();
    else showToast(`${catalogProducts[productId].name} đã được thêm vào giỏ.`);
  });
}

function initializeCartDrawer() {
  const drawer = document.querySelector("[data-cart-drawer]");
  if (!drawer) return null;
  const controller = createDialogController(drawer, "[data-close-cart-drawer]");
  drawer.querySelector("[data-close-cart-drawer]").addEventListener("click", controller.close);
  drawer.addEventListener("click", (event) => {
    if (event.target === drawer) controller.close();
  });
  return controller;
}

function initializeCart() {
  const cartItems = document.querySelector("[data-cart-items]");
  const drawerItems = document.querySelector("[data-cart-drawer-items]");

  const handleCartItemClick = (event) => {
    const removeButton = event.target.closest("[data-cart-remove]");
    const changeButton = event.target.closest("[data-cart-change]");
    const productId = removeButton?.dataset.cartRemove || changeButton?.dataset.productId;
    if (!productId) return;
    const itemContainer = event.currentTarget;
    const changeAmount = changeButton ? Number(changeButton.dataset.cartChange) : null;

    let cart = readCart();
    if (removeButton) {
      cart = cart.filter((item) => item.id !== productId);
    } else {
      const item = cart.find((entry) => entry.id === productId);
      if (item) item.quantity += changeAmount;
      cart = cart.filter((entry) => entry.quantity > 0);
    }
    writeCart(cart);
    renderCart();
    if (changeButton && cart.some((item) => item.id === productId)) {
      [...itemContainer.querySelectorAll("[data-cart-change]")].find((button) =>
        button.dataset.productId === productId && Number(button.dataset.cartChange) === changeAmount
      )?.focus();
    } else {
      const nextItemControl = itemContainer.querySelector("[data-cart-remove], [data-cart-change]");
      if (nextItemControl) nextItemControl.focus();
      else if (itemContainer === drawerItems) document.querySelector("[data-close-cart-drawer]")?.focus();
    }
  };
  cartItems?.addEventListener("click", handleCartItemClick);
  drawerItems?.addEventListener("click", handleCartItemClick);

  document.querySelectorAll("[data-checkout-link]").forEach((checkoutLink) => {
    checkoutLink.addEventListener("click", (event) => {
      if (!readCart().length) {
        event.preventDefault();
        showToast("Thêm ít nhất một món vào giỏ trước nhé.");
      }
    });
  });

  window.addEventListener("storage", (event) => {
    if (event.key === cartStorageKey) renderCart();
  });
}

function initializeCustomerOrderActions() {
  document.querySelectorAll("[data-open-cancel-dialog]").forEach((button) => {
    button.addEventListener("click", () => {
      document.getElementById(button.dataset.openCancelDialog)?.showModal();
    });
  });
  document.querySelectorAll("[data-close-cancel-dialog]").forEach((button) => {
    button.addEventListener("click", () => button.closest("dialog")?.close());
  });

  document.querySelectorAll("[data-reorder-form]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const submitButton = form.querySelector('button[type="submit"]');
      const csrfToken = form.querySelector('[name="csrfmiddlewaretoken"]')?.value;
      if (!csrfToken) {
        showToast("Không gửi được yêu cầu mua lại. Hãy tải lại trang rồi thử lại.");
        return;
      }
      if (submitButton) submitButton.disabled = true;
      try {
        const response = await fetch(form.action, {
          method: "POST",
          credentials: "same-origin",
          headers: { Accept: "application/json", "X-CSRFToken": csrfToken },
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "Không thể mua lại đơn hàng này.");
        sessionStorage.setItem("fitmeal-pending-reorder", JSON.stringify(payload.items));
        window.location.assign("/products/?open_cart=1");
      } catch (error) {
        showToast(error.message || "Không thể mua lại đơn hàng này.");
        if (submitButton) submitButton.disabled = false;
      }
    });
  });
}

function applyPendingReorder() {
  const pendingReorder = sessionStorage.getItem("fitmeal-pending-reorder");
  if (!pendingReorder) return;

  let items;
  try {
    items = JSON.parse(pendingReorder);
    if (!Array.isArray(items) || items.some((item) =>
      !item || typeof item.id !== "string" || !Number.isInteger(item.quantity)
      || item.quantity < 1 || item.quantity > 99
    )) {
      throw new TypeError("Danh sách mua lại không đúng định dạng.");
    }
  } catch (error) {
    sessionStorage.removeItem("fitmeal-pending-reorder");
    console.error("Không thể đọc danh sách mua lại.", error);
    showToast("Không thể khôi phục các món của đơn hàng trước.");
    return;
  }

  const cart = readCart();
  let addedCount = 0;
  let skippedCount = 0;
  items.forEach((item) => {
    if (!catalogProducts[item.id]?.available) {
      skippedCount += 1;
      return;
    }
    const existing = cart.find((entry) => entry.id === item.id);
    if (existing) existing.quantity = Math.min(99, existing.quantity + item.quantity);
    else cart.push({ id: item.id, quantity: item.quantity });
    addedCount += 1;
  });
  sessionStorage.removeItem("fitmeal-pending-reorder");
  if (!addedCount) {
    showToast("Các món trong đơn cũ hiện không còn bán.");
    return;
  }

  writeCart(cart);
  renderCart();
  const url = new URL(window.location.href);
  const shouldOpenCart = url.searchParams.get("open_cart") === "1";
  url.searchParams.delete("open_cart");
  window.history.replaceState(null, "", url);
  if (skippedCount) {
    showToast(`Đã thêm món còn bán vào giỏ; bỏ qua ${skippedCount} món đã ngừng bán.`);
  }
  if (shouldOpenCart && cartDrawerController) cartDrawerController.open();
}

function initializeCheckout() {
  const form = document.querySelector("[data-checkout-form]");
  if (!form) return;

  document.querySelector("[data-checkout-saved-address]")?.addEventListener("change", (event) => {
    const option = event.currentTarget.selectedOptions[0];
    if (!option.value) return;
    form.elements.address.value = option.dataset.address;
    form.elements.district.value = option.dataset.district;
    form.elements.city.value = option.dataset.city;
    updateCheckoutDeliveryFields();
    renderCart();
  });

  const dateInput = form.elements["delivery-date"];
  dateInput.min = checkoutDeliveryDateBounds(dateInput).min;
  dateInput.value = dateInput.min;

  form.elements.city.addEventListener("input", () => {
    updateCheckoutDeliveryFields();
    renderCart();
  });
  form.elements.city.addEventListener("change", () => {
    updateCheckoutDeliveryFields();
    renderCart();
  });
  form.elements["delivery-date"].addEventListener("change", () => renderCart());
  updateCheckoutDeliveryFields();
  renderCart();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!readCart().length) {
      showToast("Giỏ hàng đang trống. Hãy thêm sản phẩm trước khi đặt.");
      return;
    }

    const values = new FormData(form);
    const checkoutError = document.querySelector("[data-checkout-error]");
    checkoutError.hidden = true;
    const paymentValue = values.get("payment");
    if (!paymentValue) {
      checkoutError.textContent = "Hiện chưa có phương thức thanh toán khả dụng.";
      checkoutError.hidden = false;
      return;
    }
    const payment = paymentValue.toString();
    const cart = readCart();
    const city = values.get("city").toString();
    if (!dryGoodsOnly(cart) && !isHoChiMinhCity(city)) {
      checkoutError.textContent = "Đồ ăn và thức uống tươi chỉ giao trong khu vực TP. Hồ Chí Minh.";
      checkoutError.hidden = false;
      return;
    }
    if (dryGoodsOnly(cart) && values.get("delivery-slot") !== "courier") {
      checkoutError.textContent = "Đồ khô được giao theo lịch của đơn vị vận chuyển.";
      checkoutError.hidden = false;
      return;
    }
    const address = values.get("address").toString().trim();
    const payload = {
      name: values.get("name").toString(),
      email: values.get("email").toString(),
      phone: values.get("phone").toString(),
      address,
      district: values.get("district").toString(),
      city: values.get("city").toString(),
      delivery_date: values.get("delivery-date").toString(),
      delivery_slot: values.get("delivery-slot").toString(),
      note: values.get("note").toString(),
      payment,
      accept_policy: values.get("accept_policy") === "on",
      items: cart.map((item) => ({ id: item.id, quantity: item.quantity })),
    };
    const submitButton = form.querySelector('[type="submit"]');
    submitButton.disabled = true;
    let order;
    try {
      const response = await fetch("/api/orders/", {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": values.get("csrfmiddlewaretoken").toString(),
        },
        body: JSON.stringify(payload),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Không thể tạo đơn hàng.");
      order = result;
    } catch (error) {
      console.error("Không thể tạo đơn hàng trên máy chủ.", error);
      checkoutError.textContent = error.message || "Có lỗi kết nối. Vui lòng thử lại.";
      checkoutError.hidden = false;
      return;
    } finally {
      submitButton.disabled = false;
    }

    if (order.payment_url) {
      writeCart([]);
      submitButton.disabled = true;
      window.location.assign(order.payment_url);
      return;
    }

    writeCart([]);
    submitButton.disabled = true;
    const successPage = document.querySelector("[data-checkout-success]");
    const checkoutPage = document.querySelector("[data-checkout-page]");
    const orderLink = document.querySelector("[data-order-history-link]");
    if (form.dataset.orderHistoryUrl) {
      orderLink.href = form.dataset.orderHistoryUrl;
    } else {
      const trackingUrl = new URL(form.dataset.orderTrackingUrl, window.location.href);
      trackingUrl.searchParams.set("token", order.tracking_token);
      orderLink.href = trackingUrl.toString();
    }
    checkoutPage.hidden = true;
    successPage.hidden = false;
    document.querySelector(".checkout-shell").classList.add("is-order-success");
  });
}

function initializeTracking() {
  const form = document.querySelector("[data-tracking-form]");
  if (!form) return;

  let selectedOrderId = "";
  let selectedTrackingToken = "";
  const deliveryActions = document.querySelector("[data-tracking-delivery-actions]");
  const renderServerOrder = (order) => {
    selectedOrderId = "";
    selectedTrackingToken = order.privacy_redacted ? "" : order.tracking_token;
    deliveryActions.hidden =
      order.privacy_redacted || order.status !== "awaiting_confirmation" || !selectedTrackingToken;
    document.querySelector("[data-tracking-order]").textContent = order.order_number;
    document.querySelector("[data-tracking-status-heading]").textContent = `Đơn hàng ${order.status_display.toLocaleLowerCase("vi")}`;
    const statePill = document.querySelector("[data-tracking-status]");
    statePill.textContent = order.status_display.toLocaleUpperCase("vi");
    statePill.className = `status-pill ${order.status === "cancelled" || order.status === "delivery_issue" ? "status-pending" : order.status === "delivering" || order.status === "awaiting_confirmation" ? "status-shipping" : order.status === "delivered" ? "status-paid" : "status-preparing"}`;
    const details = document.querySelector("[data-tracking-detail]");
    details.replaceChildren();
    const timeline = document.querySelector("[data-tracking-timeline]");
    timeline.replaceChildren();
    document.querySelector("[data-cancel-order]").hidden = true;
    if (order.privacy_redacted) {
      document.querySelector("[data-tracking-date]").textContent = "—";
      const notice = document.createElement("p");
      notice.textContent = "Mã đơn hợp lệ. Thông tin khách hàng đã được mã hóa và ẩn sau khi đơn hoàn tất hoặc bị hủy.";
      details.append(notice);
      details.hidden = false;
      const item = document.createElement("li");
      item.className = "is-current";
      const dot = document.createElement("span");
      dot.className = "timeline-dot";
      dot.textContent = order.status === "cancelled" ? "×" : "✓";
      const content = document.createElement("div");
      const heading = document.createElement("strong");
      heading.textContent = order.status === "cancelled" ? "Đã hủy đơn" : "Đã giao hàng";
      content.append(heading);
      item.append(dot, content);
      timeline.append(item);
      return;
    }

    document.querySelector("[data-tracking-date]").textContent = new Date(order.created_at).toLocaleDateString("vi-VN");
    [
      ["Lịch giao", `${order.delivery_date} · ${order.delivery_slot}`],
      ["Thanh toán", order.payment_method_display],
      ["Tạm tính", currency.format(Number(order.subtotal))],
      ["Phí giao hàng", currency.format(Number(order.shipping_fee))],
      ["Tổng tiền", currency.format(Number(order.total))],
      ["Món đã đặt", order.items.map((item) => `${item.name} × ${item.quantity}`).join(", ")],
    ].forEach(([label, value]) => {
      const line = document.createElement("div");
      const heading = document.createElement("strong");
      heading.textContent = `${label}: `;
      line.append(heading, document.createTextNode(value));
      details.append(line);
    });
    details.hidden = false;
    let steps = order.delivery_type === "nationwide"
      ? [
          ["pending", "Đã tiếp nhận đơn"],
          ["confirmed", "Đã xác nhận"],
          ["packing", "Đang đóng gói"],
          ["shipped", "Đã bàn giao đơn vị vận chuyển"],
          ["delivering", "Đang giao hàng"],
        ]
      : [
          ["pending", "Đã tiếp nhận đơn"],
          ["confirmed", "Đã xác nhận"],
          ["preparing", "Đang chuẩn bị"],
          ["ready", "Sẵn sàng giao"],
          ["delivering", "Đang giao hàng"],
        ];
    if (order.status === "delivery_issue") {
      steps.push(["delivery_issue", "Giao hàng không thành công"]);
    } else if (order.status === "cancelled") {
      steps.push(["cancelled", "Đơn hàng đã hủy"]);
    } else {
      steps.push(["delivered", "Giao hàng thành công"]);
    }
    const timelineStatus = order.status === "awaiting_confirmation" ? "delivering" : order.status;
    let currentStep = steps.findIndex(([status]) => status === timelineStatus);
    if (order.cancellation_requested) {
      if (currentStep >= 0) steps = steps.slice(0, currentStep + 1);
      steps.push(["cancellation_requested", "Quản lý đang xử lý khiếu nại"]);
      currentStep = steps.length - 1;
    }
    steps.forEach(([status, title], index) => {
      const item = document.createElement("li");
      if (index < currentStep) item.className = "is-complete";
      if (index === currentStep) item.className = "is-current";
      const dot = document.createElement("span");
      dot.className = "timeline-dot";
      dot.textContent = index < currentStep ? "✓" : ["cancelled", "delivery_issue"].includes(status) ? "×" : String(index + 1);
      const content = document.createElement("div");
      const heading = document.createElement("strong");
      heading.textContent = title;
      const text = document.createElement("small");
      text.textContent = index === currentStep ? "Trạng thái hiện tại do cửa hàng cập nhật." : "";
      content.append(heading, text);
      item.append(dot, content);
      timeline.append(item);
    });
    selectedTrackingToken = order.tracking_token;
  };
  const fetchServerOrder = async (token) => {
    const response = await fetch(`/api/orders/track/${encodeURIComponent(token)}/`, {
      headers: { Accept: "application/json" },
    });
    const order = await response.json();
    if (!response.ok) throw new Error(order.error || "Không tìm thấy đơn hàng.");
    renderServerOrder(order);
  };
  const submitTrackingAction = async (event, form, action) => {
    event.preventDefault();
    if (!selectedTrackingToken || deliveryActions.dataset.submitting === "true") return;
    const token = selectedTrackingToken;
    const csrfToken = form.querySelector('input[name="csrfmiddlewaretoken"]').value;
    deliveryActions.dataset.submitting = "true";
    deliveryActions.querySelectorAll("button").forEach((button) => { button.disabled = true; });
    try {
      const response = await fetch(
        `/api/orders/track/${encodeURIComponent(token)}/${action}/`,
        {
          method: "POST",
          headers: { Accept: "application/json", "X-CSRFToken": csrfToken },
          body: new FormData(form),
        },
      );
      if (!(response.headers.get("content-type") || "").includes("application/json")) {
        throw new Error("Phiên xác nhận đã hết hạn. Hãy tải lại trang rồi thử lại.");
      }
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Không thể gửi phản hồi cho đơn hàng.");
      if (action === "report-delivery-issue") form.reset();
      showToast(result.message);
      await fetchServerOrder(token);
    } catch (error) {
      showToast(error.message);
    } finally {
      delete deliveryActions.dataset.submitting;
      deliveryActions.querySelectorAll("button").forEach((button) => { button.disabled = false; });
    }
  };
  const renderOrder = (order) => {
    if (!order) {
      showToast("Không tìm thấy mã đơn demo trên trình duyệt này.");
      return;
    }
    selectedTrackingToken = "";
    deliveryActions.hidden = true;
    selectedOrderId = order.id;
    document.querySelector("[data-tracking-order]").textContent = order.id;
    document.querySelector("[data-tracking-date]").textContent = new Date(order.createdAt).toLocaleDateString("vi-VN");
    document.querySelector("[data-tracking-status-heading]").textContent =
      order.cancelRequested ? "Yêu cầu hủy đang chờ xử lý" : `Đơn hàng ${order.status.toLocaleLowerCase("vi")}`;
    const statePill = document.querySelector("[data-tracking-status]");
    statePill.textContent = order.cancelRequested ? "CHỜ HỦY" : order.status.toLocaleUpperCase("vi");
    statePill.className = `status-pill ${order.cancelRequested ? "status-pending" : order.status === "Đang giao" ? "status-shipping" : order.status === "Hoàn tất" ? "status-paid" : "status-preparing"}`;
    const details = document.querySelector("[data-tracking-detail]");
    details.replaceChildren();
    [
      ["Người nhận", order.name],
      ["Email", order.email || "—"],
      ["Điện thoại", order.phone],
      ["Địa chỉ", order.address],
      ["Lịch giao", `${order.deliveryDate} · ${order.deliverySlot}`],
      ["Thanh toán", order.paymentStatus || (order.payment === "online" ? "Trực tuyến (demo)" : "COD")],
      ["Tổng tiền", currency.format(order.total)],
      ["Món đã đặt", order.items.map((item) => `${item.name} × ${item.quantity}`).join(", ")],
      ["Ghi chú", order.note || "Không có"],
    ].forEach(([label, value]) => {
      const line = document.createElement("div");
      const heading = document.createElement("strong");
      heading.textContent = `${label}: `;
      line.append(heading, document.createTextNode(value));
      details.append(line);
    });
    details.hidden = false;
    const canCancel = ["Chờ xác nhận", "Đang chuẩn bị"].includes(order.status) && !order.cancelRequested;
    const cancelButton = document.querySelector("[data-cancel-order]");
    cancelButton.hidden = !canCancel;
    const timeline = document.querySelector("[data-tracking-timeline]");
    timeline.replaceChildren();
    if (order.status === "Đã hủy") {
      const item = document.createElement("li");
      item.className = "is-current";
      const dot = document.createElement("span");
      dot.className = "timeline-dot";
      dot.textContent = "×";
      const content = document.createElement("div");
      const heading = document.createElement("strong");
      heading.textContent = "Đơn hàng đã hủy";
      const text = document.createElement("small");
      text.textContent = "Trạng thái demo đã được quản trị viên cập nhật";
      content.append(heading, text);
      item.append(dot, content);
      timeline.append(item);
      return;
    }
    const steps = ["Đã tiếp nhận đơn", "Đang chuẩn bị", "Đang giao hàng", "Giao hàng thành công"];
    const currentStep = order.cancelRequested ? 0 : order.status === "Chờ xác nhận" ? 0 : order.status === "Đang giao" ? 2 : order.status === "Hoàn tất" ? 3 : 1;
    steps.forEach((title, index) => {
      const item = document.createElement("li");
      if (index < currentStep) item.className = "is-complete";
      if (index === currentStep) item.className = "is-current";
      const dot = document.createElement("span");
      dot.className = "timeline-dot";
      dot.textContent = index < currentStep ? "✓" : String(index + 1);
      const content = document.createElement("div");
      const heading = document.createElement("strong");
      heading.textContent = title;
      const text = document.createElement("small");
      text.textContent = order.cancelRequested ? "Yêu cầu hủy được ghi nhận trong bản demo" : "Trạng thái minh họa, chưa đồng bộ với cửa hàng";
      content.append(heading, text);
      item.append(dot, content);
      timeline.append(item);
    });
  };

  const requestedToken = new URLSearchParams(window.location.search).get("token");
  if (requestedToken) {
    form.elements.order.value = requestedToken;
    fetchServerOrder(requestedToken).catch((error) => showToast(error.message));
  } else {
    const requestedOrder = new URLSearchParams(window.location.search).get("order");
    if (requestedOrder) {
      form.elements.order.value = requestedOrder;
      const lastOrder = getOrders().find((order) => order.id === requestedOrder);
      if (lastOrder) renderOrder(lastOrder);
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const orderId = new FormData(form).get("order").toString().trim();
    if (!orderId) return;
    selectedTrackingToken = "";
    deliveryActions.hidden = true;
    try {
      await fetchServerOrder(orderId);
      showToast("Đã tải trạng thái đơn hàng từ cửa hàng.");
      return;
    } catch (error) {
      const order = getOrders().find((item) => item.id === orderId);
      if (order) {
        renderOrder(order);
        showToast("Đang hiển thị tiến trình đơn hàng mẫu.");
        return;
      }
      showToast(error.message);
    }
  });

  deliveryActions.querySelector("[data-tracking-confirmation-form]").addEventListener("submit", (event) => {
    submitTrackingAction(event, event.currentTarget, "confirm-delivery");
  });
  deliveryActions.querySelector("[data-tracking-issue-form]").addEventListener("submit", (event) => {
    submitTrackingAction(event, event.currentTarget, "report-delivery-issue");
  });

  document.querySelector("[data-cancel-order]").addEventListener("click", () => {
    if (selectedTrackingToken) {
      showToast("Vui lòng liên hệ cửa hàng để yêu cầu hủy đơn.");
      return;
    }
    const order = getOrders().find((item) => item.id === selectedOrderId);
    if (!order || !["Chờ xác nhận", "Đang chuẩn bị"].includes(order.status)) {
      showToast("Đơn này không còn ở trạng thái cho phép yêu cầu hủy.");
      return;
    }
    const orders = getOrders().map((item) => item.id === order.id ? { ...item, cancelRequested: true } : item);
    saveOrders(orders);
    renderOrder(orders.find((item) => item.id === order.id));
    showToast("Đã ghi nhận yêu cầu hủy trong dữ liệu demo.");
  });

  window.addEventListener("storage", (event) => {
    if (event.key === orderStorageKey && selectedOrderId) {
      renderOrder(getOrders().find((order) => order.id === selectedOrderId));
    }
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
}

function initializeAdmin() {
  const tabs = document.querySelectorAll("[data-admin-tab]");
  if (!tabs.length) return;

  const toast = document.querySelector("[data-admin-toast]");
  function notify(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add("is-visible");
    window.clearTimeout(notify.timeoutId);
    notify.timeoutId = window.setTimeout(() => toast.classList.remove("is-visible"), 2400);
  }

  const orderList = document.querySelector("[data-admin-order-list]");
  const recentOrderList = document.querySelector("[data-admin-recent-orders]");
  const emptyOrders = document.querySelector("[data-admin-orders-empty]");
  const emptyRecentOrders = document.querySelector("[data-admin-recent-empty]");
  const orderStatuses = ["Chờ xác nhận", "Đang chuẩn bị", "Đang giao", "Hoàn tất", "Đã hủy"];

  function statusClass(status) {
    if (status === "Đang giao") return "status-shipping";
    if (status === "Hoàn tất") return "status-paid";
    if (status === "Đã hủy") return "status-pending";
    return "status-preparing";
  }

  function renderAdminOrders() {
    const orders = getOrders().sort((left, right) => new Date(right.createdAt) - new Date(left.createdAt));
    const orderCount = document.querySelector("[data-admin-order-count]");
    if (orderCount) orderCount.textContent = String(orders.length);
    if (emptyOrders) emptyOrders.hidden = orders.length > 0;
    if (emptyRecentOrders) emptyRecentOrders.hidden = orders.length > 0;
    if (orderList) orderList.replaceChildren();
    if (recentOrderList) recentOrderList.replaceChildren();

    orders.forEach((order) => {
      if (orderList) {
        const row = document.createElement("tr");
        const nameCell = document.createElement("td");
        const customer = document.createElement("strong");
        customer.textContent = order.name;
        const phone = document.createElement("small");
        phone.className = "admin-order-secondary";
        phone.textContent = order.phone;
        nameCell.append(customer, phone);

        const orderId = document.createElement("td");
        const id = document.createElement("strong");
        id.textContent = `#${order.id}`;
        orderId.append(id);
        const date = document.createElement("td");
        date.textContent = new Date(order.createdAt).toLocaleString("vi-VN");
        const items = document.createElement("td");
        items.className = "admin-order-items";
        items.textContent = order.items.map((item) => `${item.name} × ${item.quantity}`).join(", ");
        const payment = document.createElement("td");
        payment.textContent = order.payment === "online" ? "Online (demo)" : "COD";
        const total = document.createElement("td");
        total.textContent = currency.format(order.total);
        const statusCell = document.createElement("td");
        const select = document.createElement("select");
        select.className = "status-select";
        select.dataset.demoOrderStatus = order.id;
        select.setAttribute("aria-label", `Trạng thái đơn ${order.id}`);
        orderStatuses.forEach((statusValue) => {
          const option = document.createElement("option");
          option.value = statusValue;
          option.textContent = statusValue;
          select.append(option);
        });
        select.value = orderStatuses.includes(order.status) ? order.status : "Chờ xác nhận";
        statusCell.append(select);
        const notes = document.createElement("td");
        if (order.cancelRequested) {
          const request = document.createElement("span");
          request.className = "admin-order-cancel-request";
          request.textContent = "Khách yêu cầu hủy";
          const hint = document.createElement("small");
          hint.textContent = "Cập nhật trạng thái để xử lý";
          notes.append(request, hint);
        } else {
          const request = document.createElement("span");
          request.className = "admin-order-cancel-request is-clear";
          request.textContent = "—";
          notes.append(request);
        }
        row.append(orderId, nameCell, date, items, payment, total, statusCell, notes);
        orderList.append(row);
      }

      if (recentOrderList && recentOrderList.children.length < 4) {
        const row = document.createElement("tr");
        const idCell = document.createElement("td");
        const id = document.createElement("strong");
        id.textContent = `#${order.id}`;
        idCell.append(id);
        const customer = document.createElement("td");
        customer.textContent = order.name;
        const date = document.createElement("td");
        date.textContent = new Date(order.createdAt).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
        const total = document.createElement("td");
        total.textContent = currency.format(order.total);
        const state = document.createElement("td");
        const badge = document.createElement("span");
        badge.className = `status-pill ${statusClass(order.cancelRequested ? "Chờ xác nhận" : order.status)}`;
        badge.textContent = order.cancelRequested ? "Khách yêu cầu hủy" : order.status;
        state.append(badge);
        row.append(idCell, customer, date, total, state);
        recentOrderList.append(row);
      }
    });
  }

  renderAdminOrders();

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
  orderList?.addEventListener("change", (event) => {
    const select = event.target.closest("[data-demo-order-status]");
    if (!select) return;
    const order = getOrders().find((item) => item.id === select.dataset.demoOrderStatus);
    if (!order) {
      notify("Không tìm thấy đơn demo cần cập nhật.");
      renderAdminOrders();
      return;
    }
    const updatedOrders = getOrders().map((item) => item.id === order.id
      ? { ...item, status: select.value, cancelRequested: false }
      : item);
    saveOrders(updatedOrders);
    renderAdminOrders();
    notify(order.cancelRequested
      ? `Đã xử lý yêu cầu hủy đơn ${order.id}: ${select.value}.`
      : `Đã cập nhật đơn ${order.id}: ${select.value}.`);
  });

  window.addEventListener("storage", (event) => {
    if (event.key === orderStorageKey) renderAdminOrders();
  });

  document.querySelector("[data-admin-account-form]")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const feedback = form.querySelector("[data-admin-account-feedback]");
    const password = form.elements.password.value;
    const passwordConfirm = form.elements["password-confirm"].value;
    if (password !== passwordConfirm) {
      feedback.textContent = "Mật khẩu nhập lại chưa khớp.";
      form.elements["password-confirm"].focus();
      return;
    }
    feedback.textContent = "Biểu mẫu hợp lệ. Đây chỉ là bản xem trước; chưa tạo tài khoản admin thật.";
    form.elements.password.value = "";
    form.elements["password-confirm"].value = "";
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

function initializeAnnouncementBanner() {
  const banner = document.querySelector("[data-announcement-banner]");
  const closeButton = document.querySelector("[data-close-announcement]");
  closeButton?.addEventListener("click", () => {
    banner.hidden = true;
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

function initializePasswordVisibility() {
  document.querySelectorAll(".first-login-password-toggle").forEach((button) => {
    button.addEventListener("click", () => {
      const input = document.getElementById(button.getAttribute("aria-controls"));
      if (!input) return;

      const isVisible = input.type === "password";
      input.type = isVisible ? "text" : "password";
      button.setAttribute("aria-pressed", String(isVisible));
      button.setAttribute("aria-label", isVisible ? "Ẩn mật khẩu" : "Hiện mật khẩu");
    });
  });
}

function initializeEmployeeWorkspaceRefresh() {
  if (!document.querySelector("[data-auto-refresh]")) return;
  const refreshWhenSafe = () => {
    window.setTimeout(() => {
      const activeElement = document.activeElement;
      const isEditing = activeElement && activeElement.matches("input:not([type='hidden']), textarea");
      const hasUnsavedInput = Array.from(
        document.querySelectorAll("input:not([type='hidden']), textarea"),
      ).some((field) => {
        if (field.type === "checkbox" || field.type === "radio") {
          return field.checked !== field.defaultChecked;
        }
        return field.value !== field.defaultValue;
      });
      if (document.hidden || isEditing || hasUnsavedInput) {
        refreshWhenSafe();
        return;
      }
      window.location.reload();
    }, 30000);
  };
  refreshWhenSafe();
}

function initializeEmployeeAvailabilityToggles() {
  document.querySelectorAll("[data-employee-availability-form]").forEach((form) => {
    const toggle = form.querySelector('input[type="checkbox"][name="is_available"]');
    if (!toggle) return;
    toggle.addEventListener("change", () => form.requestSubmit());
  });
}

function initializeBankTransferStatus() {
  const page = document.querySelector("[data-bank-transfer-status]");
  const liveStatus = page && page.querySelector("[data-payment-live-status]");
  if (!page || !liveStatus) return;
  const liveText = liveStatus.querySelector("[data-payment-live-text]") || liveStatus;
  const heading = page.querySelector("[data-payment-heading]");

  const showPaid = () => {
    page.querySelector("[data-bank-transfer-pending]")?.setAttribute("hidden", "");
    page.querySelector("[data-payment-intro]")?.setAttribute("hidden", "");
    page.querySelector("[data-payment-home-link]")?.setAttribute("hidden", "");
    if (heading) heading.textContent = "Đã nhận được thanh toán.";
    const success = page.querySelector("[data-payment-success]");
    if (success) {
      success.hidden = false;
      success.querySelector("[data-payment-success-heading]")?.focus({ preventScroll: true });
      success.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  };

  const showExpired = () => {
    page.querySelector("[data-bank-transfer-pending]")?.setAttribute("hidden", "");
    if (heading) heading.textContent = "Mã thanh toán đã hết hạn.";
    const intro = page.querySelector("[data-payment-intro]");
    if (intro) intro.textContent = "Mã thanh toán không còn hiệu lực. Vui lòng liên hệ cửa hàng trước khi chuyển khoản.";
  };

  const checkStatus = async () => {
    try {
      const response = await fetch(page.dataset.statusUrl, {
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Không kiểm tra được trạng thái chuyển khoản.");
      const status = page.querySelector("[data-payment-status]");
      if (status) status.textContent = result.status_display;
      if (result.paid) {
        showPaid();
        return;
      }
      if (result.status === "expired" || result.status === "failed") {
        showExpired();
        return;
      }
      window.setTimeout(checkStatus, 4000);
    } catch (error) {
      liveText.textContent = `${error.message} Trang sẽ tự kiểm tra lại.`;
      window.setTimeout(checkStatus, 10000);
    }
  };
  window.setTimeout(checkStatus, 4000);
}

function initializeMomoPaymentStatus() {
  const page = document.querySelector("[data-momo-payment-status]");
  const liveStatus = page && page.querySelector("[data-payment-live-status]");
  if (!page || !liveStatus) return;

  const expiration = page.querySelector("[data-momo-expiration]");
  if (expiration) {
    const expiresAt = Date.parse(expiration.dataset.expiresAt);
    if (Number.isFinite(expiresAt)) {
      const updateExpiration = () => {
        const remainingSeconds = Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000));
        const minutes = String(Math.floor(remainingSeconds / 60)).padStart(2, "0");
        const seconds = String(remainingSeconds % 60).padStart(2, "0");
        expiration.textContent = `${minutes}:${seconds}`;
      };
      updateExpiration();
      window.setInterval(updateExpiration, 1000);
    }
  }

  const checkStatus = async () => {
    try {
      const response = await fetch(page.dataset.statusUrl, {
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Không kiểm tra được trạng thái MoMo.");
      const status = page.querySelector("[data-payment-status]");
      status.textContent = result.status_display;
      if (result.status !== "pending") {
        window.location.reload();
        return;
      }
      liveStatus.textContent = "Đang chờ MoMo xác nhận; FitMeal tự kiểm tra lại sau 2 giây.";
      window.setTimeout(checkStatus, 2000);
    } catch (error) {
      liveStatus.textContent = `${error.message} Trang sẽ tự kiểm tra lại.`;
      window.setTimeout(checkStatus, 5000);
    }
  };
  window.setTimeout(checkStatus, 2000);
}

function initializeProductCreateForm() {
  const form = document.querySelector("[data-product-create-form]");
  if (!form) return;

  const field = (name) => form.elements[name];
  const category = field("category");
  const kindOptions = [...form.querySelectorAll("[data-product-kind]")];
  const dryFields = [...form.querySelectorAll(".product-create-dry-field")];
  const inventoryFields = [...form.querySelectorAll(".product-create-inventory-field")];
  const checks = [...document.querySelectorAll("[data-product-check]")];
  const publishButton = document.querySelector("[data-product-publish]");
  const checkCount = document.querySelector("[data-product-check-count]");
  const previewImage = document.querySelector("[data-product-preview-image]");
  const uploadPreview = document.querySelector("[data-product-upload-preview]");
  const deliveryNote = document.querySelector("[data-product-delivery-note]");
  let previewUrl = null;

  const selectedKind = () =>
    kindOptions.find((option) => option.checked)?.value || "fresh";
  const updateCategoryOptions = () => {
    const dry = selectedKind() === "dry";
    [...category.options].forEach((option) => {
      if (!option.value) return;
      option.hidden = dry ? option.value !== "dry_goods" : option.value === "dry_goods";
      option.disabled = option.hidden;
    });
    if (dry && category.value !== "dry_goods") category.value = "dry_goods";
    if (!dry && category.value === "dry_goods") category.value = "meal";
    dryFields.forEach((element) => { element.hidden = !dry; });
    inventoryFields.forEach((element) => { element.hidden = !dry; });
    field("stock_quantity").required = dry;
    if (deliveryNote) {
      deliveryNote.textContent = dry
        ? "Đồ khô giao toàn quốc. Cần khai báo khối lượng để tính phí vận chuyển; tồn kho được cập nhật thủ công."
        : "Đồ tươi giao trong TP. Hồ Chí Minh và được làm sau khi khách đặt; không quản lý tồn kho.";
    }
    updatePreview();
    updateChecklist();
  };

  const updatePreview = () => {
    const name = field("name").value.trim();
    const description = field("description").value.trim();
    const calories = field("calories").value.trim();
    const protein = field("protein").value.trim();
    const serving = field("serving").value.trim();
    const price = Number(field("price").value);
    const isDry = selectedKind() === "dry";
    const previewName = document.querySelector("[data-product-preview-name]");
    const previewDescription = document.querySelector("[data-product-preview-description]");
    const previewCalories = document.querySelector("[data-product-preview-calories]");
    const previewProtein = document.querySelector("[data-product-preview-protein]");
    const previewServing = document.querySelector("[data-product-preview-serving]");
    const previewPrice = document.querySelector("[data-product-preview-price]");
    const previewCategory = document.querySelector("[data-product-preview-category]");
    if (previewName) previewName.textContent = name || "Tên món";
    if (previewDescription) previewDescription.textContent = description || field("ingredients").value.trim() || "Thành phần chính";
    if (previewCalories) previewCalories.textContent = `${calories || "—"} kcal`;
    if (previewProtein) previewProtein.textContent = `${protein || "—"} g đạm`;
    if (previewServing) previewServing.textContent = serving || "Khẩu phần";
    if (previewPrice) {
      previewPrice.textContent = price > 0
        ? new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND", maximumFractionDigits: 0 }).format(price)
        : "—";
    }
    if (previewCategory) previewCategory.textContent = isDry ? "ĐỒ KHÔ · GIAO TOÀN QUỐC" : "ĐỒ TƯƠI · TRONG NGÀY";
  };

  const updateChecklist = () => {
    const validPrice = Number(field("price").value) > 0;
    const stock = field("stock_quantity").value.trim();
    const isDry = selectedKind() === "dry";
    const checksPassed = {
      identity: Boolean(field("name").value.trim() && category.value),
      details: Boolean(
        field("description").value.trim()
        && field("ingredients").value.trim()
        && (selectedKind() !== "dry" || Number(field("shipping_weight_grams").value) > 0),
      ),
      nutrition: Boolean(
        Number(field("calories").value) > 0
        && Number(field("protein").value) > 0
        && field("serving").value.trim(),
      ),
      image: Boolean(field("image").files?.length),
      price: validPrice,
      stock: !isDry || (stock !== "" && Number(stock) >= 0),
    };
    const completed = checks.reduce((count, item) => {
      const isComplete = checksPassed[item.dataset.productCheck];
      item.classList.toggle("is-complete", isComplete);
      return count + Number(isComplete);
    }, 0);
    if (checkCount) checkCount.textContent = String(completed);
    if (publishButton) publishButton.disabled = completed !== checks.length;
  };

  kindOptions.forEach((option) => option.addEventListener("change", updateCategoryOptions));
  category.addEventListener("change", () => {
    const dry = category.value === "dry_goods";
    const matchingKind = kindOptions.find((option) => option.value === (dry ? "dry" : "fresh"));
    if (matchingKind) matchingKind.checked = true;
    updateCategoryOptions();
  });
  ["name", "description", "ingredients", "calories", "protein", "serving", "price", "stock_quantity"].forEach((name) => {
    field(name).addEventListener("input", () => {
      updatePreview();
      updateChecklist();
    });
    field(name).addEventListener("change", updateChecklist);
  });
  field("image").addEventListener("change", () => {
    const file = field("image").files?.[0];
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = file ? URL.createObjectURL(file) : null;
    [previewImage, uploadPreview].forEach((container) => {
      if (!container) return;
      container.replaceChildren();
      if (previewUrl) {
        const image = document.createElement("img");
        image.src = previewUrl;
        image.alt = "Xem trước ảnh món";
        container.append(image);
      } else {
        container.textContent = "Chưa có ảnh";
      }
    });
    updateChecklist();
  });

  updateCategoryOptions();
  updatePreview();
  updateChecklist();
}

cartDrawerController = initializeCartDrawer();
updateCartCounts();
renderCart();
initializeProductModal();
const refreshCatalog = initializeCatalog();
if (document.querySelector("[data-product-grid], [data-cart-items], [data-checkout-items], [data-home-products]")) {
  loadServerCatalog(refreshCatalog);
}
initializeCart();
initializeHomeProducts();
initializeCustomerOrderActions();
initializeCheckout();
initializeTracking();
initializeAccount();
initializePasswordVisibility();
initializeEmployeeWorkspaceRefresh();
initializeEmployeeAvailabilityToggles();
initializeBankTransferStatus();
initializeMomoPaymentStatus();
initializeProductCreateForm();
initializeAdmin();
initializeAnnouncementBanner();
initializeMobileNavigation();
initializeLanguages();
