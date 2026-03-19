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
        // If not logged in and clicking a generator tab, force to login
        if (!currentUser && ["blog", "video", "image"].includes(btn.dataset.tab)) {
            toast("Please login to generate content", "info");
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
}

// ─── Range Sliders ──────────────────────────────────────────────────────
$("#blog-words").addEventListener("input", (e) => {
    $("#blog-words-val").textContent = e.target.value;
});

$("#video-duration").addEventListener("input", (e) => {
    $("#video-duration-val").textContent = `${e.target.value} min`;
});

$("#image-count").addEventListener("input", (e) => {
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

$("#blog-form").addEventListener("submit", async (e) => {
    e.preventDefault();

    const product_name = $("#blog-product").value.trim();
    const tone = $("#blog-tone").value;
    const word_count = parseInt($("#blog-words").value);

    if (!product_name) return toast("Please enter a product name.", "error");

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

// Copy & Download blog
$("#blog-copy").addEventListener("click", () => {
    if (lastBlogContent) copyText(lastBlogContent);
    else toast("Generate a blog first.", "info");
});

$("#blog-download").addEventListener("click", () => {
    if (lastBlogContent) downloadText(lastBlogContent, "prism-blog.txt");
    else toast("Generate a blog first.", "info");
});

// ─── Video Script Generation ────────────────────────────────────────────
let lastVideoContent = "";

$("#video-form").addEventListener("submit", async (e) => {
    e.preventDefault();

    const product_name = $("#video-product").value.trim();
    const tone = $("#video-tone").value;
    const duration = parseInt($("#video-duration").value);

    if (!product_name) return toast("Please enter a product name.", "error");

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

// Copy & Download video script
$("#video-copy").addEventListener("click", () => {
    if (lastVideoContent) copyText(lastVideoContent);
    else toast("Generate a script first.", "info");
});

$("#video-download").addEventListener("click", () => {
    if (lastVideoContent) downloadText(lastVideoContent, "prism-video-script.txt");
    else toast("Generate a script first.", "info");
});

// ─── Image Generation ───────────────────────────────────────────────────
let lastImageUrls = [];

$("#image-form").addEventListener("submit", async (e) => {
    e.preventDefault();

    const product_name = $("#image-product").value.trim();
    const style = $("#image-style").value;
    const platform = $("#image-platform").value;
    const n = parseInt($("#image-count").value);

    if (!product_name) return toast("Please enter a product name.", "error");

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
$("#image-download-btn").addEventListener("click", () => {
    if (lastImageUrls.length === 0) {
        toast("Generate an image first.", "info");
        return;
    }
    lastImageUrls.forEach((img) => downloadImage(img.url, img.filename));
});

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
