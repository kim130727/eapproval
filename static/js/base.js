(function () {
  const btn = document.getElementById("profileBtn");
  const pop = document.getElementById("profilePopover");
  if (!btn || !pop) return;

  function open() {
    pop.classList.add("open");
    btn.setAttribute("aria-expanded", "true");
  }
  function close() {
    pop.classList.remove("open");
    btn.setAttribute("aria-expanded", "false");
  }
  function toggle() {
    pop.classList.contains("open") ? close() : open();
  }

  btn.addEventListener("click", function (e) {
    e.preventDefault();
    e.stopPropagation();
    toggle();
  });

  pop.addEventListener("click", function (e) {
    // 팝오버 안 클릭은 닫히지 않게
    e.stopPropagation();
  });

  document.addEventListener("click", function () {
    close();
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") close();
  });
})();