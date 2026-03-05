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

      // ✅ 체크된 항목만 핸들 활성/표시
      const handle = li ? li.querySelector(".drag-handle") : null;
      if (handle) {
        handle.style.visibility = cb.checked ? "visible" : "hidden";
        handle.style.pointerEvents = cb.checked ? "auto" : "none";
        handle.setAttribute("aria-disabled", cb.checked ? "false" : "true");
      }
    });
  }

  function getCheckedIdsInDomOrder(box) {
    // ✅ DOM 순서대로 체크된 value만
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
    box.addEventListener("change", () => syncCheckedClass(box));
  }

  // ✅ Django가 어떤 형태로 렌더하든, approversBox 내부를 <ul><li> 구조로 표준화
  function normalizeToUlLi(box) {
    // 이미 ul이 있으면 그대로 사용
    let ul = box.querySelector("ul");
    if (ul) return ul;

    // checkbox들을 기준으로 label 단위로 li를 만든다
    const checkboxes = qsa(box, 'input[type="checkbox"]');
    if (checkboxes.length === 0) return null;

    ul = document.createElement("ul");

    // label을 기준으로 묶기 (Django checkboxselectmultiple은 보통 label이 있음)
    checkboxes.forEach((cb) => {
      const label = cb.closest("label") || cb.parentElement;

      const li = document.createElement("li");
      // label이 box 바깥에 있을 수도 있으니, 안전하게 clone 대신 "이동"시킴
      // (이동해도 form submit에는 영향 없음)
      if (label) {
        li.appendChild(label);
      } else {
        // label을 못찾으면 cb 자체를 감싼다
        const fallback = document.createElement("label");
        fallback.appendChild(cb);
        li.appendChild(fallback);
      }
      ul.appendChild(li);
    });

    // box 내용을 ul로 교체
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

    // ✅ li 맨 앞에 handle을 넣는다 (label 밖!)
    qsa(ul, "li").forEach((li) => {
      if (li.querySelector(".drag-handle")) return;

      const handle = document.createElement("div");
      handle.className = "drag-handle";
      handle.textContent = "↕️";
      handle.setAttribute("aria-label", "드래그로 순서 변경");

      li.insertBefore(handle, li.firstChild);
    });

    // 초기 상태
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

      // ✅ 드래그 중 스크롤 방지(특히 모바일)
      if (e.cancelable) e.preventDefault();

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

    function isCheckedLi(li) {
      const cb = li ? li.querySelector('input[type="checkbox"]') : null;
      return !!(cb && cb.checked);
    }

    function startDragFromEvent(e, li, captureEl) {
      if (!li) return;

      // ✅ "체크된 항목만" 드래그 허용
      if (!isCheckedLi(li)) return;

      draggingLi = li;
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

      const moveEvt = window.PointerEvent ? "pointermove" : e.touches ? "touchmove" : "mousemove";
      const upEvt = window.PointerEvent ? "pointerup" : e.touches ? "touchend" : "mouseup";

      function moveHandler(ev) {
        if (ev.touches && ev.touches[0]) ev.clientY = ev.touches[0].clientY;
        onPointerMove(ev);
      }

      function upHandler() {
        document.removeEventListener(moveEvt, moveHandler);
        document.removeEventListener(upEvt, upHandler);
        endDrag();
      }

      document.addEventListener(moveEvt, moveHandler, { passive: false });
      document.addEventListener(upEvt, upHandler, { passive: false });
    }

    function bindDragStarters() {
      // ✅ 1) 핸들에서만 드래그 시작 (체크된 경우에만 핸들이 활성화됨)
      qsa(ul, ".drag-handle").forEach((handle) => {
        handle.addEventListener("pointerdown", function (e) {
          startDragFromEvent(e, e.target.closest("li"), handle);
        });

        // pointer 없는 환경 fallback
        handle.addEventListener("mousedown", function (e) {
          if (window.PointerEvent) return;
          startDragFromEvent(e, e.target.closest("li"), handle);
        });

        handle.addEventListener(
          "touchstart",
          function (e) {
            if (window.PointerEvent) return;
            startDragFromEvent(e, e.target.closest("li"), handle);
          },
          { passive: false }
        );
      });

      // ✅ 2) 카드(label)에서도 드래그 시작 가능 (단, 체크박스 클릭은 제외)
      qsa(ul, "li > label").forEach((label) => {
        function guardStart(e) {
          if (e.target && e.target.matches('input[type="checkbox"]')) return;
          startDragFromEvent(e, e.target.closest("li"), label);
        }

        label.addEventListener("pointerdown", function (e) {
          guardStart(e);
        });

        label.addEventListener("mousedown", function (e) {
          if (window.PointerEvent) return;
          guardStart(e);
        });

        label.addEventListener(
          "touchstart",
          function (e) {
            if (window.PointerEvent) return;
            guardStart(e);
          },
          { passive: false }
        );
      });
    }

    bindDragStarters();

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