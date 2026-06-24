// Backend availability banner. Polls GET /health on mount (and on a light
// interval) and shows 🟢 Connected / 🔴 Offline / checking. Pure presentation —
// the actual fetching is driven by App via props so there is one source of truth.

export default function HealthIndicator({ state }) {
  // state: "checking" | "online" | "offline"
  let dotClass = "health__dot--checking";
  let label = "Checking backend…";

  if (state === "online") {
    dotClass = "health__dot--online";
    label = "Connected";
  } else if (state === "offline") {
    dotClass = "health__dot--offline";
    label = "Offline";
  }

  return (
    <div className={`health health--${state}`} aria-live="polite">
      <span className={`health__dot ${dotClass}`} aria-hidden="true" />
      <span className="health__label">{label}</span>
    </div>
  );
}
