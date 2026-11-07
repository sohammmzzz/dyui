// Apply the saved theme before first paint (no flash). An external file, not an
// inline script, so the app runs under a strict `script-src 'self'` CSP.
try {
  var t = localStorage.getItem("dyui:theme");
  if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t);
} catch (e) {}
