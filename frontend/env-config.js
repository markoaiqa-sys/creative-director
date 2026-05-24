// Runtime config for browser deployments (e.g. Vercel static hosting).
// Auto-detects backend URL from multiple sources.

(function () {
  let backendUrl = "";

  // Check if already configured
  if (window.__APP_CONFIG__ && window.__APP_CONFIG__.BACKEND_URL) {
    console.log("[Config] Already configured with BACKEND_URL:", window.__APP_CONFIG__.BACKEND_URL);
    return;
  }

  // 1. Check for Vercel env injection via meta tags (if build script adds them)
  const metaBackend = document.querySelector('meta[name="backend-url"]');
  if (metaBackend && metaBackend.getAttribute('content')) {
    backendUrl = metaBackend.getAttribute('content');
    console.log("[Config] Found backend URL in meta tag");
  }

  // 2. Check for environment variable passed by build system
  if (!backendUrl && typeof window.__BACKEND_URL__ !== 'undefined') {
    backendUrl = window.__BACKEND_URL__;
    console.log("[Config] Found __BACKEND_URL__ global");
  }

  // 3. Local development fallback
  if (!backendUrl && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')) {
    backendUrl = "http://127.0.0.1:8000";
    console.log("[Config] Using local backend URL");
  }

  // 4. If hosted on Render itself, backend is same origin (empty = relative URLs)
  if (!backendUrl && window.location.hostname.includes('onrender.com')) {
    backendUrl = "";
    console.log("[Config] Using same-origin backend (Render)");
  }

  // 5. Production backend URL for Vercel-hosted frontend
  if (!backendUrl) {
    backendUrl = "https://creative-director-x1js.onrender.com";
    console.log("[Config] Using production backend URL");
  }

  // Clean up trailing slashes
  backendUrl = backendUrl.trim().replace(/\/+$/, "");

  // Set global config
  window.__APP_CONFIG__ = {
    BACKEND_URL: backendUrl,
    ENV: window.location.hostname.includes('vercel') ? 'production' : 'development'
  };

  console.log("[Config] Initialized:", {
    BACKEND_URL: window.__APP_CONFIG__.BACKEND_URL,
    ENV: window.__APP_CONFIG__.ENV,
    HOSTNAME: window.location.hostname
  });
})();
