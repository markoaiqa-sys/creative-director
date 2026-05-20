let API_BASE_URL = (
  window.__APP_CONFIG__ &&
  typeof window.__APP_CONFIG__.BACKEND_URL === "string" &&
  window.__APP_CONFIG__.BACKEND_URL.trim()
)
  ? window.__APP_CONFIG__.BACKEND_URL.trim().replace(/\/+$/, "")
  : "";

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

const MAX_SAMPLE_IMAGES = 3;
const MAX_SAMPLE_IMAGE_SIZE_BYTES = 5 * 1024 * 1024;

const countTargets = {
  finals: [byId("finals-count"), byId("finals-count-large")],
  previews: [byId("previews-count"), byId("previews-count-large")],
  hooks: [byId("hooks-count"), byId("hooks-count-large")],
  angles: [byId("angles-count"), byId("angles-count-large")],
  copy: [byId("copy-count"), byId("copy-count-large")],
  concepts: [byId("concepts-count"), byId("concepts-count-large")],
  exports: [byId("exports-count"), byId("exports-count-large")]
};

let chatContext = {};
let chatSessionId = localStorage.getItem("chat_session_id");
let selectedKnowledgeImages = [];
let selectedSampleFiles = [];

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
  heroCard.classList.add("hidden");
  loadingPanel.classList.add("hidden");
  resultsPanel.classList.add("hidden");
  if (historyPanel) historyPanel.classList.add("hidden");

  if (supervisorNav) supervisorNav.classList.add("active");
  if (dashboardNav) dashboardNav.classList.remove("active");
  document.querySelectorAll(".specialist").forEach((n) => n.classList.remove("active"));
  if (navExecutionHistory) navExecutionHistory.classList.remove("active");
}

function showDashboard() {
  if (supervisorPanel) supervisorPanel.classList.add("hidden");
  if (supervisorNav) supervisorNav.classList.remove("active");
  heroCard.classList.remove("hidden");
  loadingPanel.classList.add("hidden");
  // Only hide results if we haven't generated anything yet
  if (!chatContext.campaign) {
    resultsPanel.classList.add("hidden");
  } else {
    resultsPanel.classList.remove("hidden");
  }
  if (historyPanel) historyPanel.classList.add("hidden");
  dashboardNav.classList.add("active");
  document.querySelectorAll(".specialist").forEach((n) => n.classList.remove("active"));
  if (navExecutionHistory) navExecutionHistory.classList.remove("active");
}

function showLoading() {
  if (supervisorPanel) supervisorPanel.classList.add("hidden");
  heroCard.classList.add("hidden");
  loadingPanel.classList.remove("hidden");
  resultsPanel.classList.add("hidden");
  if (historyPanel) historyPanel.classList.add("hidden");
}

function showResults() {
  if (supervisorPanel) supervisorPanel.classList.add("hidden");
  heroCard.classList.add("hidden");
  loadingPanel.classList.add("hidden");
  resultsPanel.classList.remove("hidden");
  if (historyPanel) historyPanel.classList.add("hidden");
}

function showHistory() {
  if (supervisorPanel) supervisorPanel.classList.add("hidden");
  if (supervisorNav) supervisorNav.classList.remove("active");
  heroCard.classList.add("hidden");
  loadingPanel.classList.add("hidden");
  resultsPanel.classList.add("hidden");
  if (historyPanel) historyPanel.classList.remove("hidden");

  dashboardNav.classList.remove("active");
  document.querySelectorAll(".specialist").forEach((n) => n.classList.remove("active"));
  if (navExecutionHistory) navExecutionHistory.classList.add("active");
}

function setCount(key, value) {
  (countTargets[key] || []).forEach((n) => {
    if (n) n.textContent = String(value);
  });
}

function empty(target, msg) {
  target.innerHTML = `<div class="card"><p>${esc(msg)}</p></div>`;
}

function resetOutputs() {
  empty(finalsOutput, "Rendered ad creatives will appear here after generation.");
  empty(previewsOutput, "Platform previews will appear here after generation.");
  empty(hooksOutput, "Hooks will appear here after generation.");
  empty(anglesOutput, "Angles will appear here after generation.");
  empty(copyOutput, "Ad copy will appear here after generation.");
  empty(conceptsOutput, "Generated concepts will appear here after generation.");
  empty(exportsOutput, "Export rows will appear here after generation.");
  Object.keys(countTargets).forEach((key) => setCount(key, 0));
}

function activateTab(tab) {
  if (supervisorPanel) supervisorPanel.classList.add("hidden");
  if (supervisorNav) supervisorNav.classList.remove("active");
  document.querySelectorAll(".tab").forEach((n) => n.classList.toggle("active", n.dataset.tab === tab));
  ["finals", "previews", "hooks", "angles", "copy", "concepts", "exports"].forEach((name) => {
    byId(`tab-${name}`).classList.toggle("hidden", tab !== name);
  });
  document.querySelectorAll(".specialist").forEach((n) => n.classList.toggle("active", n.dataset.agentTab === tab));
  dashboardNav.classList.remove("active");
  resultsTitle.textContent = "Campaign Output";
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

function openKbModal() {
  const modal = document.getElementById("kbModal");
  const grid = document.getElementById("kb-grid");
  if (modal) {
    modal.classList.remove("hidden");
  }
  if (grid) {
    grid.innerHTML = `<div style="padding:12px;color:var(--muted,#666);">Loading...</div>`;
  }
  fetchKnowledgeBaseImages();
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
    const items = data?.items || [];
    renderKbGrid(items);
  } catch (e) {
    const grid = document.getElementById("kb-grid");
    if (grid) grid.innerHTML = `<div class="card"><p>Error loading images.</p></div>`;
    console.error("KB fetch error", e);
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
      <div class="card" style="text-align:center;padding:8px;">
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

function appendChat(role, text) {
  const row = document.createElement("div");
  row.className = "chat-row" + (role === "user" ? " user" : "");
  row.innerHTML = `<div class="chat-avatar">${role === "user" ? "You" : "AI"}</div><div class="chat-bubble">${text}<div class="meta">${role === "user" ? "You" : "Assistant"}</div></div>`;
  chatBody.appendChild(row);
  chatBody.scrollTop = chatBody.scrollHeight;
}

async function sendChatMessage() {
  const message = chatInput.value.trim();
  if (!message) return;
  appendChat("user", esc(message));
  chatInput.value = "";
  chatSend.disabled = true;

  try {
    const res = await fetch(`${API_BASE_URL}/chat-assistant`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, context: chatContext, session_id: chatSessionId })
    });
    if (!res.ok) {
      throw new Error(await parseErrorResponse(res));
    }
    const data = await res.json();
    appendChat("ai", esc(data.reply || "No response received."));
    chatContext = data.context || chatContext;
    if (data.session_id && data.session_id !== chatSessionId) {
      chatSessionId = data.session_id;
      localStorage.setItem("chat_session_id", chatSessionId);
    }
  } catch (error) {
    appendChat("ai", esc(error.message || "Sorry, there was an error contacting the assistant."));
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

  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => activateTab(tab.dataset.tab));
  });

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
                ${primaryImageUrl ? `<img src="${primaryImageUrl}" class="campaign-thumbnail" alt="Campaign preview">` : ""}
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
        // If user uploaded sample files, save them to knowledge base first
        if (selectedSampleFiles.length) {
          const files = selectedSampleFiles.slice(0, MAX_SAMPLE_IMAGES);
          for (const f of files) {
            try {
              const fd = new FormData();
              fd.append("file", f, f.name);
              fd.append("title", `${byId("f-brand").value || "sample"} - ${f.name}`);
              await fetch(`${API_BASE_URL}/knowledge-base/images`, { method: "POST", body: fd });
            } catch (e) {
              console.warn("KB upload failed", e);
            }
          }
        }

        const response = await fetch(`${API_BASE_URL}/generate-creatives`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || data));
      renderAll(data);
      // Keep status focused on user outcome instead of provider diagnostics.
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
            Hi! I am the Creative Director Assistant. I can help with hooks, angles, copy, concepts, and campaign strategy.
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
      fetchAndRenderSuggestions();
    });
  }

  if (btnChatClose && chatPanel) {
    btnChatClose.addEventListener("click", () => {
      chatPanel.classList.add("hidden");
    });
  }
}

async function fetchAndRenderSuggestions() {
  const container = byId("suggestions-list");
  if (!container) return;

  if (!chatContext || !chatContext.campaign) {
    container.innerHTML = `
      <div class="card" style="border: 1px dashed var(--line); text-align: center; padding: 20px; background: #18181b;">
        <p style="margin: 0; color: var(--muted);">No campaign generated yet. Suggestions will appear here once you generate a campaign.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = '<div style="padding: 10px; color: var(--muted); text-align: center;">Loading suggestions...</div>';

  try {
    const res = await fetch(`${API_BASE_URL}/suggestions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ campaign: chatContext.campaign })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const suggestions = data.suggestions || [];
    if (suggestions.length === 0) {
      container.innerHTML = `
        <div class="card" style="border: 1px dashed var(--line); text-align: center; padding: 20px; background: #18181b;">
          <p style="margin: 0; color: var(--muted);">No suggestions available for the current campaign.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = suggestions.map((s) => {
      const categoryLabel = String(s.category || "").replaceAll('_', ' ');
      return `
        <div class="suggestion-card" id="sug-${s.id}">
          <span class="suggestion-category category-${s.category}">${esc(categoryLabel)}</span>
          <h4 class="suggestion-title-text">${esc(s.title)}</h4>
          <p class="suggestion-desc-text">${esc(s.description)}</p>
          <button class="suggestion-btn" onclick="executeSuggestion('${esc(s.id)}')" type="button">Execute</button>
        </div>
      `;
    }).join("");

    window.currentSuggestions = suggestions;
  } catch (error) {
    console.error("Suggestions fetch error:", error);
    container.innerHTML = `
      <div class="card" style="border: 1px dashed var(--line); text-align: center; padding: 20px; background: #18181b;">
        <p style="margin: 0; color: #ff6b6b;">Error loading suggestions. Please ensure the API is running.</p>
      </div>
    `;
  }
}
window.fetchAndRenderSuggestions = fetchAndRenderSuggestions;

async function executeSuggestion(id) {
  const suggestion = window.currentSuggestions?.find(s => s.id === id);
  if (!suggestion) return;

  const btn = document.querySelector(`#sug-${id} .suggestion-btn`);
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Executing...";
  }

  try {
    const res = await fetch(`${API_BASE_URL}/execute-suggestion`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ suggestion, campaign: chatContext.campaign })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    
    setStatus(data.message || "Suggestion executed successfully!", false);
    await fetchAndRenderSuggestions();
  } catch (error) {
    console.error("Execute suggestion error:", error);
    setStatus("Failed to execute suggestion.", true);
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Execute";
    }
  }
}
window.executeSuggestion = executeSuggestion;

resetOutputs();
wireEvents();
loadUiConfig();
loadChatHistory();
showSupervisor();
