// Cookie choice and Google Analytics.
//
// Analytics is off until the visitor accepts it. Nothing is requested from Google before that,
// and withdrawing the choice stops measurement and removes the cookies it set. The login token
// is needed for the site to work, so it is not part of this choice.

const STORAGE_KEY = "projectech_cookie_consent";
const GA_ID = "G-4J0TY48QZD";

export const CONSENT_CHANGED = "projectech:consent-changed";
export const OPEN_COOKIE_SETTINGS = "projectech:open-cookie-settings";

export function getConsent() {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return value === "accepted" || value === "declined" ? value : null;
  } catch {
    return null;
  }
}

function loadAnalytics() {
  window[`ga-disable-${GA_ID}`] = false;
  if (document.getElementById("ga-script")) return;

  window.dataLayer = window.dataLayer || [];
  window.gtag = function gtag() {
    window.dataLayer.push(arguments);
  };
  window.gtag("js", new Date());
  window.gtag("config", GA_ID);

  const script = document.createElement("script");
  script.id = "ga-script";
  script.async = true;
  script.src = `https://www.googletagmanager.com/gtag/js?id=${GA_ID}`;
  document.head.appendChild(script);
}

function stopAnalytics() {
  // Tells Google's script, if it is already loaded, to stop measuring.
  window[`ga-disable-${GA_ID}`] = true;

  // Remove the cookies it set (_ga and _ga_XXXX) on this host and its parent domains.
  const parts = window.location.hostname.split(".");
  const domains = [""];
  for (let i = 0; i < parts.length - 1; i += 1) {
    domains.push(`; domain=${parts.slice(i).join(".")}`, `; domain=.${parts.slice(i).join(".")}`);
  }
  document.cookie.split(";").forEach((cookie) => {
    const name = cookie.split("=")[0].trim();
    if (name === "_ga" || name.startsWith("_ga_")) {
      domains.forEach((domain) => {
        document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/${domain}`;
      });
    }
  });
}

// Applies the saved choice. Call it once when the app starts.
export function applyConsent() {
  if (getConsent() === "accepted") loadAnalytics();
  else stopAnalytics();
}

export function setConsent(choice) {
  try {
    localStorage.setItem(STORAGE_KEY, choice);
  } catch {
    // Storage is blocked. The choice lasts until the page reloads, then the banner asks again.
  }
  if (choice === "accepted") loadAnalytics();
  else stopAnalytics();
  window.dispatchEvent(new CustomEvent(CONSENT_CHANGED, { detail: choice }));
}

export function openCookieSettings() {
  window.dispatchEvent(new Event(OPEN_COOKIE_SETTINGS));
}
