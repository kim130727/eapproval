document.addEventListener("DOMContentLoaded", function () {
  function qsa(el, sel) {
    return Array.from(el.querySelectorAll(sel));
  }

  function syncCheckedClass(box) {
    qsa(box, 'input[type="checkbox"]').forEach((cb) => {
      const label = cb.closest("label");
      if (!label) return;

      label.classList.toggle("is-checked", cb.checked);

      const li = cb.closest("li");
      if (li) li.classList.toggle("is-checked", cb.checked);

      // 체크된 항목만 핸들 활성/표시
      const handle = li ? li.querySelector(".drag-handle") : null;
      if (handle) {
        handle.style.visibility = cb.checked ? "visible" : "hidden";
        handle.style.pointerEvents = cb.checked ? "auto" : "none";
        handle.setAttribute("aria-disabled", cb.checked ? "false" : "true");
      }
    });
  }

  function getCheckedIdsInDomOrder(box) {
    const ids = [];
    qsa(box, "li").forEach((li) => {
      const cb = li.querySelector('input[type="checkbox"]');
      if (cb && cb.checked) ids.push(String(cb.value));
    });
    return ids;
  }

  function setupSimpleBox(boxId) {
    const box = document.getElementById(boxId);
    if (!box) return;

    syncCheckedClass(box);
    box.addEventListener("change", function () {
      syncCheckedClass(box);
    });
  }

  // Django가 어떤 형태로 렌더하든 approversBox 내부를 <ul><li> 구조로 표준화
  function normalizeToUlLi(box) {
    let ul = box.querySelector("ul");
    if (ul) return ul;

    const checkboxes = qsa(box, 'input[type="checkbox"]');
    if (checkboxes.length === 0) return null;

    ul = document.createElement("ul");

    checkboxes.forEach((cb) => {
      const label = cb.closest("label") || cb.parentElement;

      const li = document.createElement("li");
      if (label) {
        li.appendChild(label);
      } else {
        const fallback = document.createElement("label");
        fallback.appendChild(cb);
        li.appendChild(fallback);
      }
      ul.appendChild(li);
    });

    box.innerHTML = "";
    box.appendChild(ul);
    return ul;
  }

  function setupApproversPointerSort(approversBoxId, hiddenId) {
    const box = document.getElementById(approversBoxId);
    const hidden = document.getElementById(hiddenId);
    if (!box || !hidden) return;

    const ul = normalizeToUlLi(box);
    if (!ul) return;

    // li 맨 앞에 handle 삽입
    qsa(ul, "li").forEach((li) => {
      if (li.querySelector(".drag-handle")) return;

      const handle = document.createElement("div");
      handle.className = "drag-handle";
      handle.textContent = "↕️";
      handle.setAttribute("aria-label", "드래그로 순서 변경");
      handle.setAttribute("role", "button");
      handle.setAttribute("tabindex", "0");

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
    let isDragging = false;

    function makePlaceholder(heightPx) {
      const ph = document.createElement("li");
      ph.className = "placeholder";
      ph.style.height = heightPx + "px";
      return ph;
    }

    function clearDanglingPlaceholder() {
      qsa(ul, "li.placeholder").forEach((el) => el.remove());
    }

    function getLiUnderPointer(clientY) {
      const lis = qsa(ul, "li").filter((li) => li !== draggingLi && li !== placeholder);
      for (const li of lis) {
        const rect = li.getBoundingClientRect();
        const mid = rect.top + rect.height / 2;
        if (clientY < mid) return li;
      }
      return null;
    }

    function onPointerMove(e) {
      if (!draggingLi || !placeholder) return;
      if (e.cancelable) e.preventDefault();

      const targetLi = getLiUnderPointer(e.clientY);
      if (targetLi) {
        ul.insertBefore(placeholder, targetLi);
      } else {
        ul.appendChild(placeholder);
      }
    }

    function endDrag() {
      if (!draggingLi || !placeholder) {
        isDragging = false;
        draggingLi = null;
        if (placeholder) {
          placeholder.remove();
          placeholder = null;
        }
        return;
      }

      draggingLi.classList.remove("dragging");
      ul.insertBefore(draggingLi, placeholder);
      placeholder.remove();

      draggingLi = null;
      placeholder = null;
      isDragging = false;

      hidden.value = getCheckedIdsInDomOrder(box).join(",");
    }

    function cancelDrag() {
      if (draggingLi) {
        draggingLi.classList.remove("dragging");
      }
      if (placeholder) {
        placeholder.remove();
      }
      draggingLi = null;
      placeholder = null;
      isDragging = false;

      hidden.value = getCheckedIdsInDomOrder(box).join(",");
    }

    function isCheckedLi(li) {
      const cb = li ? li.querySelector('input[type="checkbox"]') : null;
      return !!(cb && cb.checked);
    }

    function startDragFromEvent(e, li, captureEl) {
      if (!li) return;
      if (isDragging) return;

      // 체크된 항목만 드래그 가능
      if (!isCheckedLi(li)) return;

      clearDanglingPlaceholder();

      draggingLi = li;
      isDragging = true;
      draggingLi.classList.add("dragging");

      const rect = li.getBoundingClientRect();
      placeholder = makePlaceholder(rect.height);
      ul.insertBefore(placeholder, draggingLi.nextSibling);

      if (e.cancelable) e.preventDefault();
      e.stopPropagation();

      if (e.pointerId != null && captureEl && captureEl.setPointerCapture) {
        try {
          captureEl.setPointerCapture(e.pointerId);
        } catch (_) {}
      }

      const moveEvt = window.PointerEvent
        ? "pointermove"
        : e.touches
        ? "touchmove"
        : "mousemove";

      const upEvt = window.PointerEvent
        ? "pointerup"
        : e.touches
        ? "touchend"
        : "mouseup";

      const cancelEvt = window.PointerEvent
        ? "pointercancel"
        : e.touches
        ? "touchcancel"
        : null;

      function moveHandler(ev) {
        if (ev.touches && ev.touches[0]) {
          ev.clientY = ev.touches[0].clientY;
        }
        onPointerMove(ev);
      }

      function cleanup(useCancel) {
        document.removeEventListener(moveEvt, moveHandler);
        document.removeEventListener(upEvt, upHandler);
        if (cancelEvt) {
          document.removeEventListener(cancelEvt, cancelHandler);
        }

        if (useCancel) {
          cancelDrag();
        } else {
          endDrag();
        }
      }

      function upHandler() {
        cleanup(false);
      }

      function cancelHandler() {
        cleanup(true);
      }

      document.addEventListener(moveEvt, moveHandler, { passive: false });
      document.addEventListener(upEvt, upHandler, { passive: false });
      if (cancelEvt) {
        document.addEventListener(cancelEvt, cancelHandler, { passive: false });
      }
    }

    function bindDragStarters() {
      // 핸들에서만 드래그 시작
      qsa(ul, ".drag-handle").forEach((handle) => {
        handle.addEventListener("pointerdown", function (e) {
          startDragFromEvent(e, e.currentTarget.closest("li"), handle);
        });

        handle.addEventListener("mousedown", function (e) {
          if (window.PointerEvent) return;
          startDragFromEvent(e, e.currentTarget.closest("li"), handle);
        });

        handle.addEventListener(
          "touchstart",
          function (e) {
            if (window.PointerEvent) return;
            startDragFromEvent(e, e.currentTarget.closest("li"), handle);
          },
          { passive: false }
        );
      });
    }

    bindDragStarters();

    const form = box.closest("form");
    if (form) {
      form.addEventListener("submit", function () {
        clearDanglingPlaceholder();
        if (draggingLi) {
          cancelDrag();
        }
        hidden.value = getCheckedIdsInDomOrder(box).join(",");
      });
    }
  }

  setupSimpleBox("consultantsBox");
  setupSimpleBox("receiversBox");
  setupApproversPointerSort("approversBox", "id_approvers_order");

  // 상신 버튼 연타 방지 + 로딩 표시
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