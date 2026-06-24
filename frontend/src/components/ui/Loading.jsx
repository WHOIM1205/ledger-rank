// Small inline spinner + label. Pure / props-only.

export default function Loading({ label = "Loading…" }) {
  return (
    <div className="loading" role="status" aria-live="polite">
      <span className="loading__spinner" aria-hidden="true" />
      <span className="loading__label">{label}</span>
    </div>
  );
}
