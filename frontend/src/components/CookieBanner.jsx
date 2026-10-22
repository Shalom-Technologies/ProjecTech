import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  applyConsent,
  getConsent,
  setConsent,
  CONSENT_CHANGED,
  OPEN_COOKIE_SETTINGS,
} from "../consent";

// Asks once whether we may use Google Analytics. "Cookie settings" links open it again.
export default function CookieBanner() {
  const [visible, setVisible] = useState(() => getConsent() === null);
  const [current, setCurrent] = useState(getConsent);

  useEffect(() => {
    applyConsent();
    const reopen = () => {
      setCurrent(getConsent());
      setVisible(true);
    };
    const changed = (e) => setCurrent(e.detail);
    window.addEventListener(OPEN_COOKIE_SETTINGS, reopen);
    window.addEventListener(CONSENT_CHANGED, changed);
    return () => {
      window.removeEventListener(OPEN_COOKIE_SETTINGS, reopen);
      window.removeEventListener(CONSENT_CHANGED, changed);
    };
  }, []);

  if (!visible) return null;

  const choose = (choice) => {
    setConsent(choice);
    setVisible(false);
  };

  return (
    <div className="cookie-banner" role="dialog" aria-labelledby="cookie-title">
      <div className="cookie-banner-text">
        <p id="cookie-title" className="cookie-banner-title">Cookies</p>
        <p>
          ProjecTech keeps a login token in your browser so you stay signed in. The site needs it
          and it is not optional. With your permission we also use Google Analytics to count visits
          and see which pages are used.{" "}
          <Link to="/privacy#cookies">Read how we use them</Link>.
        </p>
        {current && (
          <p className="cookie-banner-current">
            Your current choice: {current === "accepted" ? "analytics on" : "analytics off"}.
          </p>
        )}
      </div>
      <div className="cookie-banner-actions">
        <button type="button" className="btn-secondary" onClick={() => choose("declined")}>
          Decline analytics
        </button>
        <button type="button" className="btn-secondary" onClick={() => choose("accepted")}>
          Accept analytics
        </button>
      </div>
    </div>
  );
}
