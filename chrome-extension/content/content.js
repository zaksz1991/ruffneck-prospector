chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type !== "RUFFNECK_CAPTURE") return;

  const url = window.location.href;

  // LinkedIn Profile
  if (url.includes("linkedin.com/in/")) {
    const name = document.querySelector("h1")?.innerText?.trim() || null;
    const headline = document.querySelector(".text-body-medium")?.innerText?.trim() || null;
    const about = document.querySelector("#about ~ div .inline-show-more-text, #about + div")?.innerText?.trim() || null;

    sendResponse({
      type: "linkedin_profile",
      url: url.split("?")[0],
      name,
      headline,
      about: about ? about.slice(0, 500) : null,
    });
    return true;
  }

  // Google Maps
  if (url.includes("google.com/maps") || url.includes("maps.google.com")) {
    const name = document.querySelector("h1")?.innerText?.trim()
      || document.querySelector('div[role="main"] h1')?.innerText?.trim()
      || null;

    // Heuristic: look for website link
    const hasWebsite = !!document.querySelector('a[data-item-id="authority"], a[href*="http"][data-tooltip*="Website"], a[aria-label*="Website"]');

    // Phone
    const phoneEl = document.querySelector('button[data-item-id*="phone"], button[aria-label*="Phone"]');
    const phone = phoneEl?.innerText?.trim() || phoneEl?.getAttribute("aria-label") || null;

    sendResponse({
      type: "google_maps",
      url,
      name,
      query: name,
      has_website: hasWebsite,
      phone,
    });
    return true;
  }

  sendResponse({ type: null });
  return true;
});
