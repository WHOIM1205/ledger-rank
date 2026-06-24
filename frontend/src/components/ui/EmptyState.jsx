// Placeholder shown when there is no data yet. Pure / props-only.

export default function EmptyState({ message = "No data yet." }) {
  return <div className="empty-state">{message}</div>;
}
