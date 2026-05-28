let API_BASE_URL = (
  window.__APP_CONFIG__ &&
  typeof window.__APP_CONFIG__.BACKEND_URL === "string" &&
  window.__APP_CONFIG__.BACKEND_URL.trim()
)
  ? window.__APP_CONFIG__.BACKEND_URL.trim().replace(/\/+$/, "")
  : "";

// --- Auth & DB Segregation Interceptor ---
const originalFetch = window.fetch;
window.fetch = async function () {
  let [resource, config] = arguments;
  if (!config) config = {};
  if (!config.headers) config.headers = {};
  
  const authEmail = localStorage.getItem("auth_email");
  const isGuest = localStorage.getItem("is_guest");
  
  if (config.headers instanceof Headers) {
    if (authEmail) config.headers.append("X-Client-Email", authEmail);
    if (isGuest) config.headers.append("X-Is-Guest", isGuest);
  } else {
    if (authEmail) config.headers["X-Client-Email"] = authEmail;
    if (isGuest) config.headers["X-Is-Guest"] = isGuest;
  }
  
  return originalFetch(resource, config);
};

// --- Auth Initialization ---
document.addEventListener("DOMContentLoaded", () => {
  const authEmail = localStorage.getItem("auth_email");
  const isGuest = localStorage.getItem("is_guest");
  const overlay = document.getElementById("login-overlay");
  
  if (!authEmail && isGuest !== "true") {
    overlay.style.display = "flex";
  } else {
    overlay.style.display = "none";
  }

  const loginForm = document.getElementById("login-form");
  if (loginForm) {
    loginForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const email = document.getElementById("login-email").value;
      if (email) {
        localStorage.setItem("auth_email", email);
        localStorage.setItem("is_guest", "false");
        overlay.style.display = "none";
        window.location.reload(); // Reload to fetch client-specific data
      }
    });
  }

  const guestBtn = document.getElementById("login-guest-btn");
  if (guestBtn) {
    guestBtn.addEventListener("click", () => {
      localStorage.setItem("auth_email", "guest@marko.ai");
      localStorage.setItem("is_guest", "true");
      overlay.style.display = "none";
      window.location.reload(); // Reload to clear previous state
    });
  }
});

const byId = (id) => document.getElementById(id);
const chatBody = byId("chat-body");
const chatInput = byId("chat-input");
const chatSend = byId("chat-send");
const supervisorNav = byId("supervisor-nav");
const supervisorPanel = byId("supervisor-panel");
const dashboardNav = byId("dashboard-nav");
const heroCard = byId("hero-card");
const loadingPanel = byId("loading-panel");
const resultsPanel = byId("results-panel");
const liveStatus = byId("live-status");
const resultsTitle = byId("results-title");
const heroGenerateButton = byId("hero-generate");
const hooksOutput = byId("hooks-output");
const anglesOutput = byId("angles-output");
const copyOutput = byId("copy-output");
const conceptsOutput = byId("concepts-output");
const reelsOutput = byId("reels-output");
const finalsOutput = byId("finals-output");
const previewsOutput = byId("previews-output");
const exportsOutput = byId("exports-output");
const sampleInput = byId("f-samples");
const sampleHint = byId("f-samples-hint");
const logoInput = byId("f-logo");
const referenceSimilarityInput = byId("f-ref-sim");
const referenceSimilarityValue = byId("f-ref-sim-value");
const referenceSimilarityWrap = byId("f-ref-sim-wrap");
const btnChatHistory = byId("btn-chat-history");
const btnChatNew = byId("btn-chat-new");
const btnSidebarChat = byId("btn-sidebar-chat");
const chatHistoryPanel = byId("chat-history-panel");
const chatSessionsList = byId("chat-sessions-list");
const chatPanel = document.querySelector(".chat-panel");
const tabChatbotBtn = byId("tab-chatbot-btn");
const tabSuggestionsBtn = byId("tab-suggestions-btn");
const chatbotContentArea = byId("chatbot-content-area");
const suggestionsContentArea = byId("suggestions-content-area");
const btnChatClose = byId("btn-chat-close");
const historyPanel = byId("history-panel");
const navExecutionHistory = byId("nav-execution-history");
const historyOutput = byId("history-output");
const btnKnowledgeBase = byId("btn-knowledge-base");
const requiredFieldIds = ["f-brand", "f-desc", "f-audience", "f-benefits"];

// Redesigned Chat Composer elements
const chatModeSelect = byId("chat-mode-select");
const chatModelSelect = byId("chat-model-select");
const chatAttachBtn = byId("chat-attach-btn");
const chatAttachInput = byId("chat-attach-input");
const chatAttachmentsPreview = byId("chat-attachments-preview");
let chatAttachedFiles = [];
let chatbotSessionAttachments = [];

function updateChatAttachmentsPreview() {
  if (!chatAttachmentsPreview) return;
  chatAttachmentsPreview.innerHTML = "";
  chatAttachedFiles.forEach((file, index) => {
    const pill = document.createElement("div");
    pill.className = "chat-attachment-pill";
    pill.innerHTML = `
      <span>📎 ${esc(file.name)}</span>
      <button type="button" onclick="removeChatAttachment(${index})">✕</button>
    `;
    chatAttachmentsPreview.appendChild(pill);
  });
}
window.removeChatAttachment = function(index) {
  chatAttachedFiles.splice(index, 1);
  updateChatAttachmentsPreview();
};


const MAX_SAMPLE_IMAGES = 3;
const MAX_SAMPLE_IMAGE_SIZE_BYTES = 5 * 1024 * 1024;

const countTargets = {
  finals: [byId("finals-count"), byId("finals-count-large")],
  previews: [byId("previews-count"), byId("previews-count-large")],
  hooks: [byId("hooks-count"), byId("hooks-count-large")],
  angles: [byId("angles-count"), byId("angles-count-large")],
  copy: [byId("copy-count"), byId("copy-count-large")],
  concepts: [byId("concepts-count"), byId("concepts-count-large")],
  reels: [byId("reels-count"), byId("reels-count-large")],
  exports: [byId("exports-count"), byId("exports-count-large")]
};

let chatContext = {};
let chatSessionId = null; // Default to new chat, history must be manually selected
let selectedKnowledgeImages = [];
let selectedSampleFiles = [];
let currentSuggestions = [];
let currentPayload = null;
let instagramIngestionPollHandle = null;
let instagramIngestionJobId = null;
let instagramIngestionJobState = null;
let instagramIngestionResultState = null;
let instagramAutoPipelineRunning = false;

const instagramIngestionControls = {
  reelUrls: () => byId("instagram-ingest-reel-urls"),
  brief: () => byId("instagram-brief"),
  singleMode: () => byId("instagram-single-reel-mode"),
  singleFields: () => byId("instagram-single-reel-fields"),
  singleTranscript: () => byId("instagram-single-transcript"),
  singleCaption: () => byId("instagram-single-caption"),
  singleHook: () => byId("instagram-single-hook"),
  singleViews: () => byId("instagram-single-views"),
  singleLikes: () => byId("instagram-single-likes"),
  singleComments: () => byId("instagram-single-comments"),
  singleShares: () => byId("instagram-single-shares"),
  usernames: () => byId("instagram-ingest-usernames"),
  competitorReels: () => byId("instagram-ingest-competitor-reels"),
  trendingReels: () => byId("instagram-ingest-trending-reels"),
  niche: () => byId("instagram-ingest-niche"),
  audience: () => byId("instagram-ingest-audience"),
  jobName: () => byId("instagram-ingest-job-name"),
  maxReels: () => byId("instagram-ingest-max-reels"),
  cacheTtl: () => byId("instagram-ingest-cache-ttl"),
  rateLimit: () => byId("instagram-ingest-rate-limit"),
  includeComments: () => byId("instagram-ingest-include-comments"),
  includeMetrics: () => byId("instagram-ingest-include-metrics"),
  forceRefresh: () => byId("instagram-ingest-force-refresh"),
  submit: () => byId("instagram-ingest-submit"),
  reset: () => byId("instagram-ingest-reset"),
  state: () => byId("instagram-ingest-state"),
  jobId: () => byId("instagram-ingest-job-id"),
  progress: () => byId("instagram-ingest-progress-fill"),
  message: () => byId("instagram-ingest-message"),
  result: () => byId("instagram-ingest-result"),
  secondarySources: () => byId("instagram-secondary-sources"),
  addCompetitors: () => byId("instagram-add-competitors"),
  pipelineStrip: () => byId("instagram-pipeline-strip"),
  runAnalyze: () => byId("instagram-run-analyze"),
  runTrends: () => byId("instagram-run-trends"),
  runScript: () => byId("instagram-run-script"),
  runDirect: () => byId("instagram-run-direct"),
  runScore: () => byId("instagram-run-score"),
};

function defaultSampleHint() {
  return `Optional. Up to ${MAX_SAMPLE_IMAGES} images, max 5MB each, used as visual references for Vertex AI.`;
}

function totalSelectedReferences() {
  return selectedKnowledgeImages.length + selectedSampleFiles.length;
}

function refreshSampleHint(message, bad = false) {
  if (message) {
    setSampleHint(message, bad);
    updateReferenceSimilarityVisibility();
    return;
  }
  const total = totalSelectedReferences();
  if (!total) {
    setSampleHint(defaultSampleHint());
    updateReferenceSimilarityVisibility();
    return;
  }
  setSampleHint(`Using ${total} reference image(s).`);
  updateReferenceSimilarityVisibility();
}

function updateReferenceSimilarityVisibility() {
  if (!referenceSimilarityWrap) return;
  const shouldShow = totalSelectedReferences() > 0;
  referenceSimilarityWrap.classList.toggle("hidden", !shouldShow);
}

function sampleFileKey(file) {
  return `${file.name}::${file.size}::${file.lastModified}`;
}

function useKnowledgeImage(url) {
  if (!url) return;
  console.log("useKnowledgeImage called", { url });
  if (selectedKnowledgeImages.includes(url)) {
    setSampleHint("Image already added to references.");
    return;
  }
  if (totalSelectedReferences() >= MAX_SAMPLE_IMAGES) {
    setSampleHint(`Maximum ${MAX_SAMPLE_IMAGES} reference images allowed.`, true);
    return;
  }
  selectedKnowledgeImages.push(url);
  updateSamplesList();
  refreshSampleHint();
  // Refresh KB grid if modal is open to update button states
  const kbGrid = document.getElementById("kb-grid");
  if (kbGrid && kbGrid.innerHTML) {
    fetchKnowledgeBaseImages();
  }
}

function removeKnowledgeImage(url) {
  console.log("removeKnowledgeImage called", { url });
  selectedKnowledgeImages = selectedKnowledgeImages.filter((u) => u !== url);
  updateSamplesList();
  refreshSampleHint();
  // Refresh KB grid if modal is open to update button states
  const kbGrid = document.getElementById("kb-grid");
  if (kbGrid && kbGrid.innerHTML) {
    fetchKnowledgeBaseImages();
  }
}

function removeUploadedSample(index) {
  console.log("removeUploadedSample called", { index });
  if (index < 0 || index >= selectedSampleFiles.length) return;
  selectedSampleFiles.splice(index, 1);
  updateSamplesList();
  refreshSampleHint();

  // Refresh KB grid if modal is open to update button states
  const kbGrid = document.getElementById("kb-grid");
  if (kbGrid && kbGrid.innerHTML) {
    fetchKnowledgeBaseImages();
  }
}

function updateSamplesList() {
  const container = byId("f-samples-list");
  if (!container) return;
  if (!selectedKnowledgeImages.length && !selectedSampleFiles.length) {
    container.innerHTML = "";
    return;
  }
  container.innerHTML = "";

  const createThumb = ({ src, label, onRemove }) => {
    const wrapper = document.createElement("div");
    wrapper.className = "sample-thumb";
    wrapper.style.display = "inline-block";
    wrapper.style.marginRight = "8px";
    wrapper.style.marginBottom = "8px";
    wrapper.style.textAlign = "center";

    const img = document.createElement("img");
    img.src = src;
    img.style.width = "64px";
    img.style.height = "64px";
    img.style.objectFit = "cover";
    img.style.borderRadius = "6px";
    img.style.border = "1px solid #e5e5e5";
    wrapper.appendChild(img);

    const kind = document.createElement("div");
    kind.style.fontSize = "0.75em";
    kind.style.color = "#6d7788";
    kind.style.marginTop = "4px";
    kind.textContent = label;
    wrapper.appendChild(kind);

    const removeLine = document.createElement("div");
    removeLine.style.marginTop = "2px";
    removeLine.style.fontSize = "0.8em";

    const removeBtn = document.createElement("button");
    removeBtn.className = "link-btn";
    removeBtn.type = "button";
    removeBtn.textContent = "Remove";
    removeBtn.addEventListener("click", onRemove);

    removeLine.appendChild(removeBtn);
    wrapper.appendChild(removeLine);
    container.appendChild(wrapper);
  };

  selectedSampleFiles.forEach((file, index) => {
    const objectUrl = URL.createObjectURL(file);
    createThumb({
      src: objectUrl,
      label: "Uploaded",
      onRemove: () => removeUploadedSample(index),
    });
  });

  selectedKnowledgeImages.forEach((url) => {
    createThumb({
      src: url,
      label: "Knowledge Base",
      onRemove: () => removeKnowledgeImage(url),
    });
  });
}

function esc(v) {
  return String(v)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function setStatus(msg, bad = false) {
  liveStatus.textContent = msg;
  liveStatus.style.color = bad ? "#a9342a" : "#4f5f72";
}

function clearFieldErrors() {
  requiredFieldIds.forEach((id) => {
    const field = byId(id);
    if (field) field.classList.remove("field-error");
  });
}

function markFieldError(id) {
  const field = byId(id);
  if (field) field.classList.add("field-error");
}

function validatePayload(payload) {
  clearFieldErrors();
  const errors = [];
  if (!payload.brand_name) {
    errors.push("Brand Name is required.");
    markFieldError("f-brand");
  }
  if (!payload.product_description) {
    errors.push("Product Description is required.");
    markFieldError("f-desc");
  }
  if (!payload.target_audience) {
    errors.push("Target Audience is required.");
    markFieldError("f-audience");
  }
  if (!payload.key_benefits.length) {
    errors.push("Add at least one Key Benefit.");
    markFieldError("f-benefits");
  }
  return errors;
}

async function parseErrorResponse(response) {
  try {
    const data = await response.json();
    if (typeof data.detail === "string") return data.detail;
    return JSON.stringify(data);
  } catch {
    try {
      return await response.text();
    } catch {
      return `Request failed with status ${response.status}`;
    }
  }
}

async function getBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => resolve(reader.result);
    reader.onerror = (error) => reject(error);
  });
}

function setSampleHint(message, bad = false) {
  if (!sampleHint) return;
  sampleHint.textContent = message;
  sampleHint.style.color = bad ? "#a9342a" : "#4f5f72";
}

function toPublicAssetUrl(rawPath) {
  if (!rawPath) return "";
  if (/^data:|^https?:\/\//i.test(rawPath)) return rawPath;

  const normalized = String(rawPath).replaceAll("\\", "/");
  const lower = normalized.toLowerCase();
  let relative = normalized;
  const outputMarker = "/output/";
  const outputIndex = lower.lastIndexOf(outputMarker);

  if (outputIndex >= 0) {
    relative = normalized.slice(outputIndex + outputMarker.length);
  } else if (lower.startsWith("output/")) {
    relative = normalized.slice("output/".length);
  } else {
    const parts = normalized.split("/");
    const outputPartIndex = parts.map((part) => part.toLowerCase()).lastIndexOf("output");
    if (outputPartIndex >= 0) {
      relative = parts.slice(outputPartIndex + 1).join("/");
    }
  }

  return `${API_BASE_URL}/output/${relative.replace(/^\/+/, "")}`;
}

function showSupervisor() {
  if (supervisorPanel) supervisorPanel.classList.remove("hidden");
  if (heroCard) heroCard.classList.add("hidden");
  if (loadingPanel) loadingPanel.classList.add("hidden");
  if (resultsPanel) resultsPanel.classList.add("hidden");
  if (historyPanel) historyPanel.classList.add("hidden");

  if (supervisorNav) supervisorNav.classList.add("active");
  if (dashboardNav) dashboardNav.classList.remove("active");
  document.querySelectorAll(".specialist").forEach((n) => n.classList.remove("active"));
  if (navExecutionHistory) navExecutionHistory.classList.remove("active");
}

function showDashboard() {
  if (supervisorPanel) supervisorPanel.classList.add("hidden");
  if (supervisorNav) supervisorNav.classList.remove("active");
  if (heroCard) heroCard.classList.remove("hidden");
  if (loadingPanel) loadingPanel.classList.add("hidden");
  // Only hide results if we haven't generated anything yet
  if (resultsPanel) {
    if (!chatContext.campaign) {
      resultsPanel.classList.add("hidden");
    } else {
      resultsPanel.classList.remove("hidden");
    }
  }
  if (historyPanel) historyPanel.classList.add("hidden");
  if (dashboardNav) dashboardNav.classList.add("active");
  document.querySelectorAll(".specialist").forEach((n) => n.classList.remove("active"));
  if (navExecutionHistory) navExecutionHistory.classList.remove("active");
}

function showLoading() {
  if (supervisorPanel) supervisorPanel.classList.add("hidden");
  if (heroCard) heroCard.classList.add("hidden");
  if (loadingPanel) loadingPanel.classList.remove("hidden");
  if (resultsPanel) resultsPanel.classList.add("hidden");
  if (historyPanel) historyPanel.classList.add("hidden");
}

function showResults() {
  if (supervisorPanel) supervisorPanel.classList.add("hidden");
  if (heroCard) heroCard.classList.add("hidden");
  if (loadingPanel) loadingPanel.classList.add("hidden");
  if (resultsPanel) resultsPanel.classList.remove("hidden");
  if (historyPanel) historyPanel.classList.add("hidden");
}

function showHistory() {
  if (supervisorPanel) supervisorPanel.classList.add("hidden");
  if (supervisorNav) supervisorNav.classList.remove("active");
  if (heroCard) heroCard.classList.add("hidden");
  if (loadingPanel) loadingPanel.classList.add("hidden");
  if (resultsPanel) resultsPanel.classList.add("hidden");
  if (historyPanel) historyPanel.classList.remove("hidden");

  if (dashboardNav) dashboardNav.classList.remove("active");
  document.querySelectorAll(".specialist").forEach((n) => n.classList.remove("active"));
  if (navExecutionHistory) navExecutionHistory.classList.add("active");
}

function setCount(key, value) {
  (countTargets[key] || []).forEach((n) => {
    if (n) n.textContent = String(value);
  });
}

function empty(target, msg) {
  if (target) {
    target.innerHTML = `<div class="card"><p>${esc(msg)}</p></div>`;
  }
}

function resetOutputs() {
  empty(finalsOutput, "Rendered ad creatives will appear here after generation.");
  empty(previewsOutput, "Platform previews will appear here after generation.");
  empty(hooksOutput, "Hooks will appear here after generation.");
  empty(anglesOutput, "Angles will appear here after generation.");
  empty(copyOutput, "Ad copy will appear here after generation.");
  empty(conceptsOutput, "Generated concepts will appear here after generation.");
  empty(reelsOutput, "Instagram reels scripts and direction will appear here.");
  empty(exportsOutput, "Export rows will appear here after generation.");
  Object.keys(countTargets).forEach((key) => setCount(key, 0));
}

function activateTab(tab) {
  if (supervisorPanel) supervisorPanel.classList.add("hidden");
  if (supervisorNav) supervisorNav.classList.remove("active");
  document.querySelectorAll(".tab").forEach((n) => n.classList.toggle("active", n.dataset.tab === tab));
  ["finals", "previews", "hooks", "angles", "copy", "concepts", "reels", "exports"].forEach((name) => {
    byId(`tab-${name}`).classList.toggle("hidden", tab !== name);
  });
  document.querySelectorAll(".specialist").forEach((n) => n.classList.toggle("active", n.dataset.agentTab === tab));
  dashboardNav.classList.remove("active");
  resultsTitle.textContent = "Campaign Output";
  chatContext.active_specialist = tab;
}

function toggleCampaign(id) {
  const contentElem = document.getElementById(id);
  if (contentElem) {
    contentElem.classList.toggle("expanded");
    const headerElem = contentElem.previousElementSibling;
    const icon = headerElem?.querySelector(".toggle-icon");
    if (icon) {
      icon.style.transform = contentElem.classList.contains("expanded") ? "rotate(180deg)" : "rotate(0deg)";
    }
  }
}

function openImageModal(imageUrl, title) {
  const modal = document.getElementById("imageModal");
  const modalImage = document.getElementById("modalImage");
  const modalTitle = document.getElementById("modalTitle");
  
  if (modal && modalImage) {
    modalImage.src = imageUrl;
    modalTitle.textContent = title || "Creative Preview";
    modal.classList.remove("hidden");
  }
}

function closeImageModal() {
  const modal = document.getElementById("imageModal");
  if (modal) {
    modal.classList.add("hidden");
  }
}

let activeKbTab = "upload";

function switchKbTab(tabName) {
  activeKbTab = tabName;
  document.querySelectorAll(".kb-tabs .tab-btn").forEach(btn => {
    if (btn.dataset.kbTab === tabName) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });
  const hintText = document.getElementById("kb-hint-text");
  if (hintText) {
    if (tabName === "generation") {
      hintText.textContent = "View your previously generated ad campaigns.";
    } else if (tabName === "asset") {
      hintText.textContent = "Company logo and assets used in campaigns.";
    } else {
      hintText.textContent = "Select one or more uploaded images to use as sample context.";
    }
  }
  const uploadBtn = document.getElementById("kb-upload-btn");
  if (uploadBtn) {
    uploadBtn.style.display = (tabName === "upload") ? "inline-flex" : "none";
  }
  const grid = document.getElementById("kb-grid");
  if (grid) grid.innerHTML = `<div style="padding:12px;color:var(--muted,#666);">Loading...</div>`;
  fetchKnowledgeBaseImages();
}

function openKbModal(tabName = "upload") {
  const modal = document.getElementById("kbModal");
  if (modal) {
    modal.classList.remove("hidden");
  }
  // Check if event object was passed instead of string (default UI click)
  if (typeof tabName !== 'string') {
    tabName = "generation";
  }
  switchKbTab(tabName);
}

function closeKbModal() {
  const modal = document.getElementById("kbModal");
  if (modal) modal.classList.add("hidden");
}

async function fetchKnowledgeBaseImages() {
  try {
    const endpoint = (API_BASE_URL ? API_BASE_URL.replace(/\/+$/,'') : '') + '/knowledge-base/images';
    const res = await fetch(endpoint);
    if (!res.ok) throw new Error(`Fetch failed: ${res.status}`);
    const data = await res.json();
    let items = data?.items || [];
    
    items = items.filter(item => {
      let tags = item.tags;
      if (!Array.isArray(tags)) {
        if (typeof tags === 'string') tags = [tags];
        else tags = [];
      }
      if (activeKbTab === "generation") return tags.includes("generation");
      if (activeKbTab === "asset") return tags.includes("asset");
      return tags.includes("upload") || (!tags.includes("generation") && !tags.includes("asset"));
    });
    
    renderKbGrid(items);
  } catch (e) {
    const grid = document.getElementById("kb-grid");
    if (grid) grid.innerHTML = `<div class="card"><p>Error loading images.</p></div>`;
    console.error("KB fetch error", e);
  }
}

async function deleteKbImage(imageId) {
  if (!confirm("Are you sure you want to remove this image from the Knowledge Base?")) return;
  try {
    const endpoint = (API_BASE_URL ? API_BASE_URL.replace(/\/+$/,'') : '') + `/knowledge-base/images/${encodeURIComponent(imageId)}`;
    const res = await fetch(endpoint, { method: "DELETE" });
    if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
    fetchKnowledgeBaseImages(); // refresh
  } catch (e) {
    alert("Failed to delete image.");
    console.error(e);
  }
}

function renderKbGrid(items) {
  const grid = document.getElementById("kb-grid");
  if (!grid) return;
  if (!items || !items.length) {
    grid.innerHTML = `<div class="card"><p>No knowledge base images found.</p></div>`;
    return;
  }

  grid.innerHTML = items.map((it) => {
    const url = toPublicAssetUrl(it.web_path || it.webPath || it.path || "");
    const title = esc(it.title || it.filename || "Untitled");
    const escUrl = esc(url);
    const isSelected = selectedKnowledgeImages.includes(url);
    const atLimit = totalSelectedReferences() >= MAX_SAMPLE_IMAGES;
    const useButtonHtml = isSelected
      ? `<button class="link-btn" disabled style="opacity:0.5;cursor:not-allowed;">Already in use</button>`
      : atLimit
        ? `<button class="link-btn" disabled style="opacity:0.5;cursor:not-allowed;">Limit reached</button>`
        : `<button class="link-btn" onclick="useKnowledgeImage('${escUrl}')">Use in generation</button>`;
    return `
      <div class="card" style="text-align:center;padding:8px;position:relative;">
        <button class="icon-btn" onclick="deleteKbImage('${esc(it.id)}')" style="position:absolute;top:4px;right:4px;width:24px;height:24px;line-height:24px;padding:0;background:rgba(0,0,0,0.5);color:white;border-radius:50%;font-size:12px;" aria-label="Delete Image">✕</button>
        <div style="height:120px;overflow:hidden;display:flex;align-items:center;justify-content:center;">
          <img src="${escUrl}" alt="${title}" style="max-width:100%;max-height:120px;object-fit:cover;border-radius:6px;" onclick="openImageModal('${escUrl}','${title}')" />
        </div>
        <div style="margin-top:8px;font-weight:600;">${title}</div>
        <div style="margin-top:8px;display:flex;gap:6px;justify-content:center;">
          <button class="link-btn" onclick="openImageModal('${escUrl}','${title}')">View</button>
          ${useButtonHtml}
        </div>
      </div>
    `;
  }).join("");
}

function list(target, items, render) {
  if (!items || !items.length) {
    empty(target, "No items.");
    return;
  }
  target.innerHTML = items.map((item, index) => render(item, index)).join("");
}

function clampReelScore(value) {
  const number = Number(value);
  if (Number.isNaN(number)) return 0;
  return Math.max(0, Math.min(100, number));
}

function findInsightByCategory(items, category) {
  return (items || []).find((item) => String(item.category || "").toLowerCase() === category) || null;
}

function renderCurveBars(values, tone) {
  const palette = tone === "replay" ? ["72%", "84%", "66%", "54%", "78%", "48%"] : ["100%", "88%", "72%", "64%", "52%", "38%"];
  return `
    <div class="reels-curve">
      ${(values || []).map((value, index) => `
        <div class="reels-curve-col">
          <span class="reels-curve-bar ${tone === "replay" ? "is-replay" : ""}" style="height:${Math.max(16, clampReelScore(value))}%"></span>
          <small>${esc(palette[index] || `${index + 1}`)}</small>
        </div>
      `).join("")}
    </div>
  `;
}

function renderReelsAnalysis(analysis) {
  if (!reelsOutput) return;
  if (!analysis) {
    reelsOutput.innerHTML = `
      <div class="reels-empty-state">
        <h3>No reel intelligence yet</h3>
        <p>Paste a reel URL, describe what you want to create, and the system will ingest, analyze, detect trends, and generate a directed script automatically.</p>
      </div>
    `;
    setCount("reels", 0);
    return;
  }

  if (resultsTitle) resultsTitle.textContent = analysis.title || "Instagram Viral Reel Intelligence";
  if (liveStatus) liveStatus.textContent = analysis.summary || "Viral reel intelligence ready.";

  const analysisItems = analysis.analysis || [];
  const score = analysis.scores || {};
  const timeline = analysis.second_by_second_timeline || analysis.full_script || analysis.script?.scene_by_scene_direction || [];
  const script = analysis.script || {};
  const hookInsight = findInsightByCategory(analysisItems, "opening_line");
  const visualInsight = findInsightByCategory(analysisItems, "visual_hook");
  const emotionalInsight = findInsightByCategory(analysisItems, "emotional_trigger");
  const captionInsight = findInsightByCategory(analysisItems, "caption_pattern");
  const ctaInsight = findInsightByCategory(analysisItems, "cta_style");
  const topCompetitor = (analysis.competitor_winning_reels || [])[0];
  const topTrend = (analysis.trend_objects || [])[0];

  const scoreCards = [
    ["Curiosity", score.curiosity_gap],
    ["Emotional Trigger", score.emotional_impact],
    ["Replayability", analysis.replay_spike_curve?.[2] ?? score.shareability],
    ["Shareability", score.shareability],
    ["Watch Retention", score.retention],
    ["Comment Bait", score.cta_effectiveness],
    ["Save Potential", score.virality],
  ];

  const warningBanner = analysis.warning_message
    ? `
      <div class="reels-warning-banner">
        <strong>${esc(analysis.confidence_label || "Low")} confidence analysis</strong>
        <p>${esc(analysis.warning_message)}</p>
      </div>
    `
    : "";

  const hookSection = `
    <section class="reels-dashboard-section">
      <div class="reels-section-head">
        <div>
          <p class="panel-kicker">Section A</p>
          <h3>Viral Hook Analysis</h3>
        </div>
        <div class="reels-confidence-chip">Data quality ${esc(clampReelScore(analysis.data_quality_score))}/100</div>
      </div>
      <div class="reels-hook-grid">
        <div class="reels-hook-hero">
          <div class="reels-hook-type">${esc(hookInsight?.insight || analysis.hook_alternatives?.[0] || "No opening hook captured yet")}</div>
          <div class="reels-hook-score">
            <span>Hook Strength</span>
            <strong>${esc(clampReelScore(analysis.hook_strength_score))}/100</strong>
          </div>
          <p>${esc(hookInsight?.why_it_works || "The opening line should create an immediate information gap or a sharp promise.")}</p>
        </div>
        <div class="reels-hook-facts">
          <div class="reels-signal-card"><span>Visual hook</span><strong>${esc(visualInsight?.insight || "No visual hook extracted")}</strong></div>
          <div class="reels-signal-card"><span>Emotional trigger</span><strong>${esc(emotionalInsight?.insight || "Not enough evidence yet")}</strong></div>
          <div class="reels-signal-card"><span>Curiosity gap</span><strong>${esc(`${clampReelScore(score.curiosity_gap)}/100`)}</strong></div>
          <div class="reels-signal-card"><span>Retention prediction</span><strong>${esc(`${clampReelScore(analysis.audience_retention_prediction || analysis.retention_score)}/100`)}</strong></div>
        </div>
      </div>
    </section>
  `;

  const timelineSection = `
    <section class="reels-dashboard-section">
      <div class="reels-section-head">
        <div>
          <p class="panel-kicker">Section B</p>
          <h3>Visual Hook Timeline</h3>
        </div>
      </div>
      <div class="reels-flow-track">
        ${timeline.length ? timeline.map((beat) => `
          <article class="reels-flow-card${beat.interruption_pattern ? " is-critical" : ""}">
            <span>${esc(beat.second_range || "-")}</span>
            <strong>${esc(beat.scene || "-")}</strong>
            <p>${esc(beat.camera_direction || "-")}</p>
            <small>${esc((beat.text_overlay || [])[0] || beat.retention_note || "-")}</small>
          </article>
        `).join("") : `<div class="reels-empty-inline">Timeline will appear after analysis.</div>`}
      </div>
    </section>
  `;

  const retentionSection = `
    <section class="reels-dashboard-section">
      <div class="reels-section-head">
        <div>
          <p class="panel-kicker">Section C</p>
          <h3>Retention Graph</h3>
        </div>
      </div>
      <div class="reels-graph-grid">
        <div class="reels-graph-card">
          <span>Predicted retention arc</span>
          ${renderCurveBars(analysis.retention_curve || [], "retention")}
        </div>
        <div class="reels-graph-card">
          <span>Replay and dopamine spikes</span>
          ${renderCurveBars(analysis.replay_spike_curve || [], "replay")}
        </div>
        <div class="reels-graph-meta">
          <div class="reels-signal-card"><span>Drop-off risk</span><strong>${esc(analysis.retention_critical_moments?.[0] || "Not enough signal yet")}</strong></div>
          <div class="reels-signal-card"><span>Replay spike</span><strong>${esc(analysis.dopamine_spikes?.[0] || "Awaiting stronger signal")}</strong></div>
        </div>
      </div>
    </section>
  `;

  const competitorSection = `
    <section class="reels-dashboard-section">
      <div class="reels-section-head">
        <div>
          <p class="panel-kicker">Section D</p>
          <h3>Competitor Intelligence</h3>
        </div>
      </div>
      <div class="reels-compare-grid">
        ${topCompetitor ? `
          <article class="reels-competitor-hero">
            <span>Top competitor formula</span>
            <h4>${esc(topCompetitor.competitor || "Competitor")}</h4>
            <p>${esc(topCompetitor.winning_pattern || "-")}</p>
            <div class="mono">Hook: ${esc(topCompetitor.hook_format || "-")} | CTA: ${esc(topCompetitor.cta_strategy || "-")}</div>
            <div class="mono">Viral probability: ${esc(topCompetitor.score ?? "-")}/100</div>
          </article>
        ` : `<div class="reels-empty-inline">Add competitor reels or usernames to compare winning formulas.</div>`}
        ${(analysis.competitor_winning_reels || []).slice(0, 3).map((item) => `
          <article class="reel-mini-card">
            <div class="reel-mini-label">${esc(item.competitor || "Competitor")}</div>
            <h4>${esc(item.hook_format || "-")}</h4>
            <p>${esc(item.why_it_wins || "-")}</p>
            <div class="mono">${esc(item.reusable_formula || "-")}</div>
          </article>
        `).join("")}
      </div>
    </section>
  `;

  const trendSection = `
    <section class="reels-dashboard-section">
      <div class="reels-section-head">
        <div>
          <p class="panel-kicker">Section E</p>
          <h3>Trend Intelligence</h3>
        </div>
      </div>
      <div class="reels-trend-grid">
        ${(analysis.trend_objects || []).length ? (analysis.trend_objects || []).slice(0, 4).map((trend, index) => `
          <article class="reels-trend-card">
            <div class="reels-trend-top">
              <strong>${esc(trend.trend_name || "-")}</strong>
              <span class="reels-trend-badge ${index === 0 ? "is-rising" : trend.saturation_level === "high" ? "is-hot" : ""}">${esc(trend.saturation_level || "unknown")}</span>
            </div>
            <div class="reels-trend-metric">
              <span>Momentum</span>
              <strong>${esc(clampReelScore(trend.trend_score))}</strong>
            </div>
            <p>${esc((trend.hook_examples || [])[0] || "No hook example returned.")}</p>
            <div class="mono">${esc((trend.caption_patterns || []).join(" | ") || "No caption pattern")}</div>
          </article>
        `).join("") : `<div class="reels-empty-inline">Trend clusters will appear after enough reels or trend references are available.</div>`}
      </div>
      ${topTrend ? `<div class="reels-opportunity-bar">Emerging opportunity: ${esc(topTrend.trend_name)} with ${esc(topTrend.viral_probability)}/100 viral probability.</div>` : ""}
    </section>
  `;

  const dnaSection = `
    <section class="reels-dashboard-section">
      <div class="reels-section-head">
        <div>
          <p class="panel-kicker">Section F</p>
          <h3>Reel DNA / Viral Score</h3>
        </div>
      </div>
      <div class="reel-score-grid">
        ${scoreCards.map(([label, value]) => `
          <div class="reel-score-card">
            <span>${esc(label)}</span>
            <strong>${esc(clampReelScore(value))}</strong>
          </div>
        `).join("")}
      </div>
    </section>
  `;

  const cinematicSection = `
    <section class="reels-dashboard-section">
      <div class="reels-section-head">
        <div>
          <p class="panel-kicker">Section G</p>
          <h3>Cinematic Script Output</h3>
        </div>
      </div>
      <div class="reels-scene-stack">
        ${timeline.length ? timeline.map((beat, index) => `
          <article class="reels-scene-card">
            <div class="reels-scene-head">
              <span>Scene ${index + 1} (${esc(beat.second_range || "-")})</span>
              <strong>${esc(beat.scene || "-")}</strong>
            </div>
            <div class="reels-scene-body">
              <p><strong>Dialogue:</strong> ${esc((beat.text_overlay || [])[0] || script.spoken_script || "-")}</p>
              <p><strong>Camera:</strong> ${esc(beat.camera_direction || "-")}</p>
              <p><strong>Subtitle:</strong> ${esc((beat.text_overlay || [])[0] || "-")}</p>
              <p><strong>Editing:</strong> ${esc((beat.editing_notes || []).join(", ") || "-")}</p>
              <p><strong>Music cue:</strong> ${esc((beat.sound_design || []).join(", ") || "-")}</p>
            </div>
          </article>
        `).join("") : `<div class="reels-empty-inline">Directed scenes will appear after script generation.</div>`}
      </div>
    </section>
  `;

  const storyboardSection = `
    <section class="reels-dashboard-section">
      <div class="reels-section-head">
        <div>
          <p class="panel-kicker">Section H</p>
          <h3>Storyboard View</h3>
        </div>
      </div>
      <div class="reels-storyboard-flow">
        ${[
          { label: "Hook", value: hookInsight?.insight || analysis.hook_alternatives?.[0] || "Opening hook not extracted yet" },
          { label: "Curiosity", value: emotionalInsight?.insight || "Curiosity beat pending" },
          { label: "Payoff", value: analysis.recommendations?.[0] || "Proof and payoff guidance will appear here" },
          { label: "CTA", value: script.cta || ctaInsight?.insight || "CTA pending" },
        ].map((item) => `
          <article class="reels-storyboard-card">
            <span>${esc(item.label)}</span>
            <strong>${esc(item.value)}</strong>
          </article>
        `).join("")}
      </div>
      <div class="reels-caption-bar">
        <div><strong>Caption pattern:</strong> ${esc(captionInsight?.insight || analysis.caption_pattern || "No caption pattern yet")}</div>
        <div><strong>Instagram caption:</strong> ${esc(analysis.instagram_caption || script.instagram_caption || "-")}</div>
      </div>
    </section>
  `;

  reelsOutput.innerHTML = `
    ${warningBanner}
    <section class="reels-intelligence-header">
      <div>
        <p class="panel-kicker">AI Reel Intelligence</p>
        <h3>${esc(analysis.brand_name || "Instagram Reel Analysis")}</h3>
        <p>${esc(analysis.summary || "Analyze why this reel works and how to build a stronger version.")}</p>
      </div>
      <div class="reels-intelligence-meta">
        <div class="reels-meta-card"><span>Confidence</span><strong>${esc(analysis.confidence_label || "Low")}</strong></div>
        <div class="reels-meta-card"><span>Virality</span><strong>${esc(clampReelScore(analysis.viral_probability_score))}</strong></div>
        <div class="reels-meta-card"><span>Retention</span><strong>${esc(clampReelScore(analysis.retention_score || analysis.audience_retention_prediction))}</strong></div>
      </div>
    </section>
    ${hookSection}
    ${timelineSection}
    ${retentionSection}
    ${competitorSection}
    ${trendSection}
    ${dnaSection}
    ${cinematicSection}
    ${storyboardSection}
  `;
  setCount("reels", Math.max(1, analysisItems.length, (analysis.trend_objects || []).length, (analysis.competitor_winning_reels || []).length));
}

function splitMultivalue(value) {
  return String(value || "")
    .split(/[\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseBoundedNumber(value, fallback, min, max) {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(min, Math.min(max, parsed));
}

function setInstagramPipelineStage(stage, status = "idle") {
  const strip = instagramIngestionControls.pipelineStrip();
  if (!strip) return;
  const order = ["ingest", "analyze", "trends", "script", "direct"];
  const currentIndex = order.indexOf(stage);
  strip.querySelectorAll(".reels-pipeline-step").forEach((node) => {
    const step = node.dataset.stage;
    const stepIndex = order.indexOf(step);
    node.classList.remove("is-active", "is-done", "is-error");
    if (status === "error" && step === stage) {
      node.classList.add("is-error");
      return;
    }
    if (stepIndex < currentIndex || (step === stage && status === "done")) {
      node.classList.add("is-done");
    } else if (step === stage && status === "active") {
      node.classList.add("is-active");
    }
  });
}

async function runInstagramAutoPipeline() {
  if (instagramAutoPipelineRunning) return;
  instagramAutoPipelineRunning = true;
  try {
    setInstagramPipelineStage("analyze", "active");
    setInstagramIngestionStatus(instagramIngestionJobState, "Ingestion complete. Analyzing hook and retention patterns...");
    const analyzeData = await runInstagramStage("analyze", { silentChat: true });

    setInstagramPipelineStage("analyze", "done");
    setInstagramPipelineStage("trends", "active");
    setInstagramIngestionStatus(instagramIngestionJobState, "Trend signals detected. Mapping competitor and format patterns...");
    setInstagramPipelineStage("trends", "done");
    setInstagramPipelineStage("script", "active");
    setInstagramIngestionStatus(instagramIngestionJobState, "Generating cinematic script and scene logic...");

    const directData = await runInstagramStage("direct", { silentChat: true });
    const finalData = directData || analyzeData;

    setInstagramPipelineStage("script", "done");
    setInstagramPipelineStage("direct", "active");
    setInstagramPipelineStage("direct", "done");
    setInstagramIngestionStatus(instagramIngestionJobState, "Intelligence dashboard ready. Viral hook, trend, competitor, and script analysis loaded.", "success");
    if (finalData) {
      renderReelsAnalysis(finalData);
    }
  } catch (error) {
    setInstagramPipelineStage("direct", "error");
    setInstagramIngestionStatus(instagramIngestionJobState, error.message || "Auto-pipeline failed while building reel intelligence.", "error");
  } finally {
    instagramAutoPipelineRunning = false;
  }
}

function clearInstagramIngestionPoll() {
  if (instagramIngestionPollHandle) {
    clearTimeout(instagramIngestionPollHandle);
    instagramIngestionPollHandle = null;
  }
}

function setInstagramIngestionDisabled(disabled) {
  const controls = [
    instagramIngestionControls.submit(),
    instagramIngestionControls.reset(),
    instagramIngestionControls.brief(),
    instagramIngestionControls.singleMode(),
    instagramIngestionControls.singleTranscript(),
    instagramIngestionControls.singleCaption(),
    instagramIngestionControls.singleHook(),
    instagramIngestionControls.singleViews(),
    instagramIngestionControls.singleLikes(),
    instagramIngestionControls.singleComments(),
    instagramIngestionControls.singleShares(),
    instagramIngestionControls.reelUrls(),
    instagramIngestionControls.usernames(),
    instagramIngestionControls.competitorReels(),
    instagramIngestionControls.trendingReels(),
    instagramIngestionControls.niche(),
    instagramIngestionControls.audience(),
    instagramIngestionControls.jobName(),
    instagramIngestionControls.maxReels(),
    instagramIngestionControls.cacheTtl(),
    instagramIngestionControls.rateLimit(),
    instagramIngestionControls.includeComments(),
    instagramIngestionControls.includeMetrics(),
    instagramIngestionControls.forceRefresh(),
    instagramIngestionControls.addCompetitors(),
    instagramIngestionControls.runAnalyze(),
    instagramIngestionControls.runTrends(),
    instagramIngestionControls.runScript(),
    instagramIngestionControls.runDirect(),
    instagramIngestionControls.runScore(),
  ];
  controls.forEach((control) => {
    if (control) control.disabled = disabled;
  });
}

function setInstagramIngestionStatus(job, message, kind = "neutral") {
  const stateEl = instagramIngestionControls.state();
  const jobIdEl = instagramIngestionControls.jobId();
  const progressFill = instagramIngestionControls.progress();
  const messageEl = instagramIngestionControls.message();

  if (stateEl) {
    const stateLabel = job?.status ? humanizeToken(job.status) : "Idle";
    stateEl.textContent = stateLabel;
    stateEl.style.color = kind === "error" ? "#f87171" : kind === "success" ? "#4ade80" : "#ffffff";
  }

  if (jobIdEl) {
    jobIdEl.textContent = job?.job_id ? `Job ${job.job_id}` : "No job queued";
  }

  if (progressFill) {
    const progress = Number.isFinite(Number(job?.progress)) ? Math.max(0, Math.min(100, Number(job.progress))) : 0;
    progressFill.style.width = `${progress}%`;
    progressFill.classList.toggle("is-error", kind === "error");
  }

  if (messageEl) {
    messageEl.textContent = message || job?.message || "";
    messageEl.classList.toggle("is-error", kind === "error");
  }
}

function renderInstagramIngestionResult(result) {
  const container = instagramIngestionControls.result();
  if (!container) return;

  if (!result) {
    container.innerHTML = `
      <div class="card instagram-ingestion-empty">
        <p>Source intelligence will appear here once a reel is scanned. We will summarize source quality, detected captions, trend cues, and competitor signals before generating the final dashboard.</p>
      </div>
    `;
    return;
  }

  const reels = result.reels || [];
  const trends = result.trend_snapshots || [];
  const insights = result.competitor_insights || [];

  const chipList = (items, emptyLabel = "-") =>
    items && items.length
      ? `<div class="instagram-chip-list">${items.map((item) => `<span class="metric-pill">${esc(item)}</span>`).join("")}</div>`
      : `<div class="mono">${esc(emptyLabel)}</div>`;

  const sourceStrength = Math.min(
    100,
    reels.length * 10
      + (result.caption_patterns || []).length * 9
      + (result.audio_patterns || []).length * 8
      + (result.hook_library || []).length * 6
      + insights.length * 7
  );
  const reelCards = reels.length
    ? `<div class="instagram-ingestion-reel-list">${reels.slice(0, 3).map((reel) => `
        <div class="instagram-ingestion-reel-card">
          <div class="instagram-ingestion-reel-head">
            <strong>${esc(reel.username || reel.competitor_name || reel.reel_id || "Reel source")}</strong>
            <span>${esc(reel.hook_type || reel.source_type || "source")}</span>
          </div>
          <p>${esc(reel.hook_text || reel.caption || reel.transcript || "No transcript or hook text extracted yet.")}</p>
          <div class="instagram-ingestion-reel-metrics">
            <span>Views ${esc(reel.engagement?.views ?? "-")}</span>
            <span>Likes ${esc(reel.engagement?.likes ?? "-")}</span>
            <span>Shares ${esc(reel.engagement?.shares ?? "-")}</span>
          </div>
        </div>
      `).join("")}</div>`
    : '<div class="card"><p>No usable reel sources were extracted yet.</p></div>';

  container.innerHTML = `
    <div class="card instagram-ingestion-summary-card">
      <div class="instagram-ingestion-summary-grid">
        <div class="instagram-ingestion-summary-metric"><span>Source strength</span><strong>${esc(sourceStrength)}</strong></div>
        <div class="instagram-ingestion-summary-metric"><span>Reels scanned</span><strong>${esc(reels.length)}</strong></div>
        <div class="instagram-ingestion-summary-metric"><span>Competitor signals</span><strong>${esc(insights.length)}</strong></div>
        <div class="instagram-ingestion-summary-metric"><span>Trend traces</span><strong>${esc((result.caption_patterns || []).length + (result.audio_patterns || []).length)}</strong></div>
        <div class="instagram-ingestion-summary-metric"><span>Benchmark</span><strong>${esc(result.benchmark_score ?? 0)}</strong></div>
        <div class="instagram-ingestion-summary-metric"><span>Momentum</span><strong>${esc(result.momentum_score ?? 0)}</strong></div>
      </div>
      <div class="instagram-ingestion-summary-lists">
        <div>
          <div class="reel-mini-label">Detected hook language</div>
          ${chipList(result.hook_library)}
        </div>
        <div>
          <div class="reel-mini-label">Caption patterns</div>
          ${chipList(result.caption_patterns)}
        </div>
        <div>
          <div class="reel-mini-label">Hashtag patterns</div>
          ${chipList(result.hashtag_patterns)}
        </div>
        <div>
          <div class="reel-mini-label">Posting windows</div>
          ${chipList(result.posting_time_patterns)}
        </div>
        <div>
          <div class="reel-mini-label">Audio patterns</div>
          ${chipList(result.audio_patterns)}
        </div>
      </div>
    </div>
    <div class="card instagram-ingestion-reels-card">
      <h3>Source scan highlights</h3>
      ${reelCards}
    </div>
    <div class="card instagram-ingestion-trends-card">
      <h3>Trend traces</h3>
      ${trends.length ? `<div class="instagram-ingestion-trend-list">${trends.slice(0, 3).map((trend) => `
        <div class="instagram-ingestion-trend-card">
          <strong>${esc(trend.trend_name || trend.snapshot_id || "Trend")}</strong>
          <div class="mono">Score ${esc(trend.trend_score ?? 0)} | Viral ${esc(trend.viral_probability ?? 0)} | ${esc(trend.saturation_level || "unknown")}</div>
        </div>
      `).join("")}</div>` : '<div class="card"><p>We captured the sources, but they are still too thin to surface distinct trend snapshots.</p></div>'}
    </div>
  `;

  instagramIngestionResultState = result;
  chatContext.instagram_ingestion = {
    job: instagramIngestionJobState,
    result,
  };
}

function resetInstagramIngestionPanel() {
  const controls = instagramIngestionControls;
  const valueControls = [
    controls.reelUrls(),
    controls.brief(),
    controls.singleTranscript(),
    controls.singleCaption(),
    controls.singleHook(),
    controls.singleViews(),
    controls.singleLikes(),
    controls.singleComments(),
    controls.singleShares(),
    controls.usernames(),
    controls.competitorReels(),
    controls.trendingReels(),
    controls.niche(),
    controls.audience(),
    controls.jobName(),
  ];

  valueControls.forEach((control) => {
    if (control) control.value = "";
  });

  if (controls.maxReels()) controls.maxReels().value = "20";
  if (controls.cacheTtl()) controls.cacheTtl().value = "1800";
  if (controls.rateLimit()) controls.rateLimit().value = "30";
  if (controls.includeComments()) controls.includeComments().checked = true;
  if (controls.includeMetrics()) controls.includeMetrics().checked = true;
  if (controls.forceRefresh()) controls.forceRefresh().checked = false;
  if (controls.singleMode()) controls.singleMode().checked = false;

  instagramIngestionJobId = null;
  instagramIngestionJobState = null;
  instagramIngestionResultState = null;
  instagramAutoPipelineRunning = false;
  clearInstagramIngestionPoll();
  setInstagramIngestionDisabled(false);
  const secondarySources = controls.secondarySources();
  if (secondarySources) secondarySources.classList.add("hidden");
  const singleFields = controls.singleFields();
  if (singleFields) singleFields.classList.add("hidden");
  if (controls.addCompetitors()) controls.addCompetitors().textContent = "Upload Competitor Reels";
  setInstagramPipelineStage("ingest", "active");
  setInstagramIngestionStatus(null, "Paste a reel URL and we will run the full intelligence pipeline automatically.");
  renderInstagramIngestionResult(null);
}

async function fetchInstagramIngestionJob(jobId) {
  const response = await fetch(`${API_BASE_URL}/instagram/ingestion-jobs/${encodeURIComponent(jobId)}`);
  if (!response.ok) {
    throw new Error(await parseErrorResponse(response));
  }
  return response.json();
}

async function fetchInstagramIngestionResult(jobId) {
  const response = await fetch(`${API_BASE_URL}/instagram/ingestion-jobs/${encodeURIComponent(jobId)}/result`);
  if (!response.ok) {
    throw new Error(await parseErrorResponse(response));
  }
  return response.json();
}

async function pollInstagramIngestionJob(jobId) {
  clearInstagramIngestionPoll();
  try {
    const job = await fetchInstagramIngestionJob(jobId);
    instagramIngestionJobState = job;
    setInstagramIngestionStatus(job, job.message || `Job ${job.status || "queued"}.`);

    if (job.status === "completed") {
      const result = await fetchInstagramIngestionResult(jobId);
      instagramIngestionResultState = result;
      renderInstagramIngestionResult(result);
      setInstagramPipelineStage("ingest", "done");
      setInstagramIngestionStatus(job, "Source scan complete. Building viral hook, trend, and direction intelligence...", "success");
      setInstagramIngestionDisabled(false);
      clearInstagramIngestionPoll();
      await runInstagramAutoPipeline();
      return;
    }

    if (job.status === "failed") {
      setInstagramPipelineStage("ingest", "error");
      setInstagramIngestionStatus(job, job.error || job.message || "Ingestion failed.", "error");
      setInstagramIngestionDisabled(false);
      clearInstagramIngestionPoll();
      return;
    }

    instagramIngestionPollHandle = setTimeout(() => pollInstagramIngestionJob(jobId), 2500);
  } catch (error) {
    setInstagramIngestionStatus({ job_id: jobId, status: "failed", progress: 0 }, error.message || "Could not load ingestion job.", "error");
    setInstagramIngestionDisabled(false);
  }
}

async function submitInstagramIngestionJob() {
  const reelUrls = splitMultivalue(instagramIngestionControls.reelUrls()?.value);
  const usernames = splitMultivalue(instagramIngestionControls.usernames()?.value);
  const competitorReels = splitMultivalue(instagramIngestionControls.competitorReels()?.value).map((reelUrl) => ({ reel_url: reelUrl }));
  const trendingReels = splitMultivalue(instagramIngestionControls.trendingReels()?.value).map((reelUrl) => ({ reel_url: reelUrl }));

  if (!reelUrls.length && !usernames.length && !competitorReels.length && !trendingReels.length) {
    setInstagramIngestionStatus(null, "Add at least one reel URL, username, competitor reel, or trending reel.", "error");
    return;
  }

  const payload = {
    reel_urls: reelUrls,
    instagram_usernames: usernames,
    competitor_reels: competitorReels,
    trending_reels: trendingReels,
    niche: instagramIngestionControls.niche()?.value.trim() || null,
    audience: instagramIngestionControls.audience()?.value.trim() || null,
    max_reels: parseBoundedNumber(instagramIngestionControls.maxReels()?.value, 20, 1, 100),
    include_comments: Boolean(instagramIngestionControls.includeComments()?.checked),
    include_metrics: Boolean(instagramIngestionControls.includeMetrics()?.checked),
    force_refresh: Boolean(instagramIngestionControls.forceRefresh()?.checked),
    cache_ttl_seconds: parseBoundedNumber(instagramIngestionControls.cacheTtl()?.value, 1800, 0, 86400),
    rate_limit_per_minute: parseBoundedNumber(instagramIngestionControls.rateLimit()?.value, 30, 1, 120),
    job_name: instagramIngestionControls.jobName()?.value.trim() || null,
    async_job: true,
  };

  clearInstagramIngestionPoll();
  setInstagramIngestionDisabled(true);
  renderInstagramIngestionResult(null);
  setInstagramPipelineStage("ingest", "active");
  setInstagramIngestionStatus({ status: "queued", progress: 0 }, "Submitting reel sources for ingestion...");
  showResults();
  activateTab("reels");

  try {
    const response = await fetch(`${API_BASE_URL}/instagram/ingest-reels`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(await parseErrorResponse(response));
    }

    const job = await response.json();
    instagramIngestionJobId = job.job_id || null;
    instagramIngestionJobState = job;
    setInstagramIngestionStatus(job, job.message || "Ingestion job queued.");

    if (job.status === "completed") {
      const result = await fetchInstagramIngestionResult(job.job_id);
      instagramIngestionResultState = result;
      renderInstagramIngestionResult(result);
      setInstagramPipelineStage("ingest", "done");
      setInstagramIngestionStatus(job, "Source scan complete. Building viral hook, trend, and direction intelligence...", "success");
      setInstagramIngestionDisabled(false);
      await runInstagramAutoPipeline();
      return;
    }

    pollInstagramIngestionJob(job.job_id);
  } catch (error) {
    setInstagramPipelineStage("ingest", "error");
    setInstagramIngestionStatus({ job_id: instagramIngestionJobId, status: "failed", progress: 0 }, error.message || "Ingestion failed.", "error");
    setInstagramIngestionDisabled(false);
  }
}

function buildInstagramReelsPayloadFromState(briefText) {
  const ingestionResult = chatContext?.instagram_ingestion?.result || instagramIngestionResultState || {};
  const normalized = Array.isArray(ingestionResult.reels) ? ingestionResult.reels : [];
  const singleMode = Boolean(instagramIngestionControls.singleMode()?.checked);
  const singleTranscript = instagramIngestionControls.singleTranscript()?.value?.trim() || "";
  const singleCaption = instagramIngestionControls.singleCaption()?.value?.trim() || "";
  const singleHook = instagramIngestionControls.singleHook()?.value?.trim() || "";
  const singleViews = parseBoundedNumber(instagramIngestionControls.singleViews()?.value, 0, 0, 1000000000);
  const singleLikes = parseBoundedNumber(instagramIngestionControls.singleLikes()?.value, 0, 0, 1000000000);
  const singleComments = parseBoundedNumber(instagramIngestionControls.singleComments()?.value, 0, 0, 1000000000);
  const singleShares = parseBoundedNumber(instagramIngestionControls.singleShares()?.value, 0, 0, 1000000000);
  const competitorRefs = normalized
    .filter((item) => String(item?.source_type || "").toLowerCase().includes("compet"))
    .slice(0, 20)
    .map((item) => ({
      username: item.username || item.competitor_name || null,
      reel_url: item.reel_url || null,
      caption: item.caption || null,
      transcript: item.transcript || null,
      comments: Array.isArray(item.comments) ? item.comments : [],
      audio_name: item.audio_name || null,
      views: item.engagement?.views ?? null,
      likes: item.engagement?.likes ?? null,
      shares: item.engagement?.shares ?? null,
      saves: item.engagement?.saves ?? null,
    }));
  const trendingRefs = normalized
    .filter((item) => String(item?.source_type || "").toLowerCase().includes("trend"))
    .slice(0, 20)
    .map((item) => ({
      username: item.username || item.competitor_name || null,
      reel_url: item.reel_url || null,
      caption: item.caption || null,
      transcript: item.transcript || null,
      comments: Array.isArray(item.comments) ? item.comments : [],
      audio_name: item.audio_name || null,
      views: item.engagement?.views ?? null,
      likes: item.engagement?.likes ?? null,
      shares: item.engagement?.shares ?? null,
      saves: item.engagement?.saves ?? null,
    }));

  const reelUrls = splitMultivalue(instagramIngestionControls.reelUrls()?.value);
  const primaryReelUrl = reelUrls[0] || null;
  const manualSingleReference = singleMode ? [{
    username: null,
    reel_url: primaryReelUrl,
    caption: singleCaption || null,
    transcript: singleTranscript || null,
    comments: [],
    audio_name: null,
    views: singleViews > 0 ? singleViews : null,
    likes: singleLikes > 0 ? singleLikes : null,
    shares: singleShares > 0 ? singleShares : null,
    saves: null,
  }] : [];

  return {
    brief: instagramIngestionControls.brief()?.value.trim() || briefText,
    single_reel_mode: singleMode,
    brand_name: byId("f-brand")?.value?.trim() || "",
    niche: byId("instagram-ingest-niche")?.value?.trim() || "",
    audience: byId("instagram-ingest-audience")?.value?.trim() || "",
    goal: byId("f-objective")?.value || "conversions",
    tone: byId("f-tone")?.value || "premium",
    duration_seconds: 30,
    call_to_action: "Comment SCRIPT for the full playbook",
    transcript: singleTranscript || null,
    caption: singleCaption || null,
    hook_angle: singleHook || null,
    instagram_usernames: splitMultivalue(byId("instagram-ingest-usernames")?.value),
    competitor_reels: singleMode ? manualSingleReference.concat(competitorRefs) : competitorRefs,
    trending_reels: trendingRefs,
    normalized_reels: normalized.slice(0, 100),
    extra_context: String(chatContext?.campaign ? JSON.stringify(chatContext.campaign) : "").slice(0, 3000),
  };
}

async function runInstagramStage(stage, options = {}) {
  const endpointMap = {
    analyze: "/instagram/analyze-reel",
    trends: "/instagram/detect-trends",
    script: "/instagram/generate-script",
    direct: "/instagram/direct-reel",
    score: "/instagram/score-reel",
  };
  const endpoint = endpointMap[stage];
  if (!endpoint) return;

  const prompt = instagramIngestionControls.brief()?.value.trim() || chatInput?.value?.trim() || `Create a high-retention Instagram reel for ${byId("f-brand")?.value?.trim() || "my brand"}`;
  const payload = buildInstagramReelsPayloadFromState(prompt);
  if (!payload.brief || payload.brief.length < 3) {
    if (!options.silentChat) appendChat("ai", "Please enter a clearer reel brief (at least 3 characters).");
    return;
  }

  setInstagramPipelineStage(stage, "active");
  setStatus(`Running Instagram ${stage}...`);
  if (liveStatus) liveStatus.textContent = `Instagram ${stage} in progress...`;
  try {
    const res = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(await parseErrorResponse(res));
    const data = await res.json();
    renderReelsAnalysis(data);
    activateTab("reels");
    setInstagramPipelineStage(stage, "done");
    if (!options.silentChat) appendChat("ai", `Instagram ${stage} completed. Reels dashboard updated.`);
    return data;
  } catch (error) {
    setInstagramPipelineStage(stage, "error");
    if (!options.silentChat) appendChat("ai", `Instagram ${stage} failed: ${error.message || error}`);
    throw error;
  }
}

function fileNameFromPath(rawPath, fallback) {
  if (!rawPath) return fallback;
  const normalized = String(rawPath).replaceAll("\\", "/");
  const parts = normalized.split("/");
  return parts[parts.length - 1] || fallback;
}

async function downloadAsset(event, url, filename) {
  event.preventDefault();
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error("Download failed");
    const blob = await res.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(blobUrl);
  } catch (e) {
    console.error("Download error:", e);
    window.open(url, "_blank");
  }
}
window.downloadAsset = downloadAsset;

function downloadButton(url, filename, label) {
  if (!url) return "";
  const escUrl = esc(url);
  const escFile = esc(filename);
  return `<button class="download-btn" onclick="downloadAsset(event, '${escUrl}', '${escFile}')">${esc(label)}</button>`;
}

function renderScoreNote(asset) {
  const rationale = asset.score?.rationale || "";
  if (!rationale) return "";
  if (/heuristic review used/i.test(rationale)) return "";
  return `<div class="mono">${esc(rationale)}</div>`;
}

function humanizeToken(value) {
  return String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function renderAll(data) {
  showResults();
  activateTab("finals");

  const hooks = data.hooks || [];
  const angles = data.angles || [];
  const copies = [...(data.ad_copies || [])].sort((a, b) => (b.total_score ?? -1) - (a.total_score ?? -1));
  const concepts = data.visual_concepts || [];
  const assets = data.creative_assets || [];
  const exportRows = data.export_rows || [];
  const previews = assets.filter((asset) => asset.preview);
  const campaignDir = data.output_directory || "";
  const csvUrl = campaignDir ? toPublicAssetUrl(`${campaignDir}\\exports\\meta_ads_bulk_upload.csv`) : "";
  const renderedCount = assets.filter((asset) => asset.rendered_ad).length;

  setCount("finals", renderedCount);
  setCount("previews", previews.length);
  setCount("hooks", hooks.length);
  setCount("angles", angles.length);
  setCount("copy", copies.length);
  setCount("concepts", concepts.length);
  setCount("exports", exportRows.length);

  chatContext = { ...chatContext, campaign: { hooks, angles, copies, concepts, assets, exportRows } };
  setStatus(`Generated ${renderedCount} full ad${renderedCount === 1 ? "" : "s"} with previews and export assets.`);

  list(finalsOutput, assets, (asset) => {
    let displayUrl = asset.rendered_ad?.image_path ? toPublicAssetUrl(asset.rendered_ad.image_path) : null;
    if (!displayUrl && asset.generated_creative?.image_urls && asset.generated_creative.image_urls.length > 0) {
      displayUrl = asset.generated_creative.image_urls[0];
    }
    const assetsDownloadUrl = campaignDir ? toPublicAssetUrl(`${campaignDir}\\exports\\${asset.concept_id}-assets.zip`) : "";
    const mockupDownloadUrl = campaignDir ? toPublicAssetUrl(`${campaignDir}\\exports\\${asset.concept_id}-mockup.pdf`) : "";
    const visualConfidence = asset.score?.total_score ?? "-";
    
    return `
      <div class="card card-creative">
        <div class="creative-grid">
          <div>
            ${displayUrl ? `<img src="${displayUrl}" class="concept-img" alt="Generated ad" loading="lazy">` : '<div class="card-inline-empty">Image unavailable.</div>'}
          </div>
          <div class="creative-meta">
            <div class="pill-row">
              <span class="metric-pill">Rank ${esc(asset.score?.rank ?? "-")}</span>
              <span class="metric-pill">Score ${esc(asset.score?.total_score ?? "-")}</span>
              <span class="metric-pill">${esc(asset.platform)}</span>
            </div>
            <h3>${esc(asset.headline || asset.hook_text)}</h3>
            <div class="final-summary-grid">
              <div class="summary-chip emphasis">
                <span>Best Hook</span>
                <strong>${esc(asset.hook_text || "-")}</strong>
              </div>
              <div class="summary-chip emphasis">
                <span>Best Angle</span>
                <strong>${esc(asset.angle_name || "-")}</strong>
              </div>
              <div class="summary-chip confidence">
                <span>Visual Confidence</span>
                <strong>${esc(visualConfidence)}%</strong>
              </div>
            </div>
            <div class="ad-copy-block">
              <div class="ad-copy-label">Primary Text</div>
              <p class="ad-copy-body">${esc(asset.primary_text || "Primary text unavailable.")}</p>
            </div>
            <div class="ad-copy-block">
              <div class="ad-copy-label">Headline</div>
              <p class="ad-copy-inline">${esc(asset.headline || asset.hook_text || "-")}</p>
            </div>
            <div class="ad-copy-inline-row">
              <div><strong>Description:</strong> ${esc(asset.description || "-")}</div>
              <div><strong>CTA:</strong> ${esc(asset.cta || "-")}</div>
            </div>
            <div class="summary-stack">
              <div><strong>Visual Concept:</strong> ${esc(asset.visual_concept?.scene_description || "-")}</div>
              <div><strong>Hook Type:</strong> ${esc(humanizeToken(asset.hook_type || "-"))}</div>
              <div><strong>Image Provider:</strong> ${esc(asset.generated_creative?.provider || "-")}</div>
            </div>
            
            <div class="download-row">
              ${displayUrl ? `<button class="view-btn" onclick="openImageModal('${esc(displayUrl)}','${esc(asset.headline || 'Generated ad')}')">View</button>` : ''}
              ${downloadButton(assetsDownloadUrl, `${asset.concept_id}-assets.zip`, "Download Assets")}
              ${downloadButton(mockupDownloadUrl, `${asset.concept_id}-mockup.pdf`, "Download Ad Mockups")}
            </div>
            ${renderScoreNote(asset)}
          </div>
        </div>
      </div>
    `;
  });

  list(previewsOutput, previews, (asset) => {
    const previewUrl = toPublicAssetUrl(asset.preview?.image_path);
    return `
      <div class="card">
        <h3>${esc(asset.campaign_name)} | ${esc(asset.platform)} preview</h3>
        ${previewUrl ? `<img src="${previewUrl}" class="concept-img" alt="Feed preview">` : '<div class="card-inline-empty">Preview unavailable.</div>'}
        <p><strong>Primary Text:</strong> ${esc(asset.primary_text || "-")}</p>
        <p><strong>Headline:</strong> ${esc(asset.headline || "-")}</p>
        <div class="download-row">
          ${downloadButton(previewUrl, fileNameFromPath(asset.preview?.image_path, `${asset.concept_id}-preview.png`), "Download Preview")}
        </div>
      </div>
    `;
  });

  list(hooksOutput, hooks, (x) => `<div class="card"><h3>${esc(humanizeToken(x.type))}</h3><p>${esc(x.text)}</p><p>${esc(x.rationale)}</p></div>`);
  list(anglesOutput, angles, (x) => `<div class="card"><h3>${esc(x.name)}</h3><p>${esc(x.description)}</p><p>Emotion: ${esc(x.target_emotion)} | Use case: ${esc(x.use_case)}</p></div>`);
  list(copyOutput, copies, (x) => `<div class="card"><h3>${esc(x.headline)}</h3><p><strong>Primary Text:</strong> ${esc(x.primary_text)}</p><p><strong>Description:</strong> ${esc(x.description)}</p><p>CTA: ${esc(x.cta)} | Hook: ${esc(x.hook_text)}</p><div class="mono">Score: ${esc(x.total_score ?? "-")} | Rank: ${esc(x.score_rank ?? "-")} | Angle: ${esc(x.angle_name)}</div></div>`);
  list(conceptsOutput, concepts, (x) => `<div class="card"><h3>${esc(x.concept_id)} | ${esc(x.aspect_ratio)} | ${esc(x.media_type)}</h3><p>${esc(x.scene_description)}</p><div class="mono">${esc(x.generation_prompt)}</div></div>`);
  list(exportsOutput, exportRows, (row, index) => {
    const imageUrl = toPublicAssetUrl(row.image_path);
    const previewUrl = toPublicAssetUrl(row.preview_path);
    return `
    <div class="card">
      <h3>${esc(row.ad_name)}</h3>
      <p><strong>Campaign:</strong> ${esc(row.campaign_name)}</p>
      <p><strong>Ad Set:</strong> ${esc(row.ad_set_name)}</p>
      <p><strong>Headline:</strong> ${esc(row.headline)}</p>
      <p><strong>CTA:</strong> ${esc(row.cta)}</p>
      <div class="download-row">
        ${downloadButton(csvUrl, fileNameFromPath(csvUrl, "meta_ads_bulk_upload.csv"), index === 0 ? "Download CSV" : "CSV")}
        ${downloadButton(imageUrl, fileNameFromPath(row.image_path, `${row.ad_name}.png`), "Rendered PNG")}
        ${downloadButton(previewUrl, fileNameFromPath(row.preview_path, `${row.ad_name}-preview.png`), "Preview PNG")}
      </div>
      <div class="mono">${esc(row.image_path)}${row.preview_path ? `\n${esc(row.preview_path)}` : ""}</div>
    </div>
  `;
  });
}

function appendChat(role, text, isHtml) {
  const row = document.createElement("div");
  row.className = "chat-row" + (role === "user" ? " user" : "");
  const content = isHtml ? text : esc(text);
  row.innerHTML = `<div class="chat-avatar">${role === "user" ? "You" : "AI"}</div><div class="chat-bubble">${content}<div class="meta">${role === "user" ? "You" : "Assistant"}</div></div>`;
  chatBody.appendChild(row);
  chatBody.scrollTop = chatBody.scrollHeight;
}

/**
 * Fill form fields visually from extracted campaign parameters.
 */
function fillFormFromExtracted(params) {
  if (!params) return;

  // Map LLM tone values to valid dropdown options
  const toneMapping = {
    premium: "premium", luxurious: "premium", elegant: "premium", sophisticated: "premium",
    casual: "casual", relaxed: "casual", laid_back: "casual", conversational: "casual",
    bold: "bold", strong: "bold", powerful: "bold", aggressive: "bold", edgy: "bold", modern: "bold",
    friendly: "friendly", warm: "friendly", playful: "friendly", fun: "friendly", cheerful: "friendly", approachable: "friendly",
    urgent: "urgent", fomo: "urgent", limited: "urgent", exclusive: "urgent",
  };

  const platformMapping = {
    meta: "meta", facebook: "meta", instagram: "meta", fb: "meta",
    google: "google", youtube: "google", search: "google",
    tiktok: "tiktok", "tik tok": "tiktok",
  };

  const objectiveMapping = {
    conversions: "conversions", sales: "conversions", purchase: "conversions", leads: "conversions",
    traffic: "traffic", clicks: "traffic", visits: "traffic",
    awareness: "awareness", reach: "awareness", branding: "awareness", brand: "awareness",
  };

  // Helper to set select value with fuzzy matching
  function setSelectValue(elementId, value, mapping) {
    const el = byId(elementId);
    if (!el || !value) return;
    const lower = value.toLowerCase().trim();
    // Try exact match first
    const options = Array.from(el.options).map(o => o.value);
    if (options.includes(lower)) {
      el.value = lower;
    } else if (mapping[lower]) {
      el.value = mapping[lower];
    } else {
      // Default to first option
      el.value = options[0] || lower;
    }
    el.style.transition = "background-color 0.3s ease";
    el.style.backgroundColor = "rgba(99, 102, 241, 0.2)";
    setTimeout(() => { el.style.backgroundColor = ""; }, 1500);
  }

  // Text input fields
  const textFieldMap = {
    brand_name: "f-brand",
    product_description: "f-desc",
    target_audience: "f-audience",
    visual_style: "f-visual",
  };
  for (const [key, elementId] of Object.entries(textFieldMap)) {
    const el = byId(elementId);
    if (el && params[key]) {
      el.value = params[key];
      el.style.transition = "background-color 0.3s ease";
      el.style.backgroundColor = "rgba(99, 102, 241, 0.2)";
      setTimeout(() => { el.style.backgroundColor = ""; }, 1500);
    }
  }

  // Select/dropdown fields with fuzzy matching
  if (params.platform) setSelectValue("f-platform", params.platform, platformMapping);
  if (params.objective) setSelectValue("f-objective", params.objective, objectiveMapping);
  if (params.tone) setSelectValue("f-tone", params.tone, toneMapping);

  // Array fields (comma-separated)
  const arrayFieldMap = {
    key_benefits: "f-benefits",
    competitors: "f-competitors",
    brand_colors: "f-brand-colors",
    brand_fonts: "f-brand-fonts",
  };
  for (const [key, elementId] of Object.entries(arrayFieldMap)) {
    const el = byId(elementId);
    if (el && params[key] && Array.isArray(params[key]) && params[key].length > 0) {
      el.value = params[key].join(", ");
      el.style.transition = "background-color 0.3s ease";
      el.style.backgroundColor = "rgba(99, 102, 241, 0.2)";
      setTimeout(() => { el.style.backgroundColor = ""; }, 1500);
    }
  }
}

/**
 * Check if a message looks like a campaign generation request.
 */
function looksLikeCampaignRequest(message) {
  const lower = message.toLowerCase().trim();
  // Must be a clear command to generate a campaign
  const campaignIntents = [
    "generate ad", "create ad", "make ad", "build ad", "design ad",
    "generate campaign", "create campaign", "make campaign",
    "ad creatives for", "ad campaign for"
  ];
  return campaignIntents.some(intent => lower.includes(intent));
}

async function sendChatMessage() {
  const message = chatInput.value.trim();
  
  // Move current attachments to chatbotSessionAttachments so they aren't "left behind" in the input area
  if (chatAttachedFiles.length > 0) {
    console.log(`[CHATBOT] Saving ${chatAttachedFiles.length} attached image(s) to chatbotSessionAttachments.`);
    chatbotSessionAttachments = chatbotSessionAttachments.concat(chatAttachedFiles);
    chatAttachedFiles = [];
    updateChatAttachmentsPreview();
  }

  if (!message && chatbotSessionAttachments.length === 0) return;
  
  if (message) {
    appendChat("user", message);
  } else {
    appendChat("user", "[Sent attached image(s)]");
  }

  chatInput.value = "";
  chatSend.disabled = true;

  try {
    const mode = chatModeSelect ? chatModeSelect.value : "ask";
    const isCampaignRequest = (mode === "generate");
    const activeSpecialist = chatContext.active_specialist || "";
    const isReelsSpecialist = activeSpecialist === "reels" && !isCampaignRequest;
    const endpoint = isCampaignRequest ? "/chat-generate" : (isReelsSpecialist ? "/reels-director" : "/chat-assistant");
    const ingestionResult = chatContext?.instagram_ingestion?.result || instagramIngestionResultState || {};
    const reelsRequestBody = {
      message,
      context: chatContext,
      session_id: chatSessionId,
      brand_name: byId("f-brand")?.value?.trim() || chatContext?.campaign?.brand_name || "",
      niche: byId("instagram-ingest-niche")?.value?.trim() || chatContext?.niche || "",
      competitors: splitMultivalue(byId("f-competitors")?.value || byId("instagram-ingest-usernames")?.value || ""),
      trending_reels: (ingestionResult.reels || []).filter((item) => (item.source_type || "").toLowerCase().includes("trend")).slice(0, 20),
      competitor_reels: (ingestionResult.reels || []).filter((item) => (item.source_type || "").toLowerCase().includes("compet")).slice(0, 20),
    };
    const requestBody = isReelsSpecialist
      ? reelsRequestBody
      : { message, context: chatContext, session_id: chatSessionId };

    const res = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody)
    });
    if (!res.ok) {
      throw new Error(await parseErrorResponse(res));
    }
    const data = await res.json();
    chatContext = data.context || chatContext;
    if (data.session_id && data.session_id !== chatSessionId) {
      chatSessionId = data.session_id;
      localStorage.setItem("chat_session_id", chatSessionId);
    }

    if (endpoint === "/reels-director") {
      appendChat("ai", data.reply || "Reels analysis generated.");
      if (data.analysis) {
        renderReelsAnalysis(data.analysis);
        activateTab("reels");
      }
    } else if (endpoint === "/chat-generate" && data.action === "generate" && data.extracted) {
      // Step 1: Show the AI reply
      appendChat("ai", data.reply);

      // Step 2: Auto-trigger generation directly from prompt data
      appendChat("ai", "⏳ <strong>Generating campaign directly...</strong> This may take 2-3 minutes.", true);

      setTimeout(async () => {
        try {
          const ext = data.extracted;
          
          const hook_count = parseInt(byId("f-hooks")?.value || "5", 10);
          const angle_count = parseInt(byId("f-angles")?.value || "3", 10);
          const copy_count = parseInt(byId("f-copy")?.value || "5", 10);
          const concept_count = Math.max(5, parseInt(byId("f-concepts")?.value || "5", 10));

          const payload = {
            brand_name: (ext.brand_name || "").trim(),
            product_description: (ext.product_description || "").trim(),
            target_audience: (ext.target_audience || "").trim(),
            platform: ext.platform || "meta",
            objective: ext.objective || "conversions",
            tone: ext.tone || "premium",
            key_benefits: Array.isArray(ext.key_benefits) ? ext.key_benefits : [],
            competitors: Array.isArray(ext.competitors) ? ext.competitors : [],
            visual_style: (ext.visual_style || "").trim(),
            brand_colors: Array.isArray(ext.brand_colors) ? ext.brand_colors : [],
            brand_fonts: Array.isArray(ext.brand_fonts) ? ext.brand_fonts : [],
            reference_similarity: 0.5,
            extra_details: (ext.extra_details || "").trim(),
            hook_count,
            angle_count,
            copy_count,
            concept_count,
            sample_images: []
          };

          // Attachments logic for chatbot generation
          if (chatbotSessionAttachments.length > 0) {
            const selected = chatbotSessionAttachments.slice(0, MAX_SAMPLE_IMAGES);
            for (const file of selected) {
              try {
                payload.sample_images.push(await getBase64(file));
              } catch (e) {
                console.error("Error reading attached file", e);
              }
            }
          }

          // Fetch the first Knowledge Base image as the Logo Icon (logo_image) for generation if available
          try {
            const kbEndpoint = (API_BASE_URL ? API_BASE_URL.replace(/\/+$/,'') : '') + '/knowledge-base/images';
            const kbRes = await fetch(kbEndpoint);
            if (kbRes.ok) {
              const kbData = await kbRes.json();
              const kbItems = kbData?.items || [];
              if (kbItems.length > 0) {
                const firstItem = kbItems[0];
                const kbUrl = toPublicAssetUrl(firstItem.web_path || firstItem.webPath || firstItem.path || "");
                if (kbUrl) {
                  payload.logo_image = kbUrl;
                }
              }
            }
          } catch (kbErr) {
            console.warn("Failed to retrieve Knowledge Base image for logo fallback:", kbErr);
          }

          // Console printing of image usage status
          console.log("\n" + "=".repeat(40));
          console.log("[FRONTEND] CREATIVE GENERATION IMAGE REFERENCES CHECK");
          if (payload.logo_image) {
            console.log("✅ Knowledge Base image WAS used as logo_image. URL:", payload.logo_image);
          } else {
            console.log("❌ No Knowledge Base image was found or used as logo_image.");
          }

          if (payload.sample_images && payload.sample_images.length > 0) {
            console.log(`✅ ${payload.sample_images.length} attached image(s) WERE used as reference sample_images.`);
            payload.sample_images.forEach((img, idx) => {
              console.log(`   * Attachment [${idx}]: length ${img.length} -> ${img.substring(0, 80)}...`);
            });
          } else {
            console.log("❌ No attached images were used as reference sample_images.");
          }
          console.log("=".repeat(40) + "\n");

          const validationErrors = validatePayload(payload);
          if (validationErrors.length) {
            appendChat("ai", `❌ Missing required fields: ${validationErrors.join(", ")}. Please supply them in your prompt and try again.`);
            return;
          }

          resetOutputs();
          showLoading();
          setStatus("Generating final ad package via chatbot...");
          heroGenerateButton.disabled = true;
          heroGenerateButton.textContent = "Generating...";

          const campaignData = await executeCampaignPipeline(payload);

          renderAll(campaignData);
          const assetCount = campaignData.creative_assets?.length || 0;
          appendChat("ai", `🎉 <strong>Campaign generated!</strong> ${assetCount} creative${assetCount !== 1 ? 's' : ''} created. Check the <strong>Concepts</strong> tab to view them.`, true);

          // Clear accumulated params and chat attachments for next conversation
          if (chatContext) {
            chatContext.accumulated_params = {};
          }
          chatAttachedFiles = [];
          chatbotSessionAttachments = [];
          updateChatAttachmentsPreview();
        } catch (genError) {
          setStatus(genError.message || "Generation failed.", true);
          showDashboard();
          appendChat("ai", `❌ Generation failed: ${genError.message || "Unknown error"}. Please try again.`);
        } finally {
          heroGenerateButton.disabled = false;
          heroGenerateButton.textContent = "Generate Final Ads";
        }
      }, 2000);

    } else if (endpoint === "/chat-generate" && data.action === "ask_details") {
      appendChat("ai", data.reply);
    } else {
      // Normal chat response
      appendChat("ai", data.reply || "No response received.");
    }

  } catch (error) {
    appendChat("ai", error.message || "Sorry, there was an error contacting the assistant.");
  } finally {
    chatSend.disabled = false;
  }
}

async function loadChatHistory() {
  if (!chatSessionId) return;
  try {
    // Load ALL session data: chat history, knowledge base, and execution history
    const res = await fetch(`${API_BASE_URL}/session-data/${chatSessionId}`);
    if (!res.ok) return;
    const data = await res.json();
    
    // Load chat history
    if (data.chat_history && data.chat_history.length > 0) {
      chatBody.innerHTML = "";
      data.chat_history.forEach((msg) => {
        appendChat(msg.role === "assistant" ? "ai" : "user", esc(msg.content));
      });
      chatContext.history = data.chat_history;
    }
    
    // Load knowledge base
    if (data.knowledge_base && data.knowledge_base.length > 0) {
      displayKnowledgeBase(data.knowledge_base);
    }
    
    // Load execution history
    if (data.execution_history && data.execution_history.length > 0) {
      displayExecutionHistory(data.execution_history);
    }
  } catch (e) {
    console.error("Failed to load session data:", e);
  }
}

function displayKnowledgeBase(kbItems) {
  const kbPanel = document.getElementById("knowledge-base-panel") || createKBPanel();
  const kbList = kbPanel.querySelector(".kb-items-list") || createKBList(kbPanel);
  
  kbList.innerHTML = "<h4>Previous Knowledge Base Items:</h4>";
  kbItems.forEach((item) => {
    const div = document.createElement("div");
    div.className = "kb-item";
    div.innerHTML = `
      <div class="kb-item-name">${esc(item.file_name)}</div>
      <div class="kb-item-meta">Type: ${esc(item.file_type)} | Added: ${new Date(item.created_at).toLocaleDateString()}</div>
      <button onclick="selectKBItem('${esc(item.file_path)}')">Use as Reference</button>
    `;
    kbList.appendChild(div);
  });
}

function displayExecutionHistory(executions) {
  const historyPanel = document.getElementById("history-panel") || createHistoryPanel();
  const historyList = historyPanel.querySelector(".history-items") || createHistoryList(historyPanel);
  
  historyList.innerHTML = "<h4>Previous Campaign Executions:</h4>";
  executions.forEach((exec) => {
    const div = document.createElement("div");
    div.className = `history-item ${exec.status}`;
    const timestamp = new Date(exec.created_at).toLocaleString();
    const duration = exec.execution_time_ms ? `${Math.round(exec.execution_time_ms / 1000)}s` : "N/A";
    
    div.innerHTML = `
      <div class="history-header">
        <span class="history-name">${esc(exec.campaign_name)}</span>
        <span class="history-type">${esc(exec.execution_type)}</span>
        <span class="history-status ${exec.status}">${exec.status.toUpperCase()}</span>
      </div>
      <div class="history-meta">
        <span>Duration: ${duration}</span>
        <span>Executed: ${timestamp}</span>
      </div>
      ${exec.error_message ? `<div class="history-error">Error: ${esc(exec.error_message)}</div>` : ""}
      <button onclick="expandExecutionDetails('${exec.id}', this)">View Details</button>
      <div class="execution-details" style="display:none;" data-exec-id="${exec.id}"></div>
    `;
    historyList.appendChild(div);
  });
}

function createKBPanel() {
  const panel = document.createElement("div");
  panel.id = "knowledge-base-panel";
  panel.className = "kb-panel";
  document.body.appendChild(panel);
  return panel;
}

function createKBList(panel) {
  const list = document.createElement("div");
  list.className = "kb-items-list";
  panel.appendChild(list);
  return list;
}

function createHistoryPanel() {
  const panel = document.getElementById("history-panel") || document.createElement("div");
  if (!panel.id) {
    panel.id = "history-panel";
    panel.className = "history-panel";
    document.body.appendChild(panel);
  }
  return panel;
}

function createHistoryList(panel) {
  const list = document.createElement("div");
  list.className = "history-items";
  panel.appendChild(list);
  return list;
}

function selectKBItem(filepath) {
  if (!selectedKnowledgeImages.includes(filepath)) {
    selectedKnowledgeImages.push(filepath);
    refreshSampleHint();
    console.log("Added reference:", filepath);
  }
}

function expandExecutionDetails(execId, button) {
  const detailsDiv = document.querySelector(`[data-exec-id="${execId}"]`);
  if (detailsDiv.style.display === "none") {
    detailsDiv.style.display = "block";
    detailsDiv.innerHTML = `<pre>${JSON.stringify({execution_id: execId}, null, 2)}</pre>`;
    button.textContent = "Hide Details";
  } else {
    detailsDiv.style.display = "none";
    button.textContent = "View Details";
  }
}

async function loadUiConfig() {
  try {
    const res = await fetch(`${API_BASE_URL}/ui-config`);
    const data = await res.json();
    document.title = data.app_name || "Creative Director Engine";
    if (!API_BASE_URL && data.backend_url && typeof data.backend_url === "string") {
      API_BASE_URL = data.backend_url.replace(/\/+$/, "");
    }
  } catch {
    document.title = "Creative Director Engine";
  }
}

async function loadProviderHealth() {
  try {
    const res = await fetch(`${API_BASE_URL}/provider-health`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

async function buildPayload() {
  // Validate and clamp count values to backend constraints
  const validateCount = (value, min, max, defaultVal) => {
    let num = parseInt(value, 10);
    if (isNaN(num)) num = defaultVal;
    if (num < min) num = min;
    if (num > max) num = max;
    return num;
  };

  const hook_count = validateCount(byId("f-hooks").value, 1, 10, 5);
  const angle_count = validateCount(byId("f-angles").value, 1, 10, 3);
  const copy_count = validateCount(byId("f-copy").value, 1, 10, 5);
  const concept_count = validateCount(byId("f-concepts").value, 1, 10, 5);

  const rawSimilarity = Number.parseFloat(referenceSimilarityInput?.value ?? "0.5");
  const safeSimilarity = Number.isFinite(rawSimilarity)
    ? Math.min(1, Math.max(0, rawSimilarity))
    : 0.5;

  const payload = {
    brand_name: byId("f-brand").value.trim(),
    product_description: byId("f-desc").value.trim(),
    target_audience: byId("f-audience").value.trim(),
    platform: byId("f-platform").value,
    objective: byId("f-objective").value,
    tone: byId("f-tone").value,
    key_benefits: byId("f-benefits").value.split(",").map((s) => s.trim()).filter(Boolean),
    competitors: byId("f-competitors").value.split(",").map((s) => s.trim()).filter(Boolean),
    visual_style: byId("f-visual").value.trim(),
    brand_colors: byId("f-brand-colors").value.split(",").map((s) => s.trim()).filter(Boolean),
    brand_fonts: byId("f-brand-fonts").value.split(",").map((s) => s.trim()).filter(Boolean),
    reference_similarity: safeSimilarity,
    extra_details: byId("f-extra") ? byId("f-extra").value.trim() : "",
    hook_count,
    angle_count,
    copy_count,
    concept_count,
    sample_images: []
  };

  if (logoInput && logoInput.files && logoInput.files[0]) {
    payload.logo_image = await getBase64(logoInput.files[0]);
  }

  if (selectedSampleFiles.length > 0) {
    console.log("buildPayload processing sample files", selectedSampleFiles);
    setStatus("Processing upload images...");
    const selected = selectedSampleFiles.slice(0, MAX_SAMPLE_IMAGES);
    for (const file of selected) {
      if (!file.type.startsWith("image/") || file.size > MAX_SAMPLE_IMAGE_SIZE_BYTES) {
        continue;
      }
      try {
        payload.sample_images.push(await getBase64(file));
      } catch (e) {
        console.error("Error reading file", e);
      }
    }

    setSampleHint(
      payload.sample_images.length
        ? `Using ${payload.sample_images.length} reference image(s) for generation.`
        : "No valid sample images selected. Using text-only generation.",
      payload.sample_images.length === 0
    );
  }

  // Include selected knowledge-base image URLs as references as well (within global limit).
  if (selectedKnowledgeImages && selectedKnowledgeImages.length) {
    const remainingSlots = Math.max(0, MAX_SAMPLE_IMAGES - payload.sample_images.length);
    if (remainingSlots > 0) {
      for (const u of selectedKnowledgeImages.slice(0, remainingSlots)) {
        payload.sample_images.push(u);
      }
    }
  }

  refreshSampleHint(
    payload.sample_images.length
      ? `Using ${payload.sample_images.length} reference image(s) for generation.`
      : defaultSampleHint(),
    false
  );
  console.log("buildPayload result sample_images", payload.sample_images);

  return payload;
}

async function executeCampaignPipeline(payload) {
  // Upload logo as asset to KB
  const logoInput = byId("f-logo");
  if (logoInput && logoInput.files && logoInput.files[0]) {
    try {
      const fd = new FormData();
      fd.append("file", logoInput.files[0], logoInput.files[0].name);
      fd.append("title", `${byId("f-brand").value || "asset"} - ${logoInput.files[0].name}`);
      fd.append("tags", "asset");
      await fetch(`${API_BASE_URL}/knowledge-base/images`, { method: "POST", body: fd });
    } catch (e) {
      console.warn("Logo KB upload failed", e);
    }
  }

  // If user uploaded sample files, save them to knowledge base first
  if (selectedSampleFiles.length) {
    const files = selectedSampleFiles.slice(0, MAX_SAMPLE_IMAGES);
    for (const f of files) {
      try {
        const fd = new FormData();
        fd.append("file", f, f.name);
        fd.append("title", `${byId("f-brand").value || "sample"} - ${f.name}`);
        fd.append("tags", "upload");
        await fetch(`${API_BASE_URL}/knowledge-base/images`, { method: "POST", body: fd });
      } catch (e) {
        console.warn("KB upload failed", e);
      }
    }
  }

  // STEP 1: Generate Concepts
  setStatus("Generating concepts (hooks, angles, copies)...");
  const conceptsResponse = await fetch(`${API_BASE_URL}/generate-concepts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const conceptsData = await conceptsResponse.json();
  if (!conceptsResponse.ok) throw new Error(conceptsData.detail || "Failed to generate concepts");

  const topConcepts = conceptsData.visual_concepts.slice(0, 3); // Hard limit to 3
  currentSuggestions = conceptsData.visual_concepts.slice(3);
  currentPayload = payload;
  
  if (currentSuggestions.length > 0) {
    renderSuggestions();
  } else {
    document.getElementById("suggestions-list").innerHTML = `
      <div class="card" style="border: 1px dashed #27272a !important; text-align: center; padding: 20px; background: #18181b !important;">
        <p style="margin: 0; color: var(--muted);">No unused concepts available for suggestions.</p>
      </div>`;
  }

  showResults();
  activateTab("finals");
  finalsOutput.innerHTML = "";
  setStatus("Concepts generated! Rendering images sequentially...");

  // STEP 2: Generate Images Sequentially
  const generated_creatives = [];
  for (let i = 0; i < topConcepts.length; i++) {
    const concept = topConcepts[i];
    setStatus(`Generating Image ${i + 1} of ${topConcepts.length}...`);

    const imageReq = {
      payload: payload,
      concept: concept
    };

    const imageResponse = await fetch(`${API_BASE_URL}/generate-image`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(imageReq)
    });
    const imageData = await imageResponse.json();
    if (!imageResponse.ok) {
      console.error(`Image ${i + 1} failed`, imageData);
      // push an empty/failed creative so scoring doesn't break
      generated_creatives.push({
         concept_id: concept.concept_id,
         provider: "unknown",
         status: "failed",
         prompt: concept.generation_prompt,
         error: "Failed to generate image"
      });
      continue;
    }

    generated_creatives.push(imageData);

    // Display partial card
    if (imageData.image_urls && imageData.image_urls.length > 0) {
      const tempCard = document.createElement("div");
      tempCard.className = "card card-creative";
      tempCard.innerHTML = `
         <div class="card-status-bar" style="background-color: #f5a623; color: white;">Scoring...</div>
         <div class="creative-image-container">
             <img src="${toPublicAssetUrl(imageData.image_urls[0])}" class="creative-image" alt="Generating...">
         </div>
         <div class="creative-content">
             <h3 class="creative-headline" style="color: #888;">Evaluating Text...</h3>
             <div class="score-meta">
                 <span class="meta-pill" style="opacity: 0.6;">Awaiting Score</span>
             </div>
         </div>
      `;
      finalsOutput.appendChild(tempCard);
    }
  }

  // STEP 3: Score and Package
  setStatus("All images generated! Running AI Scoring and Final Assembly...");
  const scoreReq = {
    payload: payload,
    hooks: conceptsData.hooks,
    angles: conceptsData.angles,
    ad_copies: conceptsData.ad_copies,
    visual_concepts: topConcepts,
    generated_creatives: generated_creatives
  };

  const scoreResponse = await fetch(`${API_BASE_URL}/score-and-package`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(scoreReq)
  });
  const scoreData = await scoreResponse.json();
  if (!scoreResponse.ok) throw new Error(scoreData.detail || "Scoring failed");

  return scoreData;
}

function wireEvents() {
  if (referenceSimilarityInput && referenceSimilarityValue) {
    const syncReferenceSimilarityValue = () => {
      const raw = Number.parseFloat(referenceSimilarityInput.value);
      const safe = Number.isFinite(raw) ? Math.min(1, Math.max(0, raw)) : 0.5;
      referenceSimilarityInput.value = safe.toFixed(2);
      referenceSimilarityValue.textContent = safe.toFixed(2);
    };
    referenceSimilarityInput.addEventListener("input", syncReferenceSimilarityValue);
    syncReferenceSimilarityValue();
  }
  updateReferenceSimilarityVisibility();

  // Validate count inputs against backend constraints
  const countConstraints = {
    "f-hooks": { min: 1, max: 10 },
    "f-angles": { min: 1, max: 10 },
    "f-copy": { min: 1, max: 10 },
    "f-concepts": { min: 1, max: 10 }
  };

  Object.entries(countConstraints).forEach(([id, { min, max }]) => {
    const input = byId(id);
    if (input) {
      const enforceConstraints = () => {
        let val = parseInt(input.value, 10);
        if (isNaN(val) || val < min) input.value = min;
        else if (val > max) input.value = max;
      };
      
      input.addEventListener("change", enforceConstraints);
      input.addEventListener("blur", enforceConstraints);
      input.addEventListener("input", () => {
        // On input, just update the input's min/max in case someone bypassed them
        input.min = min;
        input.max = max;
      });
    }
  });

  chatSend.addEventListener("click", sendChatMessage);
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage();
    }
  });

  if (chatAttachBtn && chatAttachInput) {
    chatAttachBtn.addEventListener("click", () => chatAttachInput.click());
    chatAttachInput.addEventListener("change", () => {
      const files = Array.from(chatAttachInput.files || []);
      for (const file of files) {
        if (file.type.startsWith("image/")) {
          chatAttachedFiles.push(file);
        }
      }
      chatAttachInput.value = "";
      updateChatAttachmentsPreview();
    });
  }


  if (supervisorNav) {
    supervisorNav.addEventListener("click", () => {
      showSupervisor();
      setStatus("Performance Supervisor active.");
    });
  }

  dashboardNav.addEventListener("click", () => {
    showDashboard();
    setStatus("Finished ad workspace ready.");
  });

  const supBtnKb = byId("sup-btn-kb");
  if (supBtnKb) {
    supBtnKb.addEventListener("click", openKbModal);
  }

  const supBtnTrain = byId("sup-btn-train");
  if (supBtnTrain) {
    supBtnTrain.addEventListener("click", () => {
      const uploadInput = byId("kb-upload-input");
      if (uploadInput) uploadInput.click();
    });
  }

  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => activateTab(tab.dataset.tab));
  });

  const instagramIngestSubmit = instagramIngestionControls.submit();
  if (instagramIngestSubmit) {
    instagramIngestSubmit.addEventListener("click", submitInstagramIngestionJob);
  }

  const instagramIngestReset = instagramIngestionControls.reset();
  if (instagramIngestReset) {
    instagramIngestReset.addEventListener("click", resetInstagramIngestionPanel);
  }

  const instagramAddCompetitors = instagramIngestionControls.addCompetitors();
  if (instagramAddCompetitors) {
    instagramAddCompetitors.addEventListener("click", () => {
      const panel = instagramIngestionControls.secondarySources();
      if (!panel) return;
      panel.classList.toggle("hidden");
      instagramAddCompetitors.textContent = panel.classList.contains("hidden") ? "Upload Competitor Reels" : "Hide Competitor Sources";
    });
  }

  const instagramSingleMode = instagramIngestionControls.singleMode();
  if (instagramSingleMode) {
    instagramSingleMode.addEventListener("change", () => {
      const fields = instagramIngestionControls.singleFields();
      if (!fields) return;
      fields.classList.toggle("hidden", !instagramSingleMode.checked);
      if (instagramSingleMode.checked) {
        setInstagramIngestionStatus(
          instagramIngestionJobState,
          "Single reel mode enabled. Add transcript, caption, and opening hook for stronger analysis."
        );
      }
    });
  }

  if (instagramIngestionControls.runAnalyze()) instagramIngestionControls.runAnalyze().addEventListener("click", () => runInstagramStage("analyze"));
  if (instagramIngestionControls.runTrends()) instagramIngestionControls.runTrends().addEventListener("click", () => runInstagramStage("trends"));
  if (instagramIngestionControls.runScript()) instagramIngestionControls.runScript().addEventListener("click", () => runInstagramStage("script"));
  if (instagramIngestionControls.runDirect()) instagramIngestionControls.runDirect().addEventListener("click", () => runInstagramStage("direct"));
  if (instagramIngestionControls.runScore()) instagramIngestionControls.runScore().addEventListener("click", () => runInstagramStage("score"));

  if (instagramIngestionControls.result()) {
    resetInstagramIngestionPanel();
  }

  document.querySelectorAll(".specialist").forEach((item) => {
    item.addEventListener("click", () => {
      showResults();
      activateTab(item.dataset.agentTab);
    });
  });

  if (navExecutionHistory) {
    navExecutionHistory.addEventListener("click", async () => {
      showHistory();
      empty(historyOutput, "Loading execution history...");
      try {
        const res = await fetch(`${API_BASE_URL}/campaign-history`);
        if (!res.ok) throw new Error(await parseErrorResponse(res));
        const data = await res.json();

        if (!data.items || data.items.length === 0) {
          empty(historyOutput, "No previous executions found.");
          return;
        }

        historyOutput.innerHTML = data.items.map((campaign, idx) => {
          const expandId = `campaign-${idx}`;
          const primaryImage = campaign.creatives.length > 0 
            ? (campaign.creatives[0].rendered_image_path || campaign.creatives[0].preview_image_path)
            : null;
          const primaryImageUrl = toPublicAssetUrl(primaryImage);
          
          return `
            <div class="card campaign-card">
              <div class="campaign-header" onclick="toggleCampaign('${expandId}')">
                <div class="campaign-title-block">
                  <h3>${esc(campaign.campaign_name)}</h3>
                  <div class="campaign-meta">
                    <span class="meta-pill">Score ${esc(campaign.top_score)}</span>
                    <span class="meta-pill">${esc(campaign.total_creatives)} creatives</span>
                    <span class="meta-pill">${esc(campaign.platform)}</span>
                  </div>
                </div>
                ${primaryImageUrl ? `<img src="${primaryImageUrl}" class="campaign-thumbnail" alt="Campaign preview" onerror="this.style.display='none'">` : ""}
                <span class="toggle-icon">▼</span>
              </div>
              <div id="${expandId}" class="campaign-content">
                <div class="campaign-tabs">
                  <button class="tab-btn active" data-tab="hooks-${idx}">Hooks</button>
                  <button class="tab-btn" data-tab="angles-${idx}">Angles</button>
                  <button class="tab-btn" data-tab="visuals-${idx}">Visual Concepts</button>
                  <button class="tab-btn" data-tab="creatives-${idx}">Creatives</button>
                </div>
                
                <div id="hooks-${idx}" class="tab-content active">
                  ${campaign.hooks.map(h => `
                    <div class="item-box">
                      <strong>${esc(h.type)}</strong><br/>
                      <p>${esc(h.text)}</p>
                      <small>${esc(h.rationale)}</small>
                    </div>
                  `).join('')}
                </div>
                
                <div id="angles-${idx}" class="tab-content hidden">
                  ${campaign.angles.map(a => `
                    <div class="item-box">
                      <strong>${esc(a.name)}</strong><br/>
                      <p>${esc(a.description)}</p>
                      <small>Emotion: ${esc(a.target_emotion)}</small>
                    </div>
                  `).join('')}
                </div>
                
                <div id="visuals-${idx}" class="tab-content hidden">
                  ${campaign.visual_concepts.map(v => `
                    <div class="item-box">
                      <strong>${esc(v.concept_id)}</strong><br/>
                      <p>Scene: ${esc(v.scene_description)}</p>
                      <small>Style: ${esc(v.style_reference)} | Mood: ${esc(v.mood)}</small>
                    </div>
                  `).join('')}
                </div>
                
                <div id="creatives-${idx}" class="tab-content hidden">
                  ${campaign.creatives.map(c => {
                    const renderedUrl = toPublicAssetUrl(c.rendered_image_path);
                    return `
                      <div class="creative-item">
                        <div class="creative-info">
                          <strong>${esc(c.headline || "N/A")}</strong>
                          <p class="primary-text">${esc(c.primary_text || "-")}</p>
                          <p class="description">${esc(c.description || "-")}</p>
                          <p class="cta"><strong>CTA:</strong> ${esc(c.cta || "-")}</p>
                          <p class="score">Score: ${esc(c.score)}</p>
                        </div>
                        <div class="creative-downloads">
                            ${renderedUrl ? `<img src="${renderedUrl}" class="creative-thumb" alt="Preview" onerror="this.style.display='none'">` : ""}
                            ${renderedUrl ? `<button class="view-btn" onclick="openImageModal('${esc(renderedUrl)}', '${esc(c.headline || "Creative")}')">View</button>` : ''}
                            ${downloadButton(renderedUrl, `${c.concept_id}.png`, "Download PNG")}
                        </div>
                      </div>
                    `;
                  }).join('')}
                </div>
              </div>
            </div>
          `;
        }).join("");
        
        // Attach tab switch listeners
        document.querySelectorAll(".tab-btn").forEach(btn => {
          btn.addEventListener("click", function() {
            const tabGroup = this.parentElement;
            const tabContent = tabGroup.parentElement;
            const tabName = this.dataset.tab;
            
            tabGroup.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
            this.classList.add("active");
            
            tabContent.querySelectorAll(".tab-content").forEach(tc => tc.classList.add("hidden"));
            document.getElementById(tabName).classList.remove("hidden");
          });
        });
      } catch (e) {
        empty(historyOutput, `Error loading execution history: ${esc(e.message || "Unknown error")}`);
      }
    });
  }



  heroGenerateButton.addEventListener("click", async () => {
    const payload = await buildPayload();
    const validationErrors = validatePayload(payload);
    if (validationErrors.length) {
      setStatus(validationErrors[0], true);
      byId("f-brand")?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }

    resetOutputs();
    showLoading();
    setStatus("Generating final ad package...");
    heroGenerateButton.disabled = true;
    heroGenerateButton.textContent = "Generating...";

      try {
        const scoreData = await executeCampaignPipeline(payload);
        renderAll(scoreData);
      } catch (error) {
        setStatus(error.message || "Generation failed.", true);
        showDashboard();
    } finally {
      heroGenerateButton.disabled = false;
      heroGenerateButton.textContent = "Generate Final Ads";
    }
  });

  if (sampleInput) {
    sampleInput.addEventListener("change", () => {
      const files = Array.from(sampleInput.files || []);
      if (!files.length) {
        refreshSampleHint();
        return;
      }

      const existingKeys = new Set(selectedSampleFiles.map(sampleFileKey));
      let addedCount = 0;
      let tooLarge = false;
      let badType = false;
      let duplicates = 0;
      let limitReached = false;

      for (const file of files) {
        if (!file.type.startsWith("image/")) {
          badType = true;
          continue;
        }
        if (file.size > MAX_SAMPLE_IMAGE_SIZE_BYTES) {
          tooLarge = true;
          continue;
        }

        const key = sampleFileKey(file);
        if (existingKeys.has(key)) {
          duplicates += 1;
          continue;
        }

        if (totalSelectedReferences() >= MAX_SAMPLE_IMAGES) {
          limitReached = true;
          break;
        }

        selectedSampleFiles.push(file);
        existingKeys.add(key);
        addedCount += 1;
      }

      sampleInput.value = "";
      updateSamplesList();

      const notes = [];
      if (duplicates) notes.push(`${duplicates} duplicate skipped`);
      if (tooLarge) notes.push("oversize skipped");
      if (badType) notes.push("non-image skipped");
      if (limitReached) notes.push(`limit is ${MAX_SAMPLE_IMAGES}`);

      if (addedCount > 0) {
        const noteText = notes.length ? ` (${notes.join(", ")})` : "";
        refreshSampleHint(`Selected ${selectedSampleFiles.length} uploaded image(s). Total references: ${totalSelectedReferences()}/${MAX_SAMPLE_IMAGES}.${noteText}`);
        return;
      }

      if (limitReached) {
        refreshSampleHint(`Maximum ${MAX_SAMPLE_IMAGES} reference images allowed. Remove one to add another.`, true);
        return;
      }

      if (tooLarge || badType || duplicates) {
        const detail = notes.length ? ` (${notes.join(", ")})` : "";
        refreshSampleHint(`No new images were added.${detail}`, true);
        return;
      }

      refreshSampleHint();
    });
  }

  if (btnChatHistory) {
    btnChatHistory.addEventListener("click", async () => {
      chatHistoryPanel.classList.toggle("hidden");
      if (!chatHistoryPanel.classList.contains("hidden")) {
        chatSessionsList.innerHTML = '<div style="padding: 10px;">Loading...</div>';
        try {
          const res = await fetch(`${API_BASE_URL}/chat-sessions`);
          if (!res.ok) {
            chatSessionsList.innerHTML = `<div style="padding: 10px;">Error loading sessions (Status: ${res.status}). Ensure API is running.</div>`;
            return;
          }
          const data = await res.json();
          if (data.sessions && data.sessions.length > 0) {
            const validSessions = data.sessions.filter((s) => s.session_id);
            if (validSessions.length > 0) {
              chatSessionsList.innerHTML = validSessions.map((s) => {
                const title = s.title ? s.title : "Session: " + String(s.session_id).substring(0, 8);
                return `<div class="chat-session-item" data-id="${s.session_id}" style="padding: 10px; border-bottom: 1px solid #e5e5e5; cursor: pointer; font-size: 0.9em;">
                  <strong>${esc(title)}</strong><br>
                  <span style="font-size: 0.8em; color: #666;">${new Date(s.last_activity).toLocaleString()}</span>
                </div>`;
              }).join("");

              document.querySelectorAll(".chat-session-item").forEach((item) => {
                item.addEventListener("click", () => {
                  chatSessionId = item.dataset.id;
                  localStorage.setItem("chat_session_id", chatSessionId);
                  chatHistoryPanel.classList.add("hidden");
                  loadChatHistory();
                });
              });
            } else {
              chatSessionsList.innerHTML = '<div style="padding: 10px;">No previous chats found.</div>';
            }
          } else {
            chatSessionsList.innerHTML = '<div style="padding: 10px;">No previous chats found.</div>';
          }
        } catch {
          chatSessionsList.innerHTML = '<div style="padding: 10px;">Error loading sessions.</div>';
        }
      }
    });
  }

  if (btnChatNew) {
    btnChatNew.addEventListener("click", () => {
      chatSessionId = null;
      localStorage.removeItem("chat_session_id");
      chatContext.history = [];
      chatBody.innerHTML = `
        <div class="chat-row">
          <div class="chat-avatar">AI</div>
          <div class="chat-bubble">
            Hi! I am the Creative Director Assistant. I can help with hooks, angles, copy, concepts, reels scripting, and campaign strategy.
            <div class="meta">Assistant</div>
          </div>
          <div class="chat-time">Just now</div>
        </div>
      `;
      if (chatHistoryPanel) chatHistoryPanel.classList.add("hidden");
    });
  }

  if (btnSidebarChat && chatPanel) {
    btnSidebarChat.addEventListener("click", () => {
      chatPanel.classList.remove("hidden");
    });
  }

  if (btnKnowledgeBase) {
    btnKnowledgeBase.addEventListener("click", openKbModal);
  }

  if (tabChatbotBtn && tabSuggestionsBtn) {
    tabChatbotBtn.addEventListener("click", () => {
      tabChatbotBtn.classList.add("active");
      tabSuggestionsBtn.classList.remove("active");
      chatbotContentArea.classList.remove("hidden");
      suggestionsContentArea.classList.add("hidden");
    });

    tabSuggestionsBtn.addEventListener("click", () => {
      tabSuggestionsBtn.classList.add("active");
      tabChatbotBtn.classList.remove("active");
      suggestionsContentArea.classList.remove("hidden");
      chatbotContentArea.classList.add("hidden");
      renderSuggestions();
    });
  }

  if (btnChatClose && chatPanel) {
    btnChatClose.addEventListener("click", () => {
      chatPanel.classList.add("hidden");
    });
  }
}

function renderSuggestions() {
  const container = byId("suggestions-list");
  if (!container) return;

  if (!currentSuggestions || currentSuggestions.length === 0) {
    container.innerHTML = `
      <div class="card" style="border: 1px dashed var(--line); text-align: center; padding: 20px; background: #18181b;">
        <p style="margin: 0; color: var(--muted);">No more unused concepts available for suggestions.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = currentSuggestions.map((concept, index) => {
    // Generate a simple expected impact based on angle and mood
    const expectedImpact = `By leveraging the "${concept.angle_name}" angle with a ${concept.mood} mood, this creative is designed to resonate strongly with the target audience and drive high engagement.`;
    
    return `
      <div class="suggestion-card" id="sug-${index}">
        <span class="suggestion-category category-visual_concept">Unused Concept</span>
        <h4 class="suggestion-title-text">${esc(concept.hook_text)}</h4>
        
        <div class="suggestion-actions" style="display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; margin-bottom: 12px;">
          <button class="suggestion-btn-outline" onclick="toggleSuggestionDetail('logic-${index}')" type="button">Detailed Logic</button>
          <button class="suggestion-btn-outline" onclick="toggleSuggestionDetail('impact-${index}')" type="button">Expected Impact</button>
          <div style="flex-grow: 1;"></div>
          <button class="suggestion-btn-outline" onclick="ignoreSuggestion(${index})" type="button">Ignore</button>
          <button class="suggestion-btn" onclick="executeSuggestion(${index})" type="button">Execute</button>
        </div>

        <div id="logic-${index}" class="suggestion-detail hidden" style="padding: 10px; background: rgba(0,0,0,0.2); border-radius: 4px; font-size: 0.85em; margin-bottom: 8px;">
          <strong>Angle:</strong> ${esc(concept.angle_name)}<br>
          <strong>Scene:</strong> ${esc(concept.scene_description)}<br>
          <strong>Style:</strong> ${esc(concept.style_reference)}<br>
          <strong>Colors:</strong> ${esc((concept.color_palette || []).join(", "))}
        </div>

        <div id="impact-${index}" class="suggestion-detail hidden" style="padding: 10px; background: rgba(0,0,0,0.2); border-radius: 4px; font-size: 0.85em; margin-bottom: 8px;">
          ${esc(expectedImpact)}
        </div>
      </div>
    `;
  }).join("");
}
window.renderSuggestions = renderSuggestions;

function toggleSuggestionDetail(id) {
  const el = document.getElementById(id);
  if (el) el.classList.toggle("hidden");
}
window.toggleSuggestionDetail = toggleSuggestionDetail;

function ignoreSuggestion(index) {
  if (!currentSuggestions || index >= currentSuggestions.length) return;
  const item = currentSuggestions.splice(index, 1)[0];
  currentSuggestions.push(item);
  renderSuggestions();
}
window.ignoreSuggestion = ignoreSuggestion;

async function executeSuggestion(index) {
  if (!currentSuggestions || index >= currentSuggestions.length) return;
  const concept = currentSuggestions[index];
  
  // Remove from suggestions and re-render
  currentSuggestions.splice(index, 1);
  renderSuggestions();

  // Add chat message
  appendChat("ai", `Executing suggested concept: <strong>${esc(concept.hook_text)}</strong>...`, true);
  setStatus("Generating suggested image...");
  
  try {
    const imageReq = {
      payload: currentPayload,
      concept: concept
    };

    const imageResponse = await fetch(`${API_BASE_URL}/generate-image`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(imageReq)
    });
    
    const imageData = await imageResponse.json();
    if (!imageResponse.ok) throw new Error("Failed to generate image");

    // Add directly to the output without scoring for simplicity, or we could run scoring if needed.
    // For this implementation, we will append it as a rendered ad.
    if (imageData.image_urls && imageData.image_urls.length > 0) {
      const tempCard = document.createElement("div");
      tempCard.className = "card card-creative";
      tempCard.innerHTML = `
         <div class="card-status-bar" style="background-color: #27ae60; color: white;">Suggested Creative</div>
         <div class="creative-image-container">
             <img src="${toPublicAssetUrl(imageData.image_urls[0])}" class="creative-image" alt="Generated">
         </div>
         <div class="creative-content">
             <h3 class="creative-headline" style="color: #fff;">${esc(concept.angle_name)}</h3>
             <p class="creative-text">${esc(concept.hook_text)}</p>
         </div>
      `;
      finalsOutput.appendChild(tempCard);
      
      const currentCount = parseInt(byId("finals-count").textContent || "0");
      setCount("finals", currentCount + 1);
      
      appendChat("ai", "Suggested image generation complete! Check the <strong>Final Ads</strong> tab.", true);
      setStatus("Ready.");
    }
  } catch (error) {
    console.error("Execute suggestion error:", error);
    setStatus("Failed to execute suggestion.", true);
    appendChat("ai", "Sorry, an error occurred while generating the suggested image.");
  }
}
window.executeSuggestion = executeSuggestion;

resetOutputs();

// Force counts to 5 on load to override any browser caching/autofill
if (byId("f-concepts")) byId("f-concepts").value = "5";
if (byId("f-hooks")) byId("f-hooks").value = "5";
if (byId("f-copy")) byId("f-copy").value = "5";

wireEvents();
loadUiConfig();
loadChatHistory();
showSupervisor();

// Sidebar toggle logic
const btnChatOpen = byId("btn-chat-open");
const appShell = document.querySelector(".app-shell");

if (btnChatClose && btnChatOpen && appShell) {
  btnChatClose.addEventListener("click", () => {
    appShell.classList.add("assistant-closed");
    btnChatOpen.classList.remove("hidden");
  });

  btnChatOpen.addEventListener("click", () => {
    appShell.classList.remove("assistant-closed");
    btnChatOpen.classList.add("hidden");
  });
}

// Knowledge Base upload handler
const kbUploadInput = document.getElementById("kb-upload-input");
if (kbUploadInput) {
  kbUploadInput.addEventListener("change", async (e) => {
    const files = Array.from(e.target.files);
    if (!files.length) return;
    
    const endpoint = (API_BASE_URL ? API_BASE_URL.replace(/\/+$/,'') : '') + '/knowledge-base/images';
    let hasError = false;

    for (const file of files) {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("title", file.name);
      formData.append("tags", activeKbTab === "asset" ? "asset" : "upload");
      
      try {
        const res = await fetch(endpoint, {
          method: "POST",
          body: formData
        });
        if (!res.ok) throw new Error("Upload failed for " + file.name);
      } catch (err) {
        console.error("Upload error", err);
        hasError = true;
      }
    }

    if (hasError) {
      alert("Failed to upload some or all images.");
    }
    
    // Clear input and refresh grid
    kbUploadInput.value = "";
    fetchKnowledgeBaseImages();
  });
}



// ----------------------------------------------------------------------
// NEW REELS SCRIPT DIRECTOR LOGIC
// ----------------------------------------------------------------------

function switchReelsDirectorTab(tabName) {
  // Update Tab Buttons
  document.querySelectorAll(".reels-director-tabs .tab-btn").forEach(btn => {
    if (btn.dataset.reelsTab === tabName) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });

  // Update Views
  const views = ["analyze", "trends", "generate"];
  views.forEach(v => {
    const el = document.getElementById("reels-tab-" + v);
    if (el) {
      if (v === tabName) {
        el.classList.remove("hidden");
      } else {
        el.classList.add("hidden");
      }
    }
  });

  // If opening trends tab for the first time, load defaults
  if (tabName === "trends") {
    generateDummyTrends();
  }
}

// 5MB Upload Limit Helper
function setupVideoUploadLimit(inputId, nameId) {
  const input = document.getElementById(inputId);
  const nameDisplay = document.getElementById(nameId);
  if (input) {
    input.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (file) {
        if (file.size > 5 * 1024 * 1024) {
          nameDisplay.textContent = "Error: File exceeds 5MB limit. Please upload a smaller video.";
          nameDisplay.style.color = "#ef4444";
          input.value = ""; // Clear
        } else {
          nameDisplay.textContent = "Selected: " + file.name;
          nameDisplay.style.color = "#10b981"; // Green
        }
      } else {
        nameDisplay.textContent = "";
      }
    });
  }
}

// Setup limiters on DOM load (or immediately if appended at end)
setupVideoUploadLimit("reels-analyze-file", "reels-analyze-file-name");
setupVideoUploadLimit("reels-gen-ref-file", "reels-gen-ref-file-name");

function runReelsAnalyze() {
  const btn = document.getElementById("btn-reels-analyze");
  btn.textContent = "Analyzing...";
  btn.disabled = true;
  
  // Simulate network delay
  setTimeout(() => {
    document.getElementById("reels-analyze-output").classList.remove("hidden");
    btn.textContent = "Analyze Reel";
    btn.disabled = false;
  }, 1500);
}

function runReelsGenerate() {
  const btn = document.getElementById("btn-reels-generate");
  const ctx = document.getElementById("reels-gen-context").value || "Generic trending topic";
  const duration = document.getElementById("reels-gen-duration").value;
  const toneSelect = document.getElementById("reels-gen-style");
  const tone = toneSelect ? toneSelect.options[toneSelect.selectedIndex].text : "Professional";
  
  btn.textContent = "Generating...";
  btn.disabled = true;
  
  // Simulate network delay
  setTimeout(() => {
    document.getElementById("reels-generate-output").classList.remove("hidden");
    document.getElementById("reels-out-title").textContent = "Generated Script (" + duration + ") - Tone: " + tone;
    
    let hookText = "'Stop scrolling! You are doing " + ctx + " completely wrong.'";
    let body1Text = "'Most people think the secret is grinding harder, but actually...'";
    let body2Text = "'...the real secret is leveraging this exact system I\\'ve been using for 5 years.'";
    let ctaText = "'Comment \"SYSTEM\" below and I will DM you the exact blueprint.'";
    
    if (tone === "Friendly") {
      hookText = "'Hey there! Are you struggling with " + ctx + "? Let\\'s fix that together.'";
      body1Text = "'It\\'s super common to feel stuck, but the truth is actually quite simple...'";
      body2Text = "'...I found this amazing approach that saved me hours of frustration, and I want to share it.'";
      ctaText = "'Drop a comment with \"INFO\" and I\\'ll send the guide straight to your inbox!'";
    } else if (tone === "Bold / Disruptive") {
      hookText = "'Everything you\\'ve been told about " + ctx + " is a complete lie.'";
      body1Text = "'The gurus are keeping you stuck in the old way to protect their own profits...'";
      body2Text = "'...but today I\\'m breaking down the raw strategy that actually works in 2026.'";
      ctaText = "'Comment \"REBEL\" below and I will DM you the uncensored playbook immediately.'";
    } else if (tone === "Inspirational / Story-driven") {
      hookText = "'I was ready to quit " + ctx + " until I discovered this one truth.'";
      body1Text = "'For months, I got zero traction and felt like I was shouting into a void...'";
      body2Text = "'...then I pivoted my entire framework, and everything shifted overnight.'";
      ctaText = "'If you\\'re ready to make a shift, comment \"INSPIRE\" and let\\'s get started.'";
    } else if (tone === "Urgent / Scarcity-driven") {
      hookText = "'If you don\\'t fix your " + ctx + " in the next 24 hours, you\\'re going to lose out.'";
      body1Text = "'The market is shifting rapidly, and late adopters are getting left behind...'";
      body2Text = "'...this is the exact system that successful creators are scaling right now.'";
      ctaText = "'Comment \"NOW\" to get instant access before the blueprint goes offline.'";
    } else if (tone === "Conversational / Casual") {
      hookText = "'So, let\\'s talk about " + ctx + " for a second.'";
      body1Text = "'Honestly, it\\'s not as complicated as everyone makes it out to be...'";
      body2Text = "'...here is the simple process I use every single day to get results.'";
      ctaText = "'Shoot me a DM or comment \"CHAT\" and let\\'s talk about how to apply it.'";
    } else if (tone === "Direct / Promotional") {
      hookText = "'Here is the fastest way to scale your " + ctx + " starting today.'";
      body1Text = "'We built a battle-tested framework specifically designed to solve this exact bottleneck...'";
      body2Text = "'...delivering predictable, high-converting results with minimal overhead.'";
      ctaText = "'Click the link in bio or comment \"SCALE\" to download the framework now.'";
    } else if (tone === "Informative / Educational") {
      hookText = "'Here is the step-by-step breakdown of how " + ctx + " actually works.'";
      body1Text = "'Let\\'s first dissect the core components and variables driving the system...'";
      body2Text = "'...by analyzing the input/output ratios, we can optimize the workflow for maximum output.'";
      ctaText = "'Save this post for later and comment \"GUIDE\" for the full technical documentation.'";
    }
    
    document.getElementById("reels-out-script").textContent = 
      "Title: 3 SECRETS to Mastering " + ctx + "\n" +
      "Tone: " + tone + "\n\n" +
      "[0:00 - 0:03] HOOK: Visual: Fast zoom in on face. Audio: " + hookText + "\n\n" +
      "[0:03 - 0:10] BODY 1: Visual: B-Roll showing frustration. Audio: " + body1Text + "\n\n" +
      "[0:10 - 0:20] BODY 2: Visual: Screen recording or chart. Audio: " + body2Text + "\n\n" +
      "[0:20 - 0:25] CTA: Visual: Pointing to comments. Audio: " + ctaText + "\n\n" +
      "Hashtags: #" + ctx.toLowerCase().replace(/[^a-z0-9]/g, "") + " #viral #strategy";
    
    btn.textContent = "Generate Script";
    btn.disabled = false;
  }, 2000);
}

function generateDummyTrends() {
  const category = document.getElementById("reels-trends-category").value;
  const grid = document.getElementById("reels-trends-grid");
  const hash = document.getElementById("reels-trends-hashtags");
  const audio = document.getElementById("reels-trends-audio");
  
  if (!grid) return;
  
  // Mock Data
  const thumbnails = [
    "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=300&q=80",
    "https://images.unsplash.com/photo-1516259762381-22954d7d3ad2?w=300&q=80",
    "https://images.unsplash.com/photo-1542204165-65bf26472b9b?w=300&q=80",
    "https://images.unsplash.com/photo-1550745165-9bc0b252726f?w=300&q=80",
    "https://images.unsplash.com/photo-1533227260828-53134ce46eba?w=300&q=80"
  ];
  
  let html = "";
  for(let i=0; i<5; i++) {
    const views = Math.floor(Math.random() * 500) + 10;
    const likes = Math.floor(views * 0.1);
    const shares = Math.floor(views * 0.05);
    html += `
      <div class="card" style="display: flex; gap: 12px; padding: 12px; background: #111114; align-items: center; cursor: pointer;">
        <img src="${thumbnails[i]}" style="width: 60px; height: 100px; object-fit: cover; border-radius: 6px; flex-shrink: 0;" alt="Reel">
        <div>
          <h4 style="margin: 0 0 4px 0; color: #fff;">Viral Pattern #${i+1}</h4>
          <p style="margin: 0 0 8px 0; font-size: 0.85rem; color: #a1a1aa;">Excellent retention in first 3s.</p>
          <div style="display: flex; gap: 12px; font-size: 0.8rem; color: #71717a;">
            <span>👁 ${views}K</span>
            <span>❤ ${likes}K</span>
            <span>↗ ${shares}K</span>
          </div>
        </div>
      </div>
    `;
  }
  grid.innerHTML = html;
  
  hash.innerHTML = `
    <span class="top-pill">#${category}</span>
    <span class="top-pill">#${category}tips</span>
    <span class="top-pill">#viral</span>
    <span class="top-pill">#trending</span>
    <span class="top-pill">#growth</span>
  `;
  
  audio.innerHTML = `
    1. "${category.toUpperCase()} Motivation Type Beat" - 2.5M Uses ⬆<br><br>
    2. "Trending Voiceover #42" - 1.1M Uses ⬆<br><br>
    3. "Chill Vibes 2024" - 800K Uses ➖
  `;
}

// Expose functions globally for inline HTML click handlers
window.showDashboard = showDashboard;
window.switchReelsDirectorTab = switchReelsDirectorTab;
window.runReelsAnalyze = runReelsAnalyze;
window.generateDummyTrends = generateDummyTrends;
window.runReelsGenerate = runReelsGenerate;
window.closeImageModal = closeImageModal;
window.closeKbModal = closeKbModal;
window.switchKbTab = switchKbTab;
window.openKbModal = openKbModal;
window.openImageModal = openImageModal;
window.deleteKbImage = deleteKbImage;
window.useKnowledgeImage = useKnowledgeImage;
window.toggleCampaign = toggleCampaign;
window.removeUploadedSample = removeUploadedSample;
window.removeKnowledgeImage = removeKnowledgeImage;
window.selectKBItem = selectKBItem;
