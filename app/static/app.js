/* ShopNam.pro — tăng cường giao diện. Mọi chức năng vẫn chạy khi tắt JavaScript (form gửi bình thường). */
(function () {
  "use strict";
  var $$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };

  // Thông báo: nút đóng + tự ẩn thông báo thành công sau 6 giây
  $$(".alert").forEach(function (a) {
    var close = function () { a.classList.add("fade"); setTimeout(function () { a.remove(); }, 300); };
    var b = a.querySelector("button");
    if (b) b.addEventListener("click", close);
    if (a.classList.contains("alert-success")) setTimeout(close, 6000);
  });

  // Hộp xác nhận cho form nguy hiểm: <form data-confirm="...">
  $$("form[data-confirm]").forEach(function (f) {
    f.addEventListener("submit", function (e) { if (!confirm(f.dataset.confirm)) e.preventDefault(); });
  });

  // Ô số lượng có nút −/+ ; data-autosubmit: đổi xong tự gửi form (giỏ hàng)
  $$(".stepper").forEach(function (s) {
    var input = s.querySelector("input"), timer;
    $$("button[data-step]", s).forEach(function (b) {
      b.addEventListener("click", function () {
        var min = +input.min || 0, max = input.max ? +input.max : 99;
        var v = Math.min(max, Math.max(min, (+input.value || 0) + (+b.dataset.step)));
        if (String(v) === input.value) return;
        input.value = v;
        if (s.hasAttribute("data-autosubmit")) {
          clearTimeout(timer);
          timer = setTimeout(function () { input.form.requestSubmit ? input.form.requestSubmit() : input.form.submit(); }, 450);
        }
      });
    });
  });

  // Thư viện ảnh trang chi tiết: bấm ảnh nhỏ để đổi ảnh lớn, phím ← → để chuyển
  var main = document.getElementById("main-photo"), thumbs = $$(".gallery-thumbs button");
  function show(i) {
    if (!thumbs.length) return;
    i = (i + thumbs.length) % thumbs.length;
    main.src = thumbs[i].dataset.src;
    thumbs.forEach(function (x, j) { x.classList.toggle("active", j === i); });
  }
  thumbs.forEach(function (b, i) { b.addEventListener("click", function () { show(i); }); });
  if (main && thumbs.length > 1) {
    document.addEventListener("keydown", function (e) {
      if (/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) return;
      var cur = thumbs.findIndex(function (x) { return x.classList.contains("active"); });
      if (e.key === "ArrowRight") show(cur + 1);
      if (e.key === "ArrowLeft") show(cur - 1);
    });
  }

  // Lọc/sắp xếp: chọn xong tự gửi
  $$("select[data-autosubmit]").forEach(function (s) { s.addEventListener("change", function () { s.form.submit(); }); });

  // Phím "/" để nhảy vào ô tìm kiếm
  var search = document.querySelector(".search input");
  document.addEventListener("keydown", function (e) {
    if (e.key === "/" && search && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) {
      e.preventDefault(); search.focus(); search.select();
    }
  });
})();
