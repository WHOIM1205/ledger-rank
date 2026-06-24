// Renders the result of a transaction create:
//   201 -> green "Created"
//   200 -> blue "Duplicate replay"
// Pure / props-only.

export default function StatusBadge({ status, duplicate }) {
  if (status === null || status === undefined) return null;

  let tone = "neutral";
  let label = `HTTP ${status}`;

  if (status === 201) {
    tone = "success";
    label = "Created (201)";
  } else if (status === 200 && duplicate) {
    tone = "info";
    label = "Duplicate replay (200)";
  } else if (status === 200) {
    tone = "info";
    label = "OK (200)";
  }

  return <span className={`status-badge status-badge--${tone}`}>{label}</span>;
}
