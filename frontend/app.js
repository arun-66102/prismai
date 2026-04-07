/* ═══════════════════════════════════════════════════════════════════════
   Prism AI — Frontend Logic
   Tab switching, API calls, result rendering, copy/download
   ═══════════════════════════════════════════════════════════════════════ */

const API_BASE = window.location.origin;

// ─── DOM References ─────────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const overlay = $("#loading-overlay");
const toastBox = $("#toast-container");
const authStatusBox = $("#auth-status-container");

// Auth State
let currentUser = null;
let currentUsage = null;
let accessToken = localStorage.getItem("prism_access_token");
let refreshToken = localStorage.getItem("prism_refresh_token");

// ─── Utilities ──────────────────────────────────────────────────────────
function showLoading(msg = "Loading...") { 
    const textEl = document.querySelector(".loader-text");
    if (textEl) textEl.textContent = msg;
    overlay.classList.remove("hidden"); 
}
function hideLoading() { overlay.classList.add("hidden"); }

function toast(message, type = "info") {
    const el = document.createElement("div");
    el.className = `toast ${type}`;
    el.textContent = message;
    toastBox.appendChild(el);
    setTimeout(() => el.remove(), 3200);
}

function downloadText(content, filename) {
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
}

function downloadImage(url, filename) {
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
}

async function copyText(text) {
    try {
        await navigator.clipboard.writeText(text);
        toast("Copied to clipboard!", "success");
    } catch {
        toast("Copy failed — try manually.", "error");
    }
}

async function shareContent(data) {
    if (navigator.share) {
        try {
            await navigator.share(data);
            toast("Shared successfully!", "success");
        } catch (err) {
            if (err.name !== "AbortError") {
                toast("Could not share.", "error");
            }
        }
    } else {
        toast("Web Share fallback: please copy the text.", "info");
    }
}

async function translateResult(text, targetLang) {
    showLoading(`Translating to ${targetLang}...`);
    try {
        const data = await apiPost("/translate", { text, target_language: targetLang });
        return data.translated_text;
    } catch (err) {
        toast(`Translation failed: ${err.message}`, "error");
        return null;
    } finally {
        hideLoading();
    }
}

// ─── Theme Initialization ───────────────────────────────────────────────
function updateThemeUI(theme) {
    document.querySelectorAll('.theme-btn').forEach(btn => {
        if (btn.dataset.themeVal === theme) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}

if (window.getPrismTheme) {
    const currentTheme = window.getPrismTheme();
    updateThemeUI(currentTheme);
    
    document.querySelectorAll('.theme-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const newTheme = btn.dataset.themeVal;
            window.setPrismTheme(newTheme);
            updateThemeUI(newTheme);
        });
    });
}

// ─── Health Check ───────────────────────────────────────────────────────
async function checkHealth() {
    try {
        const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(4000) });
        if (!res.ok) throw new Error();
    } catch {
        toast("API Offline — Cannot reach server", "error");
    }
}

// Check immediately
checkHealth();

// ─── Tab Switching ──────────────────────────────────────────────────────
$$(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
        // If not logged in and clicking a generator/history tab, force to login
        if (!currentUser && ["blog", "video", "image"].includes(btn.dataset.tab)) {
            toast("Please login to access this feature", "info");
            switchTab("login");
            return;
        }
        switchTab(btn.dataset.tab);
    });
});

function switchTab(tabId, updateHistory = true) {
    // Hide auth buttons in navbar if switching to them
    const authBtn = $("#nav-login-btn");
    const navbarTabs = $(".navbar-tabs");

    if (authBtn) {
        // Hide login button on auth pages or the landing page itself
        if (tabId === "login" || tabId === "register" || tabId === "landing") authBtn.style.display = "none";
        else if (!currentUser) authBtn.style.display = "block";
    }

    // Hide generator tabs in the navbar if not logged in or on landing/auth panels
    if (navbarTabs) {
        if (tabId === "landing" || tabId === "login" || tabId === "register") {
            navbarTabs.style.display = "none";
        } else {
            navbarTabs.style.display = "flex";
        }
    }

    // Deactivate all
    $$(".tab-btn").forEach((b) => b.classList.remove("active"));
    $$(".tab-panel").forEach((p) => p.classList.remove("active"));
    $("#hero-section").style.display = (tabId === "login" || tabId === "register" || tabId === "landing") ? "none" : "block";

    // Activate selected
    const btn = $(`#tab-${tabId}`);
    if (btn) btn.classList.add("active");
    const panel = $(`#panel-${tabId}`);
    if (panel) panel.classList.add("active");

    if (updateHistory) {
        window.history.pushState({ tabId: tabId }, "", `#${tabId}`);
    }

    // Auto-fetch tool-specific history for sidebars
    if (currentUser && ["blog", "video", "image", "intro"].includes(tabId)) {
        fetchSidebarHistory(tabId);
    }
}

// ─── Range Sliders ──────────────────────────────────────────────────────
$("#blog-words")?.addEventListener("input", (e) => {
    $("#blog-words-val").textContent = e.target.value;
});

$("#video-duration")?.addEventListener("input", (e) => {
    $("#video-duration-val").textContent = `${e.target.value} min`;
});

$("#image-count")?.addEventListener("input", (e) => {
    $("#image-count-val").textContent = e.target.value;
});

// ─── API Call Helper ────────────────────────────────────────────────────
async function apiPost(endpoint, body, isAuthEndpoint = false) {
    const headers = { "Content-Type": "application/json" };

    // Add JWT if it's a protected endpoint
    if (!isAuthEndpoint && accessToken) {
        headers["Authorization"] = `Bearer ${accessToken}`;
    }

    let res = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
    });

    // Handle token expiry (401)
    if (res.status === 401 && !isAuthEndpoint && refreshToken) {
        // Try to refresh
        try {
            const refreshRes = await fetch(`${API_BASE}/auth/login`, { // Actually refresh should use form data or similar, for simplicity let's force re-login if 401
                method: "POST"
            });
            // If refresh fails, clear tokens and redirect to login
            throw new Error("Session expired");
        } catch {
            logout();
            throw new Error("Session expired. Please login again.");
        }
    }

    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `Request failed (${res.status})`);
    }

    return res.json();
}

async function apiGet(endpoint) {
    if (!accessToken) throw new Error("No token");

    const res = await fetch(`${API_BASE}${endpoint}`, {
        headers: { "Authorization": `Bearer ${accessToken}` },
    });

    if (!res.ok) {
        if (res.status === 401) logout();
        throw new Error("Failed to fetch");
    }

    return res.json();
}

// ─── Auth Logic ─────────────────────────────────────────────────────────

// Listeners for auth links
$("#show-register-btn")?.addEventListener("click", () => switchTab("register"));
$("#show-login-btn")?.addEventListener("click", () => switchTab("login"));

// Listeners for landing page CTA
$("#landing-register-btn")?.addEventListener("click", () => switchTab("register"));
$("#landing-login-link")?.addEventListener("click", (e) => { e.preventDefault(); switchTab("login"); });

// Open login from navbar
$("#nav-login-btn")?.addEventListener("click", () => switchTab("login"));

// Handle document clicks to close profile dropdown
document.addEventListener("click", (e) => {
    const profile = $("#user-profile-menu");
    if (profile && !profile.contains(e.target)) {
        profile.classList.remove("open");
    }
});

function updateAuthUI() {
    if (currentUser) {
        // Render Profile Dropdown
        const tierClass = `tier-${currentUser.tier}`;
        const adminLink = currentUser.role === 'admin'
            ? `<a href="/static/admin.html" class="dropdown-item">Admin Dashboard</a>`
            : '';

        authStatusBox.innerHTML = `
            <div class="user-profile" id="user-profile-menu">
                <span class="user-name">${currentUser.name}</span>
                <span class="user-tier ${tierClass}">${currentUser.tier}</span>
                <div class="dropdown-menu">
                    ${adminLink}
                    <button class="dropdown-item" id="nav-logout-btn">
                        <span class="text-danger">Logout</span>
                    </button>
                </div>
            </div>
        `;

        const greetingEl = document.getElementById("intro-greeting");
        if (greetingEl) {
            greetingEl.textContent = `Welcome, ${currentUser.name.split(" ")[0]}!`;
        }

        // Show usage stats
        updateUsageStatsUI();

        // Bind events
        $("#user-profile-menu").addEventListener("click", function () {
            this.classList.toggle("open");
        });

        $("#nav-logout-btn").addEventListener("click", logout);

        // Switch out of auth panels if we are there
        const activePanel = $(".tab-panel.active");
        const activeTab = activePanel ? activePanel.id.replace("panel-", "") : null;
        const hashTab = window.location.hash.substring(1);
        const targetTab = (hashTab && !["login", "register", "landing"].includes(hashTab)) ? hashTab : "intro";

        if (!activeTab || ["login", "register", "landing"].includes(activeTab)) {
            switchTab(targetTab);
        }
    } else {
        // Render Login button
        authStatusBox.innerHTML = `<button class="btn-icon-sm" id="nav-login-btn">Login</button>`;
        $("#nav-login-btn").addEventListener("click", () => switchTab("login"));

        // Clear usage stats
        $$(".usage-stats").forEach(el => el.innerHTML = "");
        const dashStats = $("#dashboard-stats");
        if (dashStats) dashStats.style.display = "none";

        // Read hash to see if they specifically wanted login/register, otherwise landing
        const hashTab = window.location.hash.substring(1);
        if (hashTab === "login" || hashTab === "register") {
            switchTab(hashTab);
        } else {
            switchTab("landing");
        }
    }
}

function updateUsageStatsUI() {
    if (!currentUsage) return;

    const dashStats = $("#dashboard-stats");
    if (dashStats) {
        dashStats.style.display = "flex";
        $("#dash-stat-blogs").textContent = currentUsage.blogs_total || 0;
        $("#dash-stat-videos").textContent = currentUsage.video_scripts_total || 0;
        $("#dash-stat-images").textContent = currentUsage.images_total || 0;
    }

    const blogStats = $("#blog-usage-stats");
    if (blogStats) {
        const remaining = currentUsage.blogs_limit === "inf" ? "Unlimited" : (currentUsage.blogs_limit - currentUsage.blogs_generated);
        blogStats.innerHTML = `Used: ${currentUsage.blogs_generated} / ${currentUsage.blogs_limit === "inf" ? "∞" : currentUsage.blogs_limit}`;
    }

    const videoStats = $("#video-usage-stats");
    if (videoStats) {
        videoStats.innerHTML = `Used: ${currentUsage.video_scripts_generated} / ${currentUsage.video_scripts_limit === "inf" ? "∞" : currentUsage.video_scripts_limit}`;
    }

    const imageStats = $("#image-usage-stats");
    if (imageStats) {
        imageStats.innerHTML = `Used: ${currentUsage.images_generated} / ${currentUsage.images_limit === "inf" ? "∞" : currentUsage.images_limit}`;
    }
}

async function fetchProfile() {
    if (!accessToken) {
        updateAuthUI();
        return;
    }

    try {
        const data = await apiGet("/auth/me");
        currentUser = data.user;
        currentUsage = data.usage;
        updateAuthUI();
    } catch (err) {
        console.error("Profile fetch failed:", err);
        // Token likely expired
        updateAuthUI();
    }
}

function logout() {
    accessToken = null;
    refreshToken = null;
    currentUser = null;
    currentUsage = null;
    localStorage.removeItem("prism_access_token");
    localStorage.removeItem("prism_refresh_token");
    updateAuthUI();
    toast("Logged out successfully");
}

// Login
$("#login-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = $("#login-email").value;
    const password = $("#login-password").value;

    showLoading("Logging in...");
    try {
        // OAuth2 strict form data
        const formData = new URLSearchParams();
        formData.append("username", email);
        formData.append("password", password);

        const res = await fetch(`${API_BASE}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: formData,
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: "Login failed" }));
            throw new Error(err.detail);
        }

        const data = await res.json();
        accessToken = data.access_token;
        refreshToken = data.refresh_token;
        localStorage.setItem("prism_access_token", accessToken);
        localStorage.setItem("prism_refresh_token", refreshToken);

        toast("Logged in successfully!", "success");
        await fetchProfile(); // Automatically routes to app

        // Clear form
        $("#login-password").value = "";
    } catch (err) {
        toast(`Error: ${err.message}`, "error");
    } finally {
        hideLoading();
    }
});

// Register
$("#register-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = $("#register-name").value.trim();
    const email = $("#register-email").value.trim();
    const password = $("#register-password").value;

    showLoading("Creating account...");
    try {
        const data = await apiPost("/auth/register", { name, email, password }, true);

        accessToken = data.access_token;
        refreshToken = data.refresh_token;
        localStorage.setItem("prism_access_token", accessToken);
        localStorage.setItem("prism_refresh_token", refreshToken);

        toast("Account created successfully!", "success");
        await fetchProfile();

        // Clear form
        $("#register-password").value = "";
    } catch (err) {
        toast(`Error: ${err.message}`, "error");
    } finally {
        hideLoading();
    }
});

// Initialize app wrapper to fetch profile
const initHash = window.location.hash.substring(1);
if (accessToken && !["login", "register", "landing"].includes(initHash)) {
    showLoading("Loading Workspace...");
}
fetchProfile().finally(() => {
    hideLoading();
});

// ─── Blog Generation ────────────────────────────────────────────────────
let lastBlogContent = "";

$("#blog-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();

    const product_name = $("#blog-product").value.trim();
    const tone = $("#blog-tone").value;
    const word_count = parseInt($("#blog-words").value);

    if (!product_name) return toast("Please describe your product.", "error");

    showLoading("Drafting Blog Article...");
    try {
        const data = await apiPost("/generate-blog", { product_name, tone, word_count });
        lastBlogContent = data.generated_blog;

        // Render the blog content
        const resultEl = $("#blog-result");
        resultEl.innerHTML = "";
        resultEl.style.whiteSpace = "pre-wrap";
        resultEl.textContent = data.generated_blog;

        toast("Blog generated successfully!", "success");
        await fetchProfile(); // refresh usage stats
    } catch (err) {
        toast(`Error: ${err.message}`, "error");
    } finally {
        hideLoading();
    }
});

// Copy & Download blog & Translate
$("#blog-copy")?.addEventListener("click", () => {
    if (lastBlogContent) copyText(lastBlogContent);
    else toast("Generate a blog first.", "info");
});

$("#blog-translate-lang")?.addEventListener("change", async (e) => {
    const lang = e.target.value;
    if (!lang) return;
    if (!lastBlogContent) {
        toast("Generate a blog first.", "info");
        e.target.value = "";
        return;
    }
    const translated = await translateResult(lastBlogContent, lang);
    if (translated) {
        lastBlogContent = translated;
        $("#blog-result").textContent = translated;
        toast(`Translated to ${lang}`, "success");
    }
    e.target.value = "";
});

$("#blog-download")?.addEventListener("click", () => {
    if (lastBlogContent) downloadText(lastBlogContent, "prism-blog.txt");
    else toast("Generate a blog first.", "info");
});

$("#blog-share")?.addEventListener("click", () => {
    if (lastBlogContent) {
        shareContent({
            title: "Prism AI - Generated Blog",
            text: lastBlogContent
        });
    } else {
        toast("Generate a blog first.", "info");
    }
});

// ─── Video Script Generation ────────────────────────────────────────────
let lastVideoContent = "";

$("#video-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();

    const product_name = $("#video-product").value.trim();
    const tone = $("#video-tone").value;
    const duration = parseInt($("#video-duration").value);

    if (!product_name) return toast("Please describe your product.", "error");

    showLoading("Writing Video Script...");
    try {
        const data = await apiPost("/generate-video-script", { product_name, tone, duration });
        lastVideoContent = data.generated_script;

        const resultEl = $("#video-result");
        resultEl.innerHTML = "";
        resultEl.style.whiteSpace = "pre-wrap";
        resultEl.textContent = data.generated_script;

        toast("Video script generated!", "success");
        await fetchProfile(); // refresh usage stats
    } catch (err) {
        toast(`Error: ${err.message}`, "error");
    } finally {
        hideLoading();
    }
});

// Copy & Download video script & Translate
$("#video-copy")?.addEventListener("click", () => {
    if (lastVideoContent) copyText(lastVideoContent);
    else toast("Generate a script first.", "info");
});

$("#video-translate-lang")?.addEventListener("change", async (e) => {
    const lang = e.target.value;
    if (!lang) return;
    if (!lastVideoContent) {
        toast("Generate a script first.", "info");
        e.target.value = "";
        return;
    }
    const translated = await translateResult(lastVideoContent, lang);
    if (translated) {
        lastVideoContent = translated;
        $("#video-result").textContent = translated;
        toast(`Translated to ${lang}`, "success");
    }
    e.target.value = "";
});

$("#video-download")?.addEventListener("click", () => {
    if (lastVideoContent) downloadText(lastVideoContent, "prism-video-script.txt");
    else toast("Generate a script first.", "info");
});

$("#video-share")?.addEventListener("click", () => {
    if (lastVideoContent) {
        shareContent({
            title: "Prism AI - Generated Script",
            text: lastVideoContent
        });
    } else {
        toast("Generate a script first.", "info");
    }
});

// ─── Image Generation ───────────────────────────────────────────────────
let lastImageUrls = [];

$("#image-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();

    const product_name = $("#image-product").value.trim();
    const style = $("#image-style").value;
    const platform = $("#image-platform").value;
    const n = parseInt($("#image-count").value);

    if (!product_name) return toast("Please describe your product.", "error");

    showLoading("Synthesizing Image...");
    try {
        const data = await apiPost("/generate-image", { product_name, style, platform, n });

        // Store URLs for download
        lastImageUrls = data.images.map((img) => ({
            url: img.image_url.startsWith("data:") ? img.image_url : `${API_BASE}${img.image_url}`,
            filename: img.filename || `generated-${Date.now()}.png`,
        }));

        // Render images
        const resultEl = $("#image-result");
        resultEl.innerHTML = "";

        const grid = document.createElement("div");
        grid.className = "image-grid";

        data.images.forEach((img) => {
            const imgEl = document.createElement("img");
            imgEl.src = img.image_url.startsWith("data:") ? img.image_url : `${API_BASE}${img.image_url}`;
            imgEl.alt = `Generated image for ${product_name}`;
            imgEl.loading = "lazy";
            // Click to open full-size in new tab
            imgEl.addEventListener("click", () => window.open(imgEl.src, "_blank"));
            grid.appendChild(imgEl);
        });

        resultEl.appendChild(grid);

        // Show prompt
        const promptBox = $("#image-prompt-box");
        promptBox.classList.remove("hidden");
        $("#image-prompt-text").textContent = data.image_prompt;

        toast("Image generated!", "success");
        await fetchProfile(); // refresh usage stats
    } catch (err) {
        toast(`Error: ${err.message}`, "error");
    } finally {
        hideLoading();
    }
});

// Download image(s)
$("#image-download-btn")?.addEventListener("click", () => {
    if (lastImageUrls.length === 0) {
        toast("Generate an image first.", "info");
        return;
    }
    lastImageUrls.forEach((img) => downloadImage(img.url, img.filename));
});

$("#image-share-btn")?.addEventListener("click", async () => {
    if (lastImageUrls.length === 0) {
        toast("Generate an image first.", "info");
        return;
    }
    
    try {
        const filesToShare = [];
        for (const img of lastImageUrls) {
            const response = await fetch(img.url);
            const blob = await response.blob();
            filesToShare.push(new File([blob], img.filename, { type: blob.type }));
        }

        if (navigator.canShare && navigator.canShare({ files: filesToShare })) {
            await shareContent({
                title: "Prism AI - Generated Images",
                files: filesToShare
            });
        } else {
            // Fallback
            await shareContent({
                title: "Prism AI - Generated Image",
                text: "Check out this image I generated on Prism AI!"
            });
        }
    } catch (err) {
        console.error("Share error:", err);
        toast("Failed to prepare images for sharing.", "error");
    }
});

// ─── Sidebar Generation History ─────────────────────────────────────────

function timeAgo(dateStr) {
    const now = new Date();
    const date = new Date(dateStr);
    const seconds = Math.floor((now - date) / 1000);
    if (seconds < 60) return "just now";
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 7) return `${days}d ago`;
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

async function fetchSidebarHistory(type) {
    if (!currentUser || !accessToken) return;
    try {
        if (type === "intro") {
            const [allData, blogData, videoData, imageData] = await Promise.all([
                apiGet(`/history?limit=10&offset=0`),
                apiGet(`/history?type=blog&limit=10&offset=0`),
                apiGet(`/history?type=video&limit=10&offset=0`),
                apiGet(`/history?type=image&limit=10&offset=0`)
            ]);
            renderSidebarHistory("intro-all", allData.items, allData.total);
            renderSidebarHistory("intro-blog", blogData.items, blogData.total);
            renderSidebarHistory("intro-video", videoData.items, videoData.total);
            renderSidebarHistory("intro-image", imageData.items, imageData.total);
        } else {
            const data = await apiGet(`/history?type=${type}&limit=20&offset=0`);
            renderSidebarHistory(type, data.items, data.total);
        }
    } catch (err) {
        console.error(`Failed to fetch ${type} history:`, err);
    }
}

function renderSidebarHistory(type, items, total) {
    const listEl = $(`#sidebar-history-${type}`);
    const countEl = $(`#${type}-history-count`);
    if (!listEl) return;
    
    if (countEl) countEl.textContent = total;
    
    if (items.length === 0) {
        listEl.innerHTML = `<div style="padding: 20px; text-align: center; color: var(--text3); font-size: 13px;">No history yet.</div>`;
        return;
    }
    
    listEl.innerHTML = "";
    items.forEach(item => {
        const params = item.input_params || {};
        const title = params.product_name || "Untitled";
        
        const el = document.createElement("div");
        el.className = "history-sidebar-item";
        el.innerHTML = `
            <div class="history-sidebar-title">${title}</div>
            <div class="history-sidebar-meta">${timeAgo(item.created_at)}</div>
            <button class="history-sidebar-delete" title="Delete">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            </button>
        `;
        
        // Load into form on click
        el.addEventListener("click", (e) => {
            if (e.target.closest(".history-sidebar-delete")) return;
            if (type.startsWith("intro")) {
                // Determine gen_type and switch to it first, then reuse
                const targetTab = item.gen_type || "blog";
                switchTab(targetTab);
                setTimeout(() => reuseGeneration(item), 100);
            } else {
                reuseGeneration(item);
            }
        });
        
        // Delete item
        el.querySelector(".history-sidebar-delete").addEventListener("click", async (e) => {
            e.stopPropagation();
            if (!confirm("Delete this history entry?")) return;
            try {
                await apiDelete(`/history/${item.id}`);
                // Refresh list
                const fetchType = type.startsWith("intro") ? "intro" : type;
                fetchSidebarHistory(fetchType);
                toast("Entry deleted.", "success");
            } catch (err) {
                toast("Failed to delete.", "error");
            }
        });
        
        listEl.appendChild(el);
    });
}

function reuseGeneration(item) {
    const params = item.input_params || {};
    const type = item.gen_type;
    
    if (type === "blog") {
        const productEl = $("#blog-product");
        const toneEl = $("#blog-tone");
        const wordsEl = $("#blog-words");
        if (productEl) productEl.value = params.product_name || "";
        if (toneEl) toneEl.value = params.tone || "Informative";
        if (wordsEl) { wordsEl.value = params.word_count || 500; $("#blog-words-val").textContent = params.word_count || 500; }
        syncCustomDropdown(toneEl);
        toast("Loaded from history!", "success");
    } else if (type === "video") {
        const productEl = $("#video-product");
        const toneEl = $("#video-tone");
        const durationEl = $("#video-duration");
        if (productEl) productEl.value = params.product_name || "";
        if (toneEl) toneEl.value = params.tone || "Energetic";
        if (durationEl) { durationEl.value = params.duration || 3; $("#video-duration-val").textContent = `${params.duration || 3} min`; }
        syncCustomDropdown(toneEl);
        toast("Loaded from history!", "success");
    } else if (type === "image") {
        const productEl = $("#image-product");
        const styleEl = $("#image-style");
        const platformEl = $("#image-platform");
        if (productEl) productEl.value = params.product_name || "";
        if (styleEl) styleEl.value = params.style || "vibrant";
        if (platformEl) platformEl.value = params.platform || "instagram";
        syncCustomDropdown(styleEl);
        syncCustomDropdown(platformEl);
        toast("Loaded from history!", "success");
    }
}

function syncCustomDropdown(nativeSelect) {
    if (!nativeSelect) return;
    const wrapper = nativeSelect.closest(".custom-dropdown");
    if (!wrapper) return;
    const trigger = wrapper.querySelector(".custom-dropdown-text");
    const options = wrapper.querySelectorAll(".custom-dropdown-option");
    const selectedOpt = nativeSelect.options[nativeSelect.selectedIndex];
    if (trigger && selectedOpt) trigger.textContent = selectedOpt.textContent;
    options.forEach(opt => {
        opt.classList.toggle("selected", opt.dataset.value === nativeSelect.value);
    });
}

async function apiDelete(endpoint) {
    if (!accessToken) throw new Error("No token");
    const res = await fetch(`${API_BASE}${endpoint}`, {
        method: "DELETE",
        headers: { "Authorization": `Bearer ${accessToken}` },
    });
    if (!res.ok) {
        if (res.status === 401) logout();
        throw new Error("Failed to delete");
    }
    return res.json();
}

// Handle browser back/forward navigation
window.addEventListener("popstate", (event) => {
    // If the history state exists, switch to that tab without pushing a NEW history event
    if (event.state && event.state.tabId) {
        switchTab(event.state.tabId, false);
    } else {
        // Fallback: Read the URL hash (e.g., "#login") if there's no state, or default to landing
        const hash = window.location.hash.substring(1);
        if (hash) {
            switchTab(hash, false);
        } else {
            switchTab(currentUser ? "intro" : "landing", false);
        }
    }
});

// ─── UI Interactions ────────────────────────────────────────────────────
// Sidebar Toggle
document.querySelectorAll(".sidebar-toggle").forEach(btn => {
    btn.addEventListener("click", () => {
        const body = btn.closest(".workspace-shell")?.querySelector(".workspace-body");
        if (body) {
            body.classList.toggle("sidebar-closed");
        }
    });
});

// ─── Global History Panel ─────────────────────────────────────────────
const globalHistory = {
    items: [],
    total: 0,
    hasMore: false,
    currentFilter: "all",
    offset: 0,
    pageSize: 15
};

const gTypeIcons = {
    blog: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>`,
    video: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"></polygon><rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect></svg>`,
    image: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>`
};

async function fetchGlobalHistory(append = false) {
    if (!currentUser || !accessToken) return;
    try {
        const filter = globalHistory.currentFilter === "all" ? "" : `&type=${globalHistory.currentFilter}`;
        const data = await apiGet(`/history?limit=${globalHistory.pageSize}&offset=${globalHistory.offset}${filter}`);
        
        if (append) {
            globalHistory.items = [...globalHistory.items, ...data.items];
        } else {
            globalHistory.items = data.items;
        }
        globalHistory.total = data.total;
        globalHistory.hasMore = data.has_more;
        
        renderGlobalHistory();
    } catch (err) {
        toast("Failed to load history.", "error");
    }
}

function renderGlobalHistory() {
    const listEl = $("#history-list");
    const emptyEl = $("#history-empty");
    const actionsBar = $("#history-actions-bar");
    const countEl = $("#history-count");
    const loadMoreEl = $("#history-load-more");
    
    if (!listEl) return;
    listEl.innerHTML = "";
    
    if (globalHistory.items.length === 0) {
        emptyEl.style.display = "flex";
        actionsBar.style.display = "none";
        loadMoreEl.style.display = "none";
        return;
    }
    
    emptyEl.style.display = "none";
    actionsBar.style.display = "flex";
    countEl.textContent = `${globalHistory.total} generation${globalHistory.total !== 1 ? "s" : ""}`;
    
    globalHistory.items.forEach(item => {
        listEl.appendChild(createGlobalHistoryCard(item));
    });
    
    loadMoreEl.style.display = globalHistory.hasMore ? "flex" : "none";
}

function createGlobalHistoryCard(item) {
    const card = document.createElement("div");
    card.className = "history-card";
    const params = item.input_params || {};
    const genType = item.gen_type;
    
    // Build brief body content matching old UI closely
    let bodyContent = "";
    if (genType === "image" && item.image_urls && item.image_urls.length > 0) {
        const imgs = item.image_urls.map(url => {
            const fullUrl = url.startsWith("data:") || url.startsWith("http") ? url : `${API_BASE}${url}`;
            return `<img src="${fullUrl}" alt="Generated image" loading="lazy" onclick="window.open(this.src,'_blank')">`;
        }).join("");
        bodyContent += `<div class="history-images">${imgs}</div>`;
    } else if (item.output_data) {
        const truncated = item.output_data.length > 1000 ? item.output_data.substring(0, 1000) + "..." : item.output_data;
        bodyContent += `<div class="history-content">${truncated}</div>`;
    }
    
    card.innerHTML = `
        <div class="history-card-header">
            <div class="history-type-icon ${genType}">${gTypeIcons[genType] || ""}</div>
            <div class="history-card-info">
                <div class="history-card-title">${params.product_name || "Untitled"}</div>
                <div class="history-card-meta">
                    <span class="history-type-badge ${genType}">${genType}</span>
                    <span>${timeAgo(item.created_at)}</span>
                </div>
            </div>
            <div class="history-card-actions">
                <button class="btn-icon-sm ghistory-reuse-btn" title="Re-use settings">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="1 4 1 10 7 10"></polyline><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"></path></svg>
                </button>
                <button class="btn-icon-danger ghistory-delete-btn" title="Delete">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                </button>
            </div>
            <svg class="history-expand-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
        </div>
        <div class="history-card-body">${bodyContent}</div>
    `;
    
    card.querySelector(".history-card-header").addEventListener("click", (e) => {
        if (e.target.closest(".ghistory-reuse-btn") || e.target.closest(".ghistory-delete-btn")) return;
        card.classList.toggle("expanded");
    });
    
    card.querySelector(".ghistory-reuse-btn").addEventListener("click", (e) => {
        e.stopPropagation();
        reuseGeneration(item);
    });
    
    card.querySelector(".ghistory-delete-btn").addEventListener("click", async (e) => {
        e.stopPropagation();
        if (!confirm("Delete this history entry?")) return;
        try {
            await apiDelete(`/history/${item.id}`);
            fetchGlobalHistory();
        } catch (err) { }
    });
    
    return card;
}

// Global Filter Chips
$("#history-filters")?.addEventListener("click", (e) => {
    const chip = e.target.closest(".filter-chip");
    if (!chip) return;
    $$("#history-filters .filter-chip").forEach(c => {
        c.classList.remove("active");
        c.style.background = "rgba(255,255,255,.04)";
        c.style.color = "var(--text3)";
    });
    chip.classList.add("active");
    chip.style.background = "var(--amber)";
    chip.style.color = "#000";
    
    globalHistory.currentFilter = chip.dataset.filter;
    globalHistory.offset = 0;
    fetchGlobalHistory();
});

$("#history-load-more-btn")?.addEventListener("click", () => {
    globalHistory.offset += globalHistory.pageSize;
    fetchGlobalHistory(true);
});

$("#history-clear-all")?.addEventListener("click", async () => {
    if (!confirm("Delete all history?")) return;
    try {
        await apiDelete("/history");
        fetchGlobalHistory();
    } catch(e) {}
});

// Update standard history switch to load global history
const originalSwitchTab = switchTab;
window.switchTab = function(tabId, updateHist = true) {
    originalSwitchTab(tabId, updateHist);
    if (tabId === "history" && currentUser) {
        globalHistory.currentFilter = "all";
        globalHistory.offset = 0;
        $$("#history-filters .filter-chip").forEach(c => {
            c.classList.remove("active");
            c.style.background = "rgba(255,255,255,.04)";
            c.style.color = "var(--text3)";
        });
        const allChip = $("#history-filters .filter-chip[data-filter='all']");
        if(allChip) {
            allChip.classList.add("active");
            allChip.style.background = "var(--amber)";
            allChip.style.color = "#000";
        }
        fetchGlobalHistory();
    }
}
