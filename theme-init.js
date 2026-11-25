/* Se carga de forma bloqueante en <head>, antes de cualquier hoja de estilo: el atributo
   data-theme ya existe cuando el navegador pinta el primer cuadro, sin destello blanco. */
(function () {
  "use strict";
  var KEY = "ferrepro.theme";
  var root = document.documentElement;
  var media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

  function saved() {
    try {
      var value = localStorage.getItem(KEY);
      return value === "light" || value === "dark" ? value : null;
    } catch (e) {
      return null;
    }
  }
  function system() {
    return media && media.matches ? "dark" : "light";
  }
  function label(theme) {
    return theme === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro";
  }
  function apply(theme) {
    root.setAttribute("data-theme", theme);
    var buttons = document.querySelectorAll("[data-theme-toggle]");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].setAttribute("aria-label", label(theme));
      buttons[i].setAttribute("title", label(theme));
    }
  }

  apply(saved() || system());

  // Sin eleccion guardada, la pagina sigue al sistema en vivo
  if (media) {
    var follow = function () { if (!saved()) apply(system()); };
    if (media.addEventListener) media.addEventListener("change", follow);
    else if (media.addListener) media.addListener(follow);
  }

  window.FerreTheme = {
    get: function () { return root.getAttribute("data-theme"); },
    toggle: function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      try { localStorage.setItem(KEY, next); } catch (e) {}
      apply(next);
      return next;
    }
  };

  document.addEventListener("DOMContentLoaded", function () {
    apply(root.getAttribute("data-theme"));
    document.addEventListener("click", function (event) {
      var target = event.target.closest ? event.target.closest("[data-theme-toggle]") : null;
      if (target) window.FerreTheme.toggle();
    });
  });
}());
