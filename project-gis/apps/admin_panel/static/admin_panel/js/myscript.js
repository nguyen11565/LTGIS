// Simple cart using localStorage

function getCart() {
  try {
    return JSON.parse(localStorage.getItem("cart") || "[]");
  } catch (e) {
    return [];
  }
}

function saveCart(cart) {
  localStorage.setItem("cart", JSON.stringify(cart));
}

function addToCart(product) {
  const cart = getCart();
  const existing = cart.find((item) => item.name === product.name);
  if (existing) {
    existing.qty += 1;
  } else {
    cart.push({ ...product, qty: 1 });
  }
  saveCart(cart);
}

function formatVND(value) {
  return new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND" }).format(value);
}

function renderCart() {
  const tbody = document.getElementById("cart-items");
  const emptyBox = document.getElementById("cart-empty");
  const contentBox = document.getElementById("cart-content");
  const totalEl = document.getElementById("cart-total");
  if (!tbody || !emptyBox || !contentBox || !totalEl) return;

  const cart = getCart();
  tbody.innerHTML = "";

  if (cart.length === 0) {
    emptyBox.classList.remove("d-none");
    contentBox.classList.add("d-none");
    totalEl.textContent = "0₫";
    return;
  }

  emptyBox.classList.add("d-none");
  contentBox.classList.remove("d-none");

  let total = 0;
  cart.forEach((item, index) => {
    const lineTotal = item.price * item.qty;
    total += lineTotal;
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${item.name}</td>
      <td class="text-center">
        <button class="btn btn-sm btn-outline-light px-2 js-cart-minus" data-index="${index}">-</button>
        <span class="mx-2">${item.qty}</span>
        <button class="btn btn-sm btn-outline-light px-2 js-cart-plus" data-index="${index}">+</button>
      </td>
      <td class="text-end">${formatVND(item.price)}</td>
      <td class="text-end">${formatVND(lineTotal)}</td>
      <td class="text-end">
        <button class="btn btn-sm btn-outline-danger js-cart-remove" data-index="${index}">Xóa</button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  totalEl.textContent = formatVND(total);
}

document.addEventListener("DOMContentLoaded", function () {
  // Add to cart buttons on home page
  document.querySelectorAll(".js-add-to-cart").forEach((btn) => {
    btn.addEventListener("click", function () {
      const name = this.getAttribute("data-name");
      const price = parseInt(this.getAttribute("data-price") || "0", 10);
      if (!name || !price) return;
      addToCart({ name, price });
      window.location.href = "/cart/";
    });
  });

  // Cart page interactions
  const cartTable = document.getElementById("cart-items");
  if (cartTable) {
    renderCart();
    cartTable.addEventListener("click", function (e) {
      const target = e.target;
      const cart = getCart();
      if (target.classList.contains("js-cart-plus")) {
        const idx = parseInt(target.getAttribute("data-index"), 10);
        if (!isNaN(idx) && cart[idx]) {
          cart[idx].qty += 1;
          saveCart(cart);
          renderCart();
        }
      } else if (target.classList.contains("js-cart-minus")) {
        const idx = parseInt(target.getAttribute("data-index"), 10);
        if (!isNaN(idx) && cart[idx]) {
          cart[idx].qty -= 1;
          if (cart[idx].qty <= 0) {
            cart.splice(idx, 1);
          }
          saveCart(cart);
          renderCart();
        }
      } else if (target.classList.contains("js-cart-remove")) {
        const idx = parseInt(target.getAttribute("data-index"), 10);
        if (!isNaN(idx)) {
          cart.splice(idx, 1);
          saveCart(cart);
          renderCart();
        }
      }
    });

    const checkoutBtn = document.getElementById("btn-checkout");
    if (checkoutBtn) {
      checkoutBtn.addEventListener("click", function () {
        alert("Đây là bản demo, chức năng thanh toán chưa được kết nối.");
      });
    }
  }

  // Sorting for all products section
  const grid = document.getElementById("catalog-grid");
  if (grid) {
    const items = Array.from(grid.querySelectorAll(".catalog-item"));
    items.forEach((item, index) => item.setAttribute("data-index", String(index)));

    function applySort(mode) {
      const sorted = [...items];
      if (mode === "price-asc") {
        sorted.sort((a, b) => parseInt(a.dataset.price || "0", 10) - parseInt(b.dataset.price || "0", 10));
      } else if (mode === "price-desc") {
        sorted.sort((a, b) => parseInt(b.dataset.price || "0", 10) - parseInt(a.dataset.price || "0", 10));
      } else {
        sorted.sort((a, b) => parseInt(a.dataset.index || "0", 10) - parseInt(b.dataset.index || "0", 10));
      }
      sorted.forEach((el) => grid.appendChild(el));
    }

    document.querySelectorAll(".js-sort-btn").forEach((btn) => {
      btn.addEventListener("click", function () {
        document.querySelectorAll(".js-sort-btn").forEach((b) => b.classList.remove("active"));
        this.classList.add("active");
        const mode = this.getAttribute("data-sort") || "default";
        applySort(mode);
      });
    });
  }
});
