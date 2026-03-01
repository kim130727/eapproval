document.addEventListener("DOMContentLoaded", function () {
  function syncCheckedClass(box) {
    box.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
      const label = cb.closest("label");
      if (!label) return;
      label.classList.toggle("is-checked", cb.checked);
    });
  }

  function getCheckedIdsInDomOrder(box) {
    const ids = [];
    const items = box.querySelectorAll("li");
    items.forEach((li) => {
      const cb = li.querySelector('input[type="checkbox"]');
      if (cb && cb.checked) ids.push(String(cb.value));
    });
    return ids;
  }

  function setupSimpleBox(boxId) {
    const box = document.getElementById(boxId);
    if (!box) return;
    syncCheckedClass(box);
    box.addEventListener("change", () => syncCheckedClass(box));
  }

  function setupApproversPointerSort(approversBoxId, hiddenId) {
    const box = document.getElementById(approversBoxId);
    const hidden = document.getElementById(hiddenId);
    if (!box || !hidden) return;

    const ul = box.querySelector("ul");
    if (!ul) return;

    // ✅ li 맨 앞에 handle을 넣는다 (label 밖!)
    ul.querySelectorAll("li").forEach((li) => {
      if (li.querySelector(".drag-handle")) return;

      const handle = document.createElement("div");
      handle.className = "drag-handle";
      handle.textContent = "↕️";
      handle.setAttribute("aria-label", "드래그로 순서 변경");

      li.insertBefore(handle, li.firstChild);
    });

    syncCheckedClass(box);
    hidden.value = getCheckedIdsInDomOrder(box).join(",");

    box.addEventListener("change", function (e) {
      const t = e.target;
      if (t && t.type === "checkbox") {
        syncCheckedClass(box);
        hidden.value = getCheckedIdsInDomOrder(box).join(",");
      }
    });

    let draggingLi = null;
    let placeholder = null;

    function makePlaceholder(heightPx) {
      const ph = document.createElement("li");
      ph.className = "placeholder";
      ph.style.height = heightPx + "px";
      return ph;
    }

    function getLiUnderPointer(clientY) {
      const lis = Array.from(ul.querySelectorAll("li")).filter(
        (li) => li !== draggingLi && li !== placeholder
      );
      for (const li of lis) {
        const rect = li.getBoundingClientRect();
        const mid = rect.top + rect.height / 2;
        if (clientY < mid) return li;
      }
      return null;
    }

    function onPointerMove(e) {
      if (!draggingLi || !placeholder) return;

      const targetLi = getLiUnderPointer(e.clientY);
      if (targetLi) ul.insertBefore(placeholder, targetLi);
      else ul.appendChild(placeholder);
    }

    function endDrag() {
      if (!draggingLi || !placeholder) return;

      draggingLi.classList.remove("dragging");
      ul.insertBefore(draggingLi, placeholder);
      placeholder.remove();

      draggingLi = null;
      placeholder = null;

      hidden.value = getCheckedIdsInDomOrder(box).join(",");
    }

    // 핸들에서만 드래그 시작
    ul.querySelectorAll(".drag-handle").forEach((handle) => {
      handle.addEventListener("pointerdown", function (e) {
        const li = e.target.closest("li");
        if (!li) return;

        draggingLi = li;
        draggingLi.classList.add("dragging");

        const rect = li.getBoundingClientRect();
        placeholder = makePlaceholder(rect.height);

        ul.insertBefore(placeholder, draggingLi.nextSibling);

        // 스크롤/클릭 방지
        e.preventDefault();
        e.stopPropagation();

        // capture로 안정화
        if (handle.setPointerCapture) {
          handle.setPointerCapture(e.pointerId);
        }

        document.addEventListener("pointermove", onPointerMove, { passive: false });

        document.addEventListener("pointerup", function _up() {
          document.removeEventListener("pointermove", onPointerMove);
          document.removeEventListener("pointerup", _up);
          endDrag();
        });
      });
    });

    const form = box.closest("form");
    if (form) {
      form.addEventListener("submit", function () {
        hidden.value = getCheckedIdsInDomOrder(box).join(",");
      });
    }
  }

  setupSimpleBox("consultantsBox");
  setupSimpleBox("receiversBox");

  setupApproversPointerSort("approversBox", "id_approvers_order");

  // ✅ 상신 버튼 연타 방지 + 로딩 표시
  const formEl = document.querySelector("form[enctype='multipart/form-data']");
  const btn = document.getElementById("submitBtn");
  const txt = document.getElementById("submitText");
  const sp = document.getElementById("submitSpinner");

  if (formEl && btn) {
    let submitting = false;
    formEl.addEventListener("submit", function () {
      if (submitting) return false;
      submitting = true;

      btn.disabled = true;
      btn.style.opacity = "0.7";
      btn.style.cursor = "not-allowed";
      if (txt) txt.textContent = "상신 중...";
      if (sp) sp.style.display = "inline";
    });
  }
});