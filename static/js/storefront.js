const demoProducts = {
  "banana-whey": { name: "Banana Whey", price: 59000, category: "drink", description: "Chuối · Sữa tươi · Whey", icon: "🍌" },
  "mocha-whey": { name: "Mocha Cafe Whey", price: 65000, category: "drink", description: "Cafe · Cacao · Chuối · Whey", icon: "✳" },
  "berry-protein": { name: "Berry Protein", price: 62000, category: "drink", description: "Dâu tây · Sữa chua · Whey", icon: "✿" },
  "chicken-sous-vide": { name: "Ức gà Sous-vide", price: 89000, category: "meal", description: "Ức gà · Tiêu đen thảo mộc", icon: "F" },
  "protein-brownie": { name: "Protein Brownie", price: 39000, category: "snack", description: "Cacao · Yến mạch · Whey", icon: "FM" },
  "granola-crunch": { name: "Granola Crunch", price: 45000, category: "snack", description: "Yến mạch · Hạt · Mật ong", icon: "FM" },
};

const cartStorageKey = "fitmeal-demo-cart";
const inventoryStorageKey = "fitmeal-demo-products";
const profileStorageKey = "fitmeal-demo-profile";
const orderStorageKey = "fitmeal-demo-orders";
const sessionStorageKey = "fitmeal-demo-session";
const currency = new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND", maximumFractionDigits: 0 });
const defaultInventory = [
  { id: "banana-whey", sku: "FM-001", name: "Banana Whey", price: 59000, category: "drink", description: "Chuối · Sữa tươi · Whey", icon: "🍌", available: true, calories: 220, protein: 13, carbs: 28, fat: 5, ingredients: "Chuối, sữa tươi, whey protein", allergens: "Sữa", serving: "350 ml" },
  { id: "mocha-whey", sku: "FM-002", name: "Mocha Cafe Whey", price: 65000, category: "drink", description: "Cafe · Cacao · Chuối · Whey", icon: "✳", available: true, calories: 245, protein: 13, carbs: 30, fat: 6, ingredients: "Cà phê, cacao, chuối, sữa, whey protein", allergens: "Sữa; có caffeine", serving: "350 ml" },
  { id: "berry-protein", sku: "FM-003", name: "Berry Protein", price: 62000, category: "drink", description: "Dâu tây · Sữa chua · Whey", icon: "✿", available: true, calories: 205, protein: 18, carbs: 22, fat: 4, ingredients: "Dâu tây, sữa chua, whey protein", allergens: "Sữa", serving: "350 ml" },
  { id: "chicken-sous-vide", sku: "FM-004", name: "Ức gà Sous-vide", price: 89000, category: "meal", description: "Ức gà · Tiêu đen thảo mộc", icon: "F", available: true, calories: 360, protein: 32, carbs: 24, fat: 12, ingredients: "Ức gà, khoai lang, tiêu đen, rau củ", allergens: "Không khai báo dị ứng phổ biến", serving: "350 g" },
  { id: "protein-brownie", sku: "FM-005", name: "Protein Brownie", price: 39000, category: "snack", description: "Cacao · Yến mạch · Whey", icon: "FM", available: true, calories: 190, protein: 12, carbs: 24, fat: 7, ingredients: "Cacao, yến mạch, whey protein", allergens: "Sữa; yến mạch", serving: "80 g" },
  { id: "granola-crunch", sku: "FM-006", name: "Granola Crunch", price: 45000, category: "snack", description: "Yến mạch · Hạt · Mật ong", icon: "FM", available: true, calories: 230, protein: 8, carbs: 32, fat: 9, ingredients: "Yến mạch, hạt tổng hợp, mật ong", allergens: "Các loại hạt", serving: "80 g" },
  { id: "rice-power-bowl", sku: "FM-007", name: "Cơm gà Power Bowl", price: 79000, category: "rice", description: "Ức gà · Gạo lứt · Rau củ", icon: "F", available: true, calories: 480, protein: 34, carbs: 56, fat: 11, ingredients: "Ức gà, gạo lứt, bông cải, cà rốt", allergens: "Không khai báo dị ứng phổ biến", serving: "420 g" },
  { id: "salad-green-fit", sku: "FM-008", name: "Salad Green Fit", price: 69000, category: "salad", description: "Rau xanh · Trứng · Sốt mè", icon: "✿", available: true, calories: 310, protein: 21, carbs: 20, fat: 15, ingredients: "Rau xanh, trứng, cà chua, sốt mè", allergens: "Trứng, mè", serving: "300 g" },
  { id: "combo-energy", sku: "FM-009", name: "Combo Energy", price: 119000, category: "combo", description: "Cơm gà · Banana Whey", icon: "FM", available: true, calories: 650, protein: 43, carbs: 75, fat: 16, ingredients: "Cơm gà Power Bowl, Banana Whey", allergens: "Sữa", serving: "1 combo" },
];
let demoInventory = readInventory();
let productModalController = null;

function readInventory() {
  try {
    const saved = localStorage.getItem(inventoryStorageKey);
    if (!saved) return defaultInventory.map((product) => ({ ...product }));
    const products = JSON.parse(saved);
    if (!Array.isArray(products) || products.some((product) =>
      !product || typeof product.id !== "string" || typeof product.name !== "string"
      || !Number.isFinite(product.price) || product.price < 1000
      || !["drink", "meal", "snack", "rice", "salad", "combo"].includes(product.category)
      || typeof product.available !== "boolean"
    )) {
      throw new TypeError("Danh sách món demo không đúng định dạng.");
    }
    return products.map((product) => {
      const defaults = defaultInventory.find((item) => item.id === product.id);
      return defaults ? { ...defaults, ...product } : {
        calories: 300, protein: 15, carbs: 30, fat: 10,
        ingredients: product.description, allergens: "Vui lòng kiểm tra thành phần",
        serving: "1 khẩu phần", ...product,
      };
    });
  } catch (error) {
    console.error("Không thể đọc danh sách món demo trong trình duyệt.", error);
    return defaultInventory.map((product) => ({ ...product }));
  }
}

function applyInventory(products) {
  demoInventory = products;
  Object.keys(demoProducts).forEach((id) => delete demoProducts[id]);
  products.forEach((product) => {
    demoProducts[product.id] = product;
  });
}

applyInventory(demoInventory);

async function prepareProductImage(file) {
  const allowedTypes = ["image/jpeg", "image/png", "image/webp"];
  if (!allowedTypes.includes(file.type)) {
    throw new TypeError("Ảnh phải có định dạng JPG, PNG hoặc WebP.");
  }
  if (file.size > 10 * 1024 * 1024) {
    throw new RangeError("Ảnh gốc không được vượt quá 10 MB.");
  }

  const bitmap = await createImageBitmap(file);
  try {
    const canvas = document.createElement("canvas");
    const maxDimension = 1000;
    const scale = Math.min(1, maxDimension / Math.max(bitmap.width, bitmap.height));
    canvas.width = Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Không thể chuẩn bị ảnh trong trình duyệt này.");
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);

    for (const dimension of [1000, 800, 600]) {
      const resize = Math.min(1, dimension / Math.max(canvas.width, canvas.height));
      const output = document.createElement("canvas");
      output.width = Math.max(1, Math.round(canvas.width * resize));
      output.height = Math.max(1, Math.round(canvas.height * resize));
      const outputContext = output.getContext("2d");
      if (!outputContext) throw new Error("Không thể xử lý ảnh trong trình duyệt này.");
      outputContext.drawImage(canvas, 0, 0, output.width, output.height);
      for (const quality of [0.82, 0.68, 0.54, 0.4]) {
        const dataUrl = output.toDataURL("image/webp", quality);
        if (dataUrl.startsWith("data:image/webp") && dataUrl.length <= 700 * 1024) return dataUrl;
      }
    }
  } finally {
    bitmap.close();
  }
  throw new RangeError("Ảnh vẫn quá lớn sau khi nén. Hãy chọn ảnh khác có dung lượng thấp hơn.");
}

function saveInventory(products) {
  try {
    localStorage.setItem(inventoryStorageKey, JSON.stringify(products));
  } catch (error) {
    console.error("Không thể lưu danh sách món demo trong trình duyệt.", error);
    showToast("Không đủ dung lượng trình duyệt để lưu món hoặc ảnh. Hãy chọn ảnh nhỏ hơn hoặc gỡ bớt ảnh demo.");
    return false;
  }
  applyInventory(products);
  renderCatalogInventory();
  renderFeaturedProductImages();
  renderAdminProducts();
  writeCart(readCart());
  renderCart();
  return true;
}

function categoryName(category) {
  return { drink: "Thức uống", meal: "Bữa ăn", snack: "Ăn nhẹ", rice: "Cơm", salad: "Salad", combo: "Combo" }[category];
}

function getProfile() {
  try {
    return JSON.parse(localStorage.getItem(profileStorageKey) || "null");
  } catch (error) {
    console.error("Không thể đọc hồ sơ demo trong trình duyệt.", error);
    return null;
  }
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

function shippingFeeFor(subtotal) {
  if (!subtotal) return 0;
  return subtotal >= 300000 ? 0 : 20000;
}

function readCart() {
  try {
    const saved = JSON.parse(localStorage.getItem(cartStorageKey) || "[]");
    if (!Array.isArray(saved)) {
      throw new TypeError("Giỏ hàng minh họa không đúng định dạng.");
    }

    return saved
      .filter((item) => item && demoProducts[item.id] && demoProducts[item.id].available !== false && Number.isInteger(item.quantity) && item.quantity > 0)
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
  const shipping = shippingFeeFor(subtotal);
  const total = subtotal + shipping;
  const lineCount = cart.reduce((sum, item) => sum + item.quantity, 0);

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

  const emptyState = document.querySelector("[data-cart-empty]");
  if (emptyState) emptyState.hidden = cart.length > 0;
  const orderHistory = document.querySelector("[data-cart-order-history]");
  const orderList = document.querySelector("[data-cart-order-list]");
  if (orderHistory && orderList) {
    const orders = getOrders();
    orderList.replaceChildren();
    orderHistory.hidden = orders.length === 0;
    orders.forEach((order) => {
      const link = document.createElement("a");
      link.className = "cart-order-history-link";
      link.href = `/orders/track/?order=${encodeURIComponent(order.id)}`;
      const label = document.createElement("span");
      label.textContent = `Ấn vào đây để theo dõi đơn ${order.id}`;
      const status = document.createElement("strong");
      status.textContent = order.cancelRequested ? "Đang chờ hủy" : order.status;
      link.append(label, status);
      orderList.append(link);
    });
  }
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

function createCatalogCard(product) {
  const card = document.createElement("article");
  card.className = "catalog-card";
  card.dataset.product = "";
  card.dataset.id = product.id;
  card.dataset.category = product.category;

  const art = document.createElement("div");
  art.className = "catalog-art catalog-art-granola";
  const tag = document.createElement("span");
  tag.className = "catalog-tag";
  tag.textContent = "MÓN MỚI";
  const icon = document.createElement("span");
  icon.className = "catalog-fruit";
  icon.textContent = product.icon || "FM";
  const illustration = document.createElement("div");
  illustration.className = "granola-illustration";
  illustration.textContent = "FM";
  const caption = document.createElement("span");
  caption.className = "art-caption";
  caption.textContent = "FITMEAL / DAILY";
  art.append(tag, icon, illustration, caption);

  const details = document.createElement("div");
  details.className = "catalog-details";
  const info = document.createElement("div");
  const name = document.createElement("h3");
  const description = document.createElement("p");
  const detailButton = document.createElement("button");
  detailButton.className = "product-detail-link";
  detailButton.type = "button";
  detailButton.dataset.productDetails = product.id;
  detailButton.textContent = "Xem dinh dưỡng";
  info.append(name, description, detailButton);
  const protein = document.createElement("span");
  protein.className = "catalog-protein";
  protein.append(document.createTextNode(`${product.protein || 0}g `));
  const proteinLabel = document.createElement("small");
  proteinLabel.textContent = "PROTEIN";
  protein.append(proteinLabel);
  details.append(info, protein);

  const buy = document.createElement("div");
  buy.className = "catalog-buy";
  const price = document.createElement("strong");
  const button = document.createElement("button");
  button.type = "button";
  button.dataset.addToCart = "";
  button.textContent = "Thêm vào giỏ";
  const plus = document.createElement("span");
  plus.textContent = "＋";
  button.append(plus);
  buy.append(price, button);
  card.append(art, details, buy);
  return card;
}

function renderCatalogInventory() {
  const grid = document.querySelector("[data-product-grid]");
  if (!grid) return;

  const cards = new Map([...grid.querySelectorAll("[data-product]")].map((card) => [card.dataset.id, card]));
  demoInventory.forEach((product) => {
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
    card.querySelector(".catalog-buy > strong").textContent = currency.format(product.price);
    let photo = card.querySelector(".catalog-product-photo");
    if (product.image) {
      if (!photo) {
        photo = document.createElement("img");
        photo.className = "catalog-product-photo";
        photo.alt = "";
        card.querySelector(".catalog-art").prepend(photo);
      }
      photo.src = product.image;
      card.querySelector(".catalog-art").classList.add("has-product-image");
    } else {
      photo?.remove();
      card.querySelector(".catalog-art").classList.remove("has-product-image");
    }
    const detailButton = card.querySelector("[data-product-details]");
    if (detailButton) detailButton.dataset.productDetails = product.id;
    const protein = card.querySelector(".catalog-protein");
    if (protein) protein.firstChild.textContent = `${product.protein || 0}g `;

    const tag = card.querySelector(".catalog-tag");
    if (!tag.dataset.defaultTag) tag.dataset.defaultTag = tag.textContent;
    const button = card.querySelector("[data-add-to-cart]");
    const soldOut = !product.available;
    card.classList.toggle("is-sold-out", soldOut);
    tag.textContent = soldOut ? "HẾT MÓN" : tag.dataset.defaultTag;
    button.disabled = soldOut;
    button.replaceChildren(document.createTextNode(soldOut ? "Đã hết món" : "Thêm vào giỏ"));
    if (!soldOut) {
      const plus = document.createElement("span");
      plus.textContent = "＋";
      button.append(plus);
    }
  });

  cards.forEach((card, id) => {
    if (!demoInventory.some((product) => product.id === id)) card.hidden = true;
  });
}

function renderFeaturedProductImages() {
  document.querySelectorAll("[data-featured-product]").forEach((card) => {
    const product = demoProducts[card.dataset.featuredProduct];
    const art = card.querySelector(".product-art");
    if (!art) return;
    let photo = art.querySelector(".product-photo");
    if (product?.image) {
      if (!photo) {
        photo = document.createElement("img");
        photo.className = "product-photo";
        photo.alt = product.name;
        art.prepend(photo);
      }
      photo.src = product.image;
      art.classList.add("has-product-image");
    } else {
      photo?.remove();
      art.classList.remove("has-product-image");
    }
  });
}

function renderAdminProducts() {
  const list = document.querySelector("[data-admin-product-list]");
  if (!list) return;
  list.replaceChildren();

  demoInventory.forEach((product) => {
    const row = document.createElement("tr");
    const nameCell = document.createElement("td");
    const productIdentity = document.createElement("div");
    productIdentity.className = "admin-product-identity";
    if (product.image) {
      const thumbnail = document.createElement("img");
      thumbnail.className = "admin-product-thumbnail";
      thumbnail.src = product.image;
      thumbnail.alt = "";
      productIdentity.append(thumbnail);
    } else {
      const placeholder = document.createElement("span");
      placeholder.className = "admin-product-thumbnail admin-product-thumbnail-empty";
      placeholder.textContent = "FM";
      productIdentity.append(placeholder);
    }
    const name = document.createElement("strong");
    name.textContent = product.name;
    productIdentity.append(name);
    nameCell.append(productIdentity);

    const sku = document.createElement("td");
    sku.textContent = product.sku;
    const category = document.createElement("td");
    category.textContent = categoryName(product.category);
    const priceCell = document.createElement("td");
    const priceEditor = document.createElement("div");
    priceEditor.className = "admin-price-editor";
    const price = document.createElement("input");
    price.type = "number";
    price.min = "1000";
    price.step = "1000";
    price.value = String(product.price);
    price.setAttribute("aria-label", `Giá bán ${product.name}`);
    const savePrice = document.createElement("button");
    savePrice.type = "button";
    savePrice.dataset.productSave = product.id;
    savePrice.textContent = "Lưu giá";
    priceEditor.append(price, savePrice);
    priceCell.append(priceEditor);

    const statusCell = document.createElement("td");
    const status = document.createElement("span");
    status.className = `status-pill ${product.available ? "status-paid" : "status-pending"}`;
    status.textContent = product.available ? "Đang bán" : "Hết món";
    statusCell.append(status);

    const actionsCell = document.createElement("td");
    const actions = document.createElement("div");
    actions.className = "admin-product-row-actions";
    const imagePicker = document.createElement("button");
    imagePicker.type = "button";
    imagePicker.dataset.productImagePicker = product.id;
    imagePicker.textContent = product.image ? "Đổi ảnh" : "Tải ảnh";
    const imageInput = document.createElement("input");
    imageInput.type = "file";
    imageInput.accept = "image/jpeg,image/png,image/webp";
    imageInput.hidden = true;
    imageInput.dataset.productImageUpload = product.id;
    const availability = document.createElement("button");
    availability.type = "button";
    availability.dataset.productAvailability = product.id;
    availability.textContent = product.available ? "Đánh dấu hết món" : "Mở bán lại";
    const remove = document.createElement("button");
    remove.type = "button";
    remove.dataset.productDelete = product.id;
    remove.textContent = "Xóa";
    actions.append(imagePicker, availability, remove);
    actionsCell.append(actions, imageInput);
    row.append(nameCell, sku, category, priceCell, statusCell, actionsCell);
    list.append(row);
  });

  const outOfStock = demoInventory.filter((product) => !product.available);
  const notice = document.querySelector("[data-out-of-stock-notice]");
  if (notice) {
    notice.hidden = outOfStock.length === 0;
    notice.textContent = outOfStock.length
      ? `⚠ ${outOfStock.length} món đang hết: ${outOfStock.map((product) => product.name).join(", ")}. Cửa hàng demo đã tạm khóa nút đặt món.`
      : "";
  }
}

function initializeCatalog() {
  const productGrid = document.querySelector("[data-product-grid]");
  if (!productGrid) return;

  renderCatalogInventory();
  let selectedCategory = "all";
  const search = document.querySelector("[data-product-search]");
  const sort = document.querySelector("[data-product-sort]");
  const proteinFilter = document.querySelector("[data-protein-filter]");
  const calorieFilter = document.querySelector("[data-calorie-filter]");
  const priceMin = document.querySelector("[data-price-min]");
  const priceMax = document.querySelector("[data-price-max]");
  const emptyResults = document.querySelector("[data-empty-results]");
  const products = [...productGrid.querySelectorAll("[data-product]")];

  function filterProducts() {
    const searchTerm = search.value.trim().toLocaleLowerCase("vi");
    products.forEach((product) => {
      const matchesCategory = selectedCategory === "all" || product.dataset.category === selectedCategory;
      const matchesSearch = `${product.dataset.name} ${product.dataset.search}`.toLocaleLowerCase("vi").includes(searchTerm);
      const nutrition = demoProducts[product.dataset.id];
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
        chip.setAttribute("aria-pressed", String(chip === button));
      });
      filterProducts();
    });
  });

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
    if (!demoProducts[productCard.dataset.id]?.available) {
      showToast(`${productCard.dataset.name} hiện đã hết món.`);
      return;
    }
    const cart = readCart();
    const existing = cart.find((item) => item.id === productCard.dataset.id);
    if (existing) existing.quantity += 1;
    else cart.push({ id: productCard.dataset.id, quantity: 1 });
    writeCart(cart);
    showToast(`${productCard.dataset.name} đã được thêm vào giỏ.`);
  });
}

function showProductDetails(productId) {
  const product = demoProducts[productId];
  const modal = document.querySelector("[data-product-modal]");
  if (!product || !modal) return;
  const photo = modal.querySelector("[data-detail-image]");
  if (photo) {
    photo.src = product.image || "";
    photo.hidden = !product.image;
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
    const product = demoProducts[productId];
    if (!product || !product.available) {
      showToast("Món này hiện đã hết.");
      return;
    }
    const cart = readCart();
    const existing = cart.find((item) => item.id === productId);
    if (existing) existing.quantity += 1;
    else cart.push({ id: productId, quantity: 1 });
    writeCart(cart);
    close();
    showToast(`${product.name} đã được thêm vào giỏ.`);
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

  window.addEventListener("storage", (event) => {
    if (event.key === orderStorageKey) renderCart();
  });
}

function initializeCheckout() {
  const form = document.querySelector("[data-checkout-form]");
  if (!form) return;

  const modal = document.querySelector("[data-order-modal]");
  const dialog = createDialogController(modal, "[data-close-modal]");
  const dateInput = form.elements["delivery-date"];
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  dateInput.min = `${tomorrow.getFullYear()}-${String(tomorrow.getMonth() + 1).padStart(2, "0")}-${String(tomorrow.getDate()).padStart(2, "0")}`;
  dateInput.value = dateInput.min;

  const onlineOptions = document.querySelector("[data-payment-demo]");
  form.querySelectorAll('input[name="payment"]').forEach((input) => {
    input.addEventListener("change", () => {
      onlineOptions.hidden = input.value !== "online" || !input.checked;
    });
  });

  document.querySelector("[data-fill-profile]")?.addEventListener("click", () => {
    const profile = getProfile();
    if (!profile) {
      showToast("Chưa có hồ sơ demo. Bạn có thể nhập thông tin nhận hàng bên dưới.");
      return;
    }
    ["name", "email", "phone", "address"].forEach((key) => {
      if (profile[key]) form.elements[key].value = profile[key];
    });
    showToast("Đã điền thông tin từ hồ sơ demo.");
  });

  const closeModal = dialog.close;

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!readCart().length) {
      showToast("Giỏ hàng đang trống. Hãy thêm sản phẩm trước khi đặt.");
      return;
    }

    const values = new FormData(form);
    const payment = values.get("payment").toString();
    const paymentSucceeded = payment !== "online" || values.get("payment-result") === "success";
    const resultMessage = document.querySelector("[data-order-result-message]");
    const modalTitle = document.querySelector("#confirmation-title");
    const confirmationIcon = document.querySelector(".confirmation-check");
    if (!paymentSucceeded) {
      modalTitle.textContent = "Thanh toán chưa thành công";
      resultMessage.textContent = "Đây là kết quả mô phỏng. Đơn chưa được tạo; giỏ hàng vẫn được giữ để bạn thử lại hoặc chọn COD.";
      confirmationIcon.textContent = "!";
      confirmationIcon.classList.add("is-payment-failed");
      document.querySelector("[data-demo-order-id]").textContent = "Chưa tạo đơn";
      document.querySelector("[data-order-cart-link]").hidden = true;
      dialog.open();
      return;
    }

    const orderId = `FM-DEMO-${Date.now().toString().slice(-6)}`;
    const cart = readCart();
    const subtotal = cart.reduce((sum, item) => sum + demoProducts[item.id].price * item.quantity, 0);
    const order = {
      id: orderId,
      createdAt: new Date().toISOString(),
      items: cart.map((item) => ({
        id: item.id,
        name: demoProducts[item.id].name,
        price: demoProducts[item.id].price,
        quantity: item.quantity,
      })),
      subtotal,
      shipping: shippingFeeFor(subtotal),
      total: subtotal + shippingFeeFor(subtotal),
      name: values.get("name").toString(),
      email: values.get("email").toString(),
      phone: values.get("phone").toString(),
      address: `${values.get("address")}, ${values.get("district")}, ${values.get("city")}`,
      deliveryDate: values.get("delivery-date").toString(),
      deliverySlot: values.get("delivery-slot").toString(),
      note: values.get("note").toString(),
      payment,
      paymentStatus: payment === "online" ? "Đã thanh toán demo" : "Thanh toán khi nhận hàng",
      status: "Chờ xác nhận",
      cancelRequested: false,
    };
    const orders = getOrders();
    orders.unshift(order);
    saveOrders(orders);
    localStorage.setItem("fitmeal-demo-last-order", orderId);
    document.querySelector("[data-demo-order-id]").textContent = orderId;
    modalTitle.textContent = "Đơn minh họa đã sẵn sàng";
    resultMessage.textContent = payment === "online"
      ? "Thanh toán demo thành công. Vào giỏ hàng để theo dõi đơn; không có giao dịch thật được thực hiện."
      : "Đơn COD demo đã được ghi nhận. Vào giỏ hàng để theo dõi đơn.";
    document.querySelector("[data-order-cart-link]").hidden = false;
    confirmationIcon.textContent = "✓";
    confirmationIcon.classList.remove("is-payment-failed");
    dialog.open();
    writeCart([]);
    renderCart();
  });

  document.querySelector("[data-close-modal]").addEventListener("click", closeModal);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeModal();
  });
}

function initializeTracking() {
  const form = document.querySelector("[data-tracking-form]");
  if (!form) return;

  const list = document.querySelector("[data-tracking-history]");
  let selectedOrderId = "";
  const renderHistory = () => {
    const orders = getOrders();
    list.replaceChildren();
    if (!orders.length) {
      const empty = document.createElement("p");
      empty.className = "tracking-history-empty";
      empty.textContent = "Đơn đặt trong trình duyệt này sẽ xuất hiện ở đây.";
      list.append(empty);
      return;
    }
    const wrapper = document.createElement("div");
    wrapper.className = "tracking-history-list";
    orders.forEach((order) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "tracking-history-item";
      button.dataset.historyOrder = order.id;
      const info = document.createElement("span");
      const id = document.createElement("strong");
      id.textContent = order.id;
      const date = document.createElement("small");
      date.textContent = new Date(order.createdAt).toLocaleDateString("vi-VN");
      info.append(id, date);
      const state = document.createElement("strong");
      state.textContent = order.cancelRequested ? "Đang chờ hủy" : order.status;
      button.append(info, state);
      wrapper.append(button);
    });
    list.append(wrapper);
  };

  const renderOrder = (order) => {
    if (!order) {
      showToast("Không tìm thấy mã đơn trong lịch sử demo của trình duyệt này.");
      return;
    }
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

  renderHistory();
  const lastDemoOrder = localStorage.getItem("fitmeal-demo-last-order");
  const requestedOrder = new URLSearchParams(window.location.search).get("order") || lastDemoOrder;
  if (requestedOrder) {
    form.elements.order.value = requestedOrder;
    const lastOrder = getOrders().find((order) => order.id === requestedOrder);
    if (lastOrder) renderOrder(lastOrder);
  }

  list.addEventListener("click", (event) => {
    const button = event.target.closest("[data-history-order]");
    if (!button) return;
    form.elements.order.value = button.dataset.historyOrder;
    renderOrder(getOrders().find((order) => order.id === button.dataset.historyOrder));
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const orderId = new FormData(form).get("order").toString().trim();
    if (!orderId) return;
    const order = getOrders().find((item) => item.id === orderId);
    if (!order) {
      showToast("Mã đơn không có trong lịch sử demo của trình duyệt này.");
      return;
    }
    renderOrder(order);
    showToast("Đang hiển thị tiến trình đơn hàng mẫu.");
  });

  document.querySelector("[data-cancel-order]").addEventListener("click", () => {
    const order = getOrders().find((item) => item.id === selectedOrderId);
    if (!order || !["Chờ xác nhận", "Đang chuẩn bị"].includes(order.status)) {
      showToast("Đơn này không còn ở trạng thái cho phép yêu cầu hủy.");
      return;
    }
    const orders = getOrders().map((item) => item.id === order.id ? { ...item, cancelRequested: true } : item);
    saveOrders(orders);
    renderHistory();
    renderOrder(orders.find((item) => item.id === order.id));
    showToast("Đã ghi nhận yêu cầu hủy trong dữ liệu demo.");
  });

  window.addEventListener("storage", (event) => {
    if (event.key !== orderStorageKey) return;
    renderHistory();
    if (selectedOrderId) renderOrder(getOrders().find((order) => order.id === selectedOrderId));
  });
}

function initializeInventorySync() {
  window.addEventListener("storage", (event) => {
    if (event.key !== inventoryStorageKey) return;
    applyInventory(readInventory());
    renderCatalogInventory();
    renderFeaturedProductImages();
    renderAdminProducts();
    writeCart(readCart());
    renderCart();
  });
}

function initializeAccount() {
  const tabs = document.querySelectorAll("[data-account-tab]");
  if (!tabs.length) return;
  const authView = document.querySelector("[data-account-auth-view]");
  const profileView = document.querySelector("[data-account-profile]");
  const profileForm = document.querySelector("[data-profile-form]");
  const orderList = document.querySelector("[data-account-orders]");

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

  function renderAccountOrders() {
    orderList.replaceChildren();
    const orders = getOrders();
    if (!orders.length) {
      const empty = document.createElement("p");
      empty.className = "tracking-history-empty";
      empty.textContent = "Bạn chưa có đơn hàng demo nào trên trình duyệt này.";
      orderList.append(empty);
      return;
    }
    const list = document.createElement("div");
    list.className = "account-order-history-list";
    orders.forEach((order) => {
      const link = document.createElement("a");
      link.className = "account-order-history-item";
      link.href = `/orders/track/?order=${encodeURIComponent(order.id)}`;
      const info = document.createElement("span");
      const id = document.createElement("strong");
      id.textContent = order.id;
      const date = document.createElement("small");
      date.textContent = `${new Date(order.createdAt).toLocaleDateString("vi-VN")} · ${order.items.length} món`;
      info.append(id, date);
      const status = document.createElement("strong");
      status.textContent = order.cancelRequested ? "Chờ hủy" : order.status;
      link.append(info, status);
      list.append(link);
    });
    orderList.append(list);
  }

  function showAccountProfile() {
    const profile = getProfile();
    const isSignedIn = localStorage.getItem(sessionStorageKey) === "1"
      || sessionStorage.getItem(sessionStorageKey) === "1";
    if (!profile || !isSignedIn) {
      authView.hidden = false;
      profileView.hidden = true;
      return;
    }
    authView.hidden = true;
    profileView.hidden = false;
    document.querySelector("[data-profile-greeting]").textContent = profile.name || "bạn";
    ["name", "email", "phone", "address"].forEach((key) => {
      profileForm.elements[key].value = profile[key] || "";
    });
    renderAccountOrders();
  }

  const initialTab = window.location.hash === "#register" ? "register" : "login";
  activateAccountTab(initialTab);
  showAccountProfile();

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
      if (form.dataset.accountForm === "register") {
        const values = new FormData(form);
        const password = values.get("password").toString();
        if (password !== values.get("password-confirm").toString()) {
          feedback.textContent = "Mật khẩu nhập lại chưa khớp.";
          form.elements["password-confirm"].focus();
          return;
        }
        const profile = {
          name: values.get("name").toString().trim(),
          email: values.get("email").toString().trim().toLocaleLowerCase("vi"),
          phone: values.get("phone").toString().trim(),
          address: values.get("address").toString().trim(),
        };
        localStorage.setItem(profileStorageKey, JSON.stringify(profile));
        sessionStorage.setItem(sessionStorageKey, "1");
        form.reset();
        showAccountProfile();
        showToast("Đã tạo hồ sơ demo trên trình duyệt này.");
        return;
      }

      if (form.dataset.accountForm === "login") {
        const profile = getProfile();
        const loginId = form.querySelector('input[autocomplete="username"]').value.trim().toLocaleLowerCase("vi");
        const phoneLogin = loginId.replace(/\D/g, "");
        const matchesEmail = profile && loginId === profile.email.toLocaleLowerCase("vi");
        const matchesPhone = profile && phoneLogin && phoneLogin === (profile.phone || "").replace(/\D/g, "");
        if (!profile || (!matchesEmail && !matchesPhone)) {
          feedback.textContent = "Chưa tìm thấy hồ sơ demo có email hoặc số điện thoại này trên trình duyệt. Hãy tạo tài khoản demo trước.";
          return;
        }
        const remember = form.querySelector('input[type="checkbox"]').checked;
        if (remember) localStorage.setItem(sessionStorageKey, "1");
        else {
          localStorage.removeItem(sessionStorageKey);
          sessionStorage.setItem(sessionStorageKey, "1");
        }
        form.reset();
        showAccountProfile();
        showToast("Đăng nhập demo thành công.");
        return;
      }

      feedback.textContent = "Đã nhận yêu cầu demo. Chưa gửi email khôi phục thật.";
    });
  });

  document.querySelector("[data-account-forgot]")?.addEventListener("click", () => {
    activateAccountTab("reset");
    document.querySelector('[data-account-form="reset"] input').value =
      getProfile()?.email || document.querySelector('[data-account-form="login"] input[autocomplete="username"]').value;
  });
  document.querySelector("[data-back-to-login]")?.addEventListener("click", () => activateAccountTab("login"));

  profileForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    const values = new FormData(profileForm);
    const profile = Object.fromEntries(["name", "email", "phone", "address"].map((key) => [key, values.get(key).toString().trim()]));
    localStorage.setItem(profileStorageKey, JSON.stringify(profile));
    document.querySelector("[data-profile-greeting]").textContent = profile.name || "bạn";
    document.querySelector("[data-profile-feedback]").textContent = "Đã cập nhật hồ sơ demo trên trình duyệt này.";
  });

  document.querySelector("[data-account-logout]")?.addEventListener("click", () => {
    localStorage.removeItem(sessionStorageKey);
    sessionStorage.removeItem(sessionStorageKey);
    showAccountProfile();
    activateAccountTab("login");
    showToast("Đã đăng xuất khỏi tài khoản demo.");
  });

  window.addEventListener("storage", (event) => {
    if (event.key === orderStorageKey && !profileView.hidden) renderAccountOrders();
    if (event.key === profileStorageKey && !profileView.hidden) showAccountProfile();
  });
}

function initializeAdmin() {
  const tabs = document.querySelectorAll("[data-admin-tab]");
  if (!tabs.length) return;

  renderAdminProducts();

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

  const productForm = document.querySelector("[data-product-form]");
  const productFormToggle = document.querySelector("[data-product-form-toggle]");
  const productImageInput = productForm?.elements.image;
  const productImagePreview = document.querySelector("[data-product-image-preview]");
  const productImagePreviewImage = document.querySelector("[data-product-image-preview-img]");
  let productImagePreviewUrl = "";
  productFormToggle?.addEventListener("click", () => {
    const isOpening = productForm.hidden;
    productForm.hidden = !isOpening;
    productFormToggle.setAttribute("aria-expanded", String(isOpening));
    if (isOpening) productForm.elements.name.focus();
  });

  productImageInput?.addEventListener("change", () => {
    const file = productImageInput.files[0];
    productImageInput.setCustomValidity("");
    if (productImagePreviewUrl) URL.revokeObjectURL(productImagePreviewUrl);
    productImagePreviewUrl = "";
    if (!file) {
      productImagePreview.hidden = true;
      return;
    }
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type) || file.size > 10 * 1024 * 1024) {
      productImageInput.setCustomValidity("Chọn ảnh JPG, PNG hoặc WebP không quá 10 MB.");
      productImageInput.reportValidity();
      productImageInput.setCustomValidity("");
      productImageInput.value = "";
      productImagePreview.hidden = true;
      return;
    }
    productImagePreviewUrl = URL.createObjectURL(file);
    productImagePreviewImage.src = productImagePreviewUrl;
    productImagePreview.hidden = false;
  });

  document.querySelector("[data-clear-product-image]")?.addEventListener("click", () => {
    if (productImagePreviewUrl) URL.revokeObjectURL(productImagePreviewUrl);
    productImagePreviewUrl = "";
    productImageInput.value = "";
    productImagePreview.hidden = true;
    productImageInput.focus();
  });

  productForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = new FormData(productForm);
    const name = values.get("name").toString().trim();
    const price = Number(values.get("price"));
    const description = values.get("description").toString().trim();
    if (!name || !description || !Number.isFinite(price) || price < 1000) {
      notify("Vui lòng nhập tên, mô tả và giá bán hợp lệ.");
      return;
    }

    const baseId = name.normalize("NFD").replace(/[\u0300-\u036f]/g, "")
      .toLocaleLowerCase("vi").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "mon-moi";
    let id = baseId;
    let suffix = 2;
    while (demoInventory.some((product) => product.id === id)) {
      id = `${baseId}-${suffix}`;
      suffix += 1;
    }
    const nextSku = Math.max(0, ...demoInventory.map((product) => Number(product.sku.slice(3)) || 0)) + 1;
    const category = values.get("category").toString();
    const imageFile = values.get("image");
    let image = "";
    if (imageFile instanceof File && imageFile.size) {
      try {
        image = await prepareProductImage(imageFile);
      } catch (error) {
        console.error("Không thể xử lý ảnh sản phẩm.", error);
        notify(error instanceof Error ? error.message : "Không thể xử lý ảnh đã chọn.");
        return;
      }
    }
    const product = {
      id,
      sku: `FM-${String(nextSku).padStart(3, "0")}`,
      name,
      price,
      category,
      description,
      ...(image ? { image } : {}),
      icon: category === "drink" ? "✳" : category === "meal" ? "F" : "FM",
      available: true,
    };
    if (!saveInventory([...demoInventory, product])) return;
    productForm.reset();
    if (productImagePreviewUrl) URL.revokeObjectURL(productImagePreviewUrl);
    productImagePreviewUrl = "";
    productImagePreview.hidden = true;
    productForm.hidden = true;
    productFormToggle.setAttribute("aria-expanded", "false");
    notify(`${name} đã được thêm vào danh sách demo.`);
  });

  const productList = document.querySelector("[data-admin-product-list]");
  productList?.addEventListener("click", (event) => {
    const imagePicker = event.target.closest("[data-product-image-picker]");
    if (imagePicker) {
      imagePicker.closest("tr").querySelector("[data-product-image-upload]").click();
      return;
    }
    const saveButton = event.target.closest("[data-product-save]");
    const availabilityButton = event.target.closest("[data-product-availability]");
    const deleteButton = event.target.closest("[data-product-delete]");
    if (!saveButton && !availabilityButton && !deleteButton) return;

    const target = saveButton || availabilityButton || deleteButton;
    const product = demoInventory.find((item) => item.id === target.dataset.productSave
      || item.id === target.dataset.productAvailability || item.id === target.dataset.productDelete);
    if (!product) return;

    if (saveButton) {
      const input = saveButton.closest(".admin-price-editor").querySelector("input");
      const price = Number(input.value);
      if (!input.checkValidity() || !Number.isFinite(price) || price < 1000) {
        input.reportValidity();
        return;
      }
      if (!saveInventory(demoInventory.map((item) => item.id === product.id ? { ...item, price } : item))) return;
      notify(`Đã cập nhật giá demo của ${product.name}.`);
    } else if (availabilityButton) {
      const available = !product.available;
      if (!saveInventory(demoInventory.map((item) => item.id === product.id ? { ...item, available } : item))) return;
      notify(available
        ? `${product.name} đã được mở bán lại trong bản demo.`
        : `Đã thông báo ${product.name} hết món trên cửa hàng demo.`);
    } else if (window.confirm(`Bạn có chắc muốn xóa "${product.name}" khỏi danh sách demo?`)) {
      if (!saveInventory(demoInventory.filter((item) => item.id !== product.id))) return;
      notify(`${product.name} đã được xóa khỏi danh sách demo.`);
    }
  });

  productList?.addEventListener("change", async (event) => {
    const input = event.target.closest("[data-product-image-upload]");
    const file = input?.files[0];
    if (!input || !file) return;
    const product = demoInventory.find((item) => item.id === input.dataset.productImageUpload);
    if (!product) {
      notify("Không tìm thấy món cần cập nhật ảnh.");
      return;
    }
    try {
      const image = await prepareProductImage(file);
      if (!saveInventory(demoInventory.map((item) => item.id === product.id ? { ...item, image } : item))) return;
      notify(`Đã cập nhật ảnh cho ${product.name}.`);
    } catch (error) {
      console.error("Không thể cập nhật ảnh sản phẩm.", error);
      notify(error instanceof Error ? error.message : "Không thể xử lý ảnh đã chọn.");
    } finally {
      input.value = "";
    }
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
renderFeaturedProductImages();
initializeProductModal();
initializeCatalog();
initializeCart();
initializeCheckout();
initializeTracking();
initializeAccount();
initializeAdmin();
initializeInventorySync();
initializeMobileNavigation();
initializeLanguages();
