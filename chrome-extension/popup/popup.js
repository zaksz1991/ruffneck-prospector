const apiUrlInput = document.getElementById("apiUrl");
const workspaceInput = document.getElementById("workspaceId");
const captureBtn = document.getElementById("captureBtn");
const saveBtn = document.getElementById("saveSettings");
const statusEl = document.getElementById("status");
const pageTypeEl = document.getElementById("pageType");

// Load saved settings
chrome.storage.sync.get(["apiUrl", "workspaceId"], (data) => {
  apiUrlInput.value = data.apiUrl || "http://localhost:8000";
  workspaceInput.value = data.workspaceId || "";
});

// Detect current page type
chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
  const url = tabs[0]?.url || "";
  if (url.includes("linkedin.com/in/")) {
    pageTypeEl.textContent = "LinkedIn Profile detected";
    pageTypeEl.classList.add("active");
  } else if (url.includes("google.com/maps") || url.includes("maps.google.com")) {
    pageTypeEl.textContent = "Google Maps detected";
    pageTypeEl.classList.add("active");
  } else {
    pageTypeEl.textContent = "Unsupported page – open a LinkedIn profile or Maps place";
  }
});

saveBtn.addEventListener("click", () => {
  chrome.storage.sync.set({
    apiUrl: apiUrlInput.value.trim(),
    workspaceId: workspaceInput.value.trim(),
  }, () => {
    showStatus("Settings saved", true);
  });
});

captureBtn.addEventListener("click", async () => {
  const apiUrl = apiUrlInput.value.trim() || "http://localhost:8000";
  const workspaceId = workspaceInput.value.trim() || null;

  captureBtn.disabled = true;
  captureBtn.textContent = "Capturing…";

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) throw new Error("No active tab");

    // Ask content script for page data
    const pageData = await chrome.tabs.sendMessage(tab.id, { type: "RUFFNECK_CAPTURE" });

    if (!pageData || !pageData.type) {
      throw new Error("Could not extract data from this page");
    }

    let endpoint, body;

    if (pageData.type === "linkedin_profile") {
      endpoint = `${apiUrl}/api/linkedin/profile`;
      body = {
        profile_url: pageData.url,
        enrich: true,
      };
    } else if (pageData.type === "google_maps") {
      // Use generic search endpoint with maps platform
      endpoint = `${apiUrl}/api/prospects/search`;
      body = {
        platform: "maps",
        target_url: pageData.query || pageData.name || pageData.url,
        keywords: pageData.has_website === false ? ["no_website"] : [],
        max_results: 5,
      };
    } else {
      throw new Error("Unsupported page type");
    }

    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const err = await res.text();
      throw new Error(err || `HTTP ${res.status}`);
    }

    const result = await res.json();

    // Optionally assign to workspace
    if (workspaceId && result.prospect?.id) {
      await fetch(`${apiUrl}/api/workspaces/${workspaceId}/assign-prospects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prospect_ids: [result.prospect.id] }),
      });
    }

    showStatus("Captured successfully! Check Prospects / Pipeline.", true);
  } catch (err) {
    showStatus(err.message || "Capture failed", false);
  } finally {
    captureBtn.disabled = false;
    captureBtn.textContent = "Capture to RuffNeck";
  }
});

function showStatus(msg, ok) {
  statusEl.textContent = msg;
  statusEl.className = "status " + (ok ? "ok" : "err");
}
