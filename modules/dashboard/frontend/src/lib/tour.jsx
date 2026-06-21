import { createContext, useCallback, useContext, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { driver } from "driver.js";
import "driver.js/dist/driver.css";
import "../styles/tour.css";
import { useData } from "./data";
import { buildTourSteps } from "./tourSteps";

/**
 * Guided judge walkthrough — a driver.js spotlight tour that auto-navigates
 * across pages. Auto-starts on every page landing, re-launchable on demand
 * via the topbar Help button (`useTour().start`).
 */
const TourCtx = createContext(null);

// Resolve when the selector exists in the DOM, or after `timeout` (resolves null
// so a missing anchor degrades gracefully instead of hanging the tour).
function waitForElement(selector, timeout = 3000) {
  return new Promise((resolve) => {
    if (!selector) return resolve(null);
    if (document.querySelector(selector)) return resolve(document.querySelector(selector));
    const start = performance.now();
    const tick = () => {
      const el = document.querySelector(selector);
      if (el) return resolve(el);
      if (performance.now() - start > timeout) return resolve(null);
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
}

export function TourProvider({ children }) {
  const navigate = useNavigate();
  const { data } = useData();
  const driverRef = useRef(null);
  const autoStartedRef = useRef(false);

  const pickIncidentId = useCallback(() => {
    const incidents = data?.incidents || [];
    const crit = incidents.find((i) => i.risk_band === "CRITICAL");
    return (crit || incidents[0])?.incident_id || "";
  }, [data]);

  const start = useCallback(async () => {
    if (driverRef.current) {
      driverRef.current.destroy();
      driverRef.current = null;
    }

    const steps = buildTourSteps(pickIncidentId());

    // Navigate to a step's route (if needed) and wait for its anchor to mount.
    const goToStep = async (index) => {
      const step = steps[index];
      if (!step) return;
      const current = window.location.pathname + window.location.search;
      if (step.route && step.route !== current) navigate(step.route);
      const el = await waitForElement(step.element);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        // Let the smooth scroll settle before driver.js positions the overlay.
        await new Promise((r) => setTimeout(r, 400));
      }
    };

    const d = driver({
      showProgress: true,
      allowClose: true,
      overlayOpacity: 0.6,
      stagePadding: 6,
      popoverClass: "ti-tour",
      nextBtnText: "Next →",
      prevBtnText: "← Back",
      doneBtnText: "Done",
      progressText: "{{current}} / {{total}}",
      steps: steps.map((s) => ({ element: s.element, popover: s.popover })),
      onNextClick: async (_el, _step, opts) => {
        const next = opts.state.activeIndex + 1;
        if (next >= steps.length) return d.destroy();
        await goToStep(next);
        d.moveNext();
      },
      onPrevClick: async (_el, _step, opts) => {
        const prev = opts.state.activeIndex - 1;
        if (prev < 0) return;
        await goToStep(prev);
        d.movePrevious();
      },
      onDestroyed: () => {
        // Leave the app on a clean route — strip the tour's ?incident deep-link.
        if (window.location.pathname === "/app/findings" && window.location.search) {
          navigate("/app/findings", { replace: true });
        }
        driverRef.current = null;
      },
    });

    driverRef.current = d;
    await goToStep(0);
    d.drive();
  }, [navigate, pickIncidentId]);

  // Auto-start on every page landing, after data has loaded.
  useEffect(() => {
    if (autoStartedRef.current || !data) return;
    if (!window.location.pathname.startsWith("/app")) return;
    const t = setTimeout(() => {
      autoStartedRef.current = true;
      start();
    }, 700);
    return () => clearTimeout(t);
  }, [data, start]);

  // Clean up any live tour on unmount.
  useEffect(() => () => driverRef.current?.destroy?.(), []);

  return <TourCtx.Provider value={{ start }}>{children}</TourCtx.Provider>;
}

export function useTour() {
  return useContext(TourCtx) || { start: () => {} };
}
