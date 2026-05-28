
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
  const urlInput = document.getElementById("reels-analyze-url");
  const fileInput = document.getElementById("reels-analyze-file");
  const subjectDisplay = document.getElementById("reels-analyze-subject");

  btn.textContent = "Analyzing...";
  btn.disabled = true;
  
  // Clear output visibility during analysis
  document.getElementById("reels-analyze-output").classList.add("hidden");
  
  // Simulate network delay
  setTimeout(() => {
    let subjectText = "Instagram Reel breakdown successfully generated.";
    const url = urlInput ? urlInput.value.trim() : "";
    const file = (fileInput && fileInput.files && fileInput.files[0]) ? fileInput.files[0].name : "";

    if (url) {
      subjectText = `Breakdown generated for URL: <a href="${url}" target="_blank" style="color: #ffffff; text-decoration: underline; font-weight: 600;">${url.substring(0, 45)}${url.length > 45 ? '...' : ''}</a>`;
    } else if (file) {
      subjectText = `Breakdown generated for uploaded file: <strong style="color: #ffffff; font-weight: 600;">${file}</strong>`;
    } else {
      subjectText = `Breakdown generated for demo reference reel.`;
    }

    if (subjectDisplay) subjectDisplay.innerHTML = subjectText;

    document.getElementById("reels-analyze-output").classList.remove("hidden");
    btn.textContent = "Analyze Reel";
    btn.disabled = false;
  }, 1500);
}

function runReelsGenerate() {
  const btn = document.getElementById("btn-reels-generate");
  const ctx = document.getElementById("reels-gen-context").value || "Generic trending topic";
  const duration = document.getElementById("reels-gen-duration").value;
  
  btn.textContent = "Generating...";
  btn.disabled = true;
  
  // Simulate network delay
  setTimeout(() => {
    document.getElementById("reels-generate-output").classList.remove("hidden");
    document.getElementById("reels-out-title").textContent = "Generated Script (" + duration + ")";
    document.getElementById("reels-out-script").textContent = 
      "Title: 3 SECRETS to Mastering " + ctx + "\n\n" +
      "[0:00 - 0:03] HOOK: Visual: Fast zoom in on face. Audio: 'Stop scrolling! You are doing " + ctx + " completely wrong.'\n\n" +
      "[0:03 - 0:10] BODY 1: Visual: B-Roll showing frustration. Audio: 'Most people think the secret is grinding harder, but actually...'\n\n" +
      "[0:10 - 0:20] BODY 2: Visual: Screen recording or chart. Audio: '...the real secret is leveraging this exact system I\\'ve been using for 5 years.'\n\n" +
      "[0:20 - 0:25] CTA: Visual: Pointing to comments. Audio: 'Comment \"SYSTEM\" below and I will DM you the exact blueprint.'\n\n" +
      "Hashtags: #viral #growth #strategy";
    
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
