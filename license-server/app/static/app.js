/* Interações do app: dropzones de upload e filtro de tabelas.
   Sem dependências; re-inicializa após swaps do HTMX. */
(function () {
  function initDropzones(root) {
    root.querySelectorAll(".dropzone:not([data-dz-ready])").forEach(function (dz) {
      dz.setAttribute("data-dz-ready", "1");
      var input = dz.querySelector('input[type="file"]');
      var text = dz.querySelector(".dz-text");
      var hint = dz.querySelector(".dz-hint");
      var err = dz.parentElement.querySelector(".dz-error");
      var emptyText = text.textContent;

      function accepted(name) {
        var accept = (input.getAttribute("accept") || "").split(",")
          .map(function (s) { return s.trim().toLowerCase(); }).filter(Boolean);
        if (!accept.length) return true;
        return accept.some(function (ext) { return name.toLowerCase().endsWith(ext); });
      }

      function showFile(file) {
        dz.classList.add("filled");
        text.innerHTML = '<span class="dz-file"></span>';
        text.querySelector(".dz-file").textContent = file.name;
        hint.textContent = (file.size / 1048576).toFixed(1) + " MB — clique para trocar";
        if (err) err.style.display = "none";
      }

      function showError(msg) {
        dz.classList.remove("filled");
        text.textContent = emptyText;
        if (err) { err.textContent = msg; err.style.display = "block"; }
      }

      input.addEventListener("change", function () {
        if (input.files.length) showFile(input.files[0]);
      });

      ["dragenter", "dragover"].forEach(function (ev) {
        dz.addEventListener(ev, function (e) {
          e.preventDefault(); dz.classList.add("dragover");
        });
      });
      ["dragleave", "drop"].forEach(function (ev) {
        dz.addEventListener(ev, function (e) {
          e.preventDefault(); dz.classList.remove("dragover");
        });
      });
      dz.addEventListener("drop", function (e) {
        var files = e.dataTransfer.files;
        if (!files.length) return;
        if (!accepted(files[0].name)) {
          showError("Formato não aceito. Use: " + input.getAttribute("accept"));
          input.value = "";
          return;
        }
        var dt = new DataTransfer();
        dt.items.add(files[0]);
        input.files = dt.files;
        showFile(files[0]);
      });
    });
  }

  function initFilters(root) {
    root.querySelectorAll("input.table-filter:not([data-tf-ready])").forEach(function (inp) {
      inp.setAttribute("data-tf-ready", "1");
      inp.addEventListener("input", function () {
        var card = inp.closest(".card");
        var q = inp.value.trim().toLowerCase();
        card.querySelectorAll("tbody tr").forEach(function (tr) {
          tr.style.display = tr.textContent.toLowerCase().indexOf(q) === -1 ? "none" : "";
        });
      });
    });
  }

  function initAll(root) { initDropzones(root); initFilters(root); }

  document.addEventListener("DOMContentLoaded", function () { initAll(document); });
  document.body && initAll(document);
  document.addEventListener("htmx:afterSwap", function (e) { initAll(e.target.parentElement || document); });
})();
