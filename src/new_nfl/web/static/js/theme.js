(function () {
  'use strict';

  var STORAGE_KEY = 'new-nfl-theme';
  var THEMES = ['dark', 'light'];

  function currentTheme() {
    var attr = document.documentElement.getAttribute('data-theme');
    return THEMES.indexOf(attr) >= 0 ? attr : 'dark';
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch (e) { /* ignore */ }
  }

  function toggle() {
    applyTheme(currentTheme() === 'dark' ? 'light' : 'dark');
  }

  document.addEventListener('click', function (event) {
    var target = event.target;
    while (target && target !== document.body) {
      if (target.hasAttribute && target.hasAttribute('data-theme-toggle')) {
        toggle();
        event.preventDefault();
        return;
      }
      target = target.parentNode;
    }
  });
})();
