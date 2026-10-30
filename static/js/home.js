const productTrack = document.querySelector("#nutrition");

if (productTrack) {
  document.querySelectorAll("[data-carousel-direction]").forEach((button) => {
  button.addEventListener("click", () => {
    const direction = Number(button.dataset.carouselDirection);
    const card = productTrack.querySelector(".product-card");
    const gap = Number.parseFloat(getComputedStyle(productTrack).columnGap) || 0;

    productTrack.scrollBy({
      left: direction * (card.getBoundingClientRect().width + gap),
      behavior: "smooth",
    });
  });
  });
}

const menuToggle = document.querySelector(".menu-toggle");
const primaryNavigation = document.querySelector("#primary-navigation");

if (menuToggle && primaryNavigation) {
  menuToggle.addEventListener("click", () => {
    const isExpanded = menuToggle.getAttribute("aria-expanded") === "true";
    menuToggle.setAttribute("aria-expanded", String(!isExpanded));
    menuToggle.setAttribute("aria-label", isExpanded ? "Mở menu" : "Đóng menu");
    primaryNavigation.classList.toggle("is-open", !isExpanded);
  });

  primaryNavigation.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      menuToggle.setAttribute("aria-expanded", "false");
      menuToggle.setAttribute("aria-label", "Mở menu");
      primaryNavigation.classList.remove("is-open");
    });
  });
}

function updateHomeCartCount() {
  const countBadges = document.querySelectorAll("[data-cart-count]");
  if (!countBadges.length) return;

  try {
    const cart = JSON.parse(localStorage.getItem("fitmeal-demo-cart") || "[]");
    const count = Array.isArray(cart)
      ? cart.reduce((total, item) => total + (Number.isInteger(item.quantity) && item.quantity > 0 ? item.quantity : 0), 0)
      : 0;
    countBadges.forEach((badge) => {
      badge.textContent = String(count);
    });
  } catch (error) {
    console.error("Không thể đọc số lượng giỏ hàng minh họa.", error);
    countBadges.forEach((badge) => {
      badge.textContent = "0";
    });
  }
}

function initializeHomeLanguages() {
  document.querySelectorAll("[data-language]").forEach((button) => {
    button.addEventListener("click", () => {
      const status = button.closest("[aria-label='Ngôn ngữ giao diện']")?.querySelector("[data-language-status]");
      if (button.dataset.language === "en") {
        if (status) status.textContent = "Phiên bản tiếng Anh chưa có. Giao diện hiện vẫn hiển thị tiếng Việt.";
        return;
      }

      button.closest("[aria-label='Ngôn ngữ giao diện']").querySelectorAll("[data-language]").forEach((languageButton) => {
        const isActive = languageButton === button;
        languageButton.classList.toggle("is-active", isActive);
        languageButton.setAttribute("aria-pressed", String(isActive));
      });
      if (status) status.textContent = "Giao diện hiện hiển thị tiếng Việt.";
    });
  });
}

updateHomeCartCount();
initializeHomeLanguages();
