import re

with open('frontend/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

start_marker = '<section id="tab-reels" class="output-tab hidden">'
end_marker = '</section>\n          <section id="tab-exports" class="output-tab hidden">'

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx != -1 and end_idx != -1:
    new_reels = '''<section id="tab-reels" class="output-tab hidden">
            <div class="section-title">Reels Script Director</div>
            
            <div class="kb-tabs reels-director-tabs" style="display: flex; gap: 10px; margin-bottom: 24px; border-bottom: 1px solid var(--line, #27272a); padding-bottom: 8px;">
              <button class="tab-btn active" data-reels-tab="analyze" onclick="switchReelsDirectorTab('analyze')">Analyze Reels</button>
              <button class="tab-btn" data-reels-tab="trends" onclick="switchReelsDirectorTab('trends')">Discover Trends</button>
              <button class="tab-btn" data-reels-tab="generate" onclick="switchReelsDirectorTab('generate')">Generate your own script</button>
            </div>

            <!-- ANALYZE REELS TAB -->
            <div id="reels-tab-analyze" class="reels-director-view">
              <div class="reels-guided-grid" style="margin-bottom: 16px;">
                <label class="field span-2 reels-hero-field">
                  <span>Paste Reel URL</span>
                  <textarea id="reels-analyze-url" placeholder="Paste an Instagram Reel URL here..."></textarea>
                </label>
                <label class="field span-2 reels-hero-field">
                  <span>Or Upload Reel Video (Max 5MB)</span>
                  <input type="file" id="reels-analyze-file" accept="video/mp4,video/quicktime,video/webm" style="padding: 10px; background: #111114; border: 1px solid #27272a; border-radius: 8px; color: #fff; width: 100%;">
                  <div id="reels-analyze-file-name" style="margin-top: 8px; font-size: 0.85rem; color: #ef4444;"></div>
                </label>
              </div>
              <div class="reels-hero-actions" style="margin-bottom: 24px;">
                <button id="btn-reels-analyze" class="primary-btn" type="button" onclick="runReelsAnalyze()">Analyze Reel</button>
              </div>
              
              <!-- Analyze Output -->
              <div id="reels-analyze-output" class="hidden stack">
                <div class="instagram-ingestion-status" style="margin-bottom: 16px;">
                  <div class="instagram-ingestion-status-row">
                    <strong>Analysis Complete</strong>
                    <span>Visual dashboards & hook breakdowns generated.</span>
                  </div>
                </div>
                <div class="card" style="padding: 16px;">
                  <h3 style="margin-top:0;">Reel Breakdown</h3>
                  <div style="display: flex; gap: 16px; margin-top: 12px; flex-wrap: wrap;">
                    <div style="flex: 1; min-width: 200px; padding: 12px; background: #111114; border-radius: 8px; border: 1px solid #27272a;">
                      <strong>Opening Line (0-2s)</strong>
                      <p style="color: #a1a1aa; font-style: italic; margin: 4px 0 0 0;">"Stop doing this one thing if you want to grow..."</p>
                    </div>
                    <div style="flex: 1; min-width: 200px; padding: 12px; background: #111114; border-radius: 8px; border: 1px solid #27272a;">
                      <strong>Visual Hook</strong>
                      <p style="color: #a1a1aa; margin: 4px 0 0 0;">Fast motion pointing at screen, bold yellow text overlay.</p>
                    </div>
                  </div>
                  <h4 style="margin-top: 16px; margin-bottom: 8px;">Timeline Captions</h4>
                  <ul style="list-style: none; padding: 0; margin: 0; color: #a1a1aa; font-size: 0.9rem;">
                    <li style="margin-bottom: 4px;"><strong style="color: #fff;">0:00</strong> Stop doing this one thing</li>
                    <li style="margin-bottom: 4px;"><strong style="color: #fff;">0:02</strong> If you want to grow on Instagram</li>
                    <li style="margin-bottom: 4px;"><strong style="color: #fff;">0:05</strong> The algorithm completely changed today</li>
                  </ul>
                </div>
              </div>
            </div>

            <!-- DISCOVER TRENDS TAB -->
            <div id="reels-tab-trends" class="reels-director-view hidden">
              <label class="field" style="max-width: 300px; margin-bottom: 24px;">
                <span>Select Category</span>
                <select id="reels-trends-category" onchange="generateDummyTrends()">
                  <option value="fitness">Fitness & Health</option>
                  <option value="saas">SaaS & Tech</option>
                  <option value="ecommerce">E-commerce</option>
                  <option value="realestate">Real Estate</option>
                  <option value="fashion">Fashion & Style</option>
                  <option value="travel">Travel</option>
                  <option value="finance">Finance & Crypto</option>
                  <option value="education">Education & Coaching</option>
                  <option value="entertainment">Entertainment</option>
                  <option value="food">Food & Cooking</option>
                </select>
              </label>
              
              <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 24px;">
                <div>
                  <h3 style="margin-top: 0; margin-bottom: 12px;">Top Trending Reels</h3>
                  <div id="reels-trends-grid" style="display: flex; flex-direction: column; gap: 12px;">
                    <!-- Populated by JS -->
                  </div>
                </div>
                <div>
                  <div class="card" style="padding: 16px; background: #111114;">
                    <h3 style="margin-top: 0; margin-bottom: 12px;">Trending Hashtags</h3>
                    <div id="reels-trends-hashtags" style="display: flex; flex-wrap: wrap; gap: 8px;">
                      <!-- Populated by JS -->
                    </div>
                    <h3 style="margin-top: 24px; margin-bottom: 12px;">Trending Audio</h3>
                    <div id="reels-trends-audio" style="color: #a1a1aa; font-size: 0.9rem;">
                      <!-- Populated by JS -->
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- GENERATE SCRIPT TAB -->
            <div id="reels-tab-generate" class="reels-director-view hidden">
              <div class="reels-guided-grid" style="margin-bottom: 16px;">
                <label class="field">
                  <span>Reel Duration</span>
                  <select id="reels-gen-duration">
                    <option value="15s">15 seconds (Short & Punchy)</option>
                    <option value="30s" selected>30 seconds (Standard)</option>
                    <option value="60s">60 seconds (Deep Dive)</option>
                  </select>
                </label>
                <label class="field">
                  <span>Style / Tone</span>
                  <select id="reels-gen-style">
                    <option value="educational">Educational / Value</option>
                    <option value="humorous">Humorous / Skit</option>
                    <option value="contrarian">Contrarian / Hot Take</option>
                    <option value="storytelling">Storytelling / Vlog</option>
                    <option value="promotional">Direct Promo / CTA</option>
                  </select>
                </label>
                <label class="field span-2">
                  <span>Script Context & Information</span>
                  <textarea id="reels-gen-context" placeholder="What is this reel about? E.g., Explain why cold email is dead and inbound marketing is the future."></textarea>
                </label>
              </div>

              <div class="card" style="padding: 16px; background: #111114; border: 1px solid #27272a; margin-bottom: 24px;">
                <h3 style="margin-top: 0; margin-bottom: 12px;">Reference Material (Optional)</h3>
                <div class="reels-guided-grid">
                  <label class="field span-2">
                    <span>Paste Reference Reel URL</span>
                    <input type="text" id="reels-gen-ref-url" placeholder="https://instagram.com/reel/..." style="width: 100%; padding: 10px; background: #18181b; border: 1px solid #27272a; border-radius: 8px; color: #fff;">
                  </label>
                  <label class="field span-2">
                    <span>Or Upload Reference Video (Max 5MB)</span>
                    <input type="file" id="reels-gen-ref-file" accept="video/mp4,video/quicktime,video/webm" style="padding: 10px; background: #111114; border: 1px solid #27272a; border-radius: 8px; color: #fff; width: 100%;">
                    <div id="reels-gen-ref-file-name" style="margin-top: 8px; font-size: 0.85rem; color: #ef4444;"></div>
                  </label>
                </div>
              </div>

              <div class="reels-hero-actions" style="margin-bottom: 24px;">
                <button id="btn-reels-generate" class="primary-btn" type="button" onclick="runReelsGenerate()">Generate Script</button>
              </div>
              
              <!-- Generate Output -->
              <div id="reels-generate-output" class="hidden stack">
                <div class="instagram-ingestion-status" style="margin-bottom: 16px;">
                  <div class="instagram-ingestion-status-row">
                    <strong>Script Generated successfully</strong>
                    <span>Ready for production.</span>
                  </div>
                </div>
                <div class="card" style="padding: 20px;">
                  <h2 id="reels-out-title" style="margin-top: 0; margin-bottom: 16px;"></h2>
                  <div id="reels-out-script" style="white-space: pre-wrap; font-family: monospace; color: #d4d4d8; font-size: 0.95rem; line-height: 1.6;"></div>
                </div>
              </div>
            </div>

'''
    
    new_content = content[:start_idx] + new_reels + content[end_idx:]
    with open('frontend/index.html', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("SUCCESS")
else:
    print("FAILED TO FIND MARKERS")
