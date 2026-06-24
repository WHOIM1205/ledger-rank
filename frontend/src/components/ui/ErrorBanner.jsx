// Renders a backend error envelope uniformly: code + message + optional details.
// Pure / props-only. `error` is an ApiError (or null).

export default function ErrorBanner({ error, title = "Error" }) {
  if (!error) return null;

  const hasDetails =
    error.details && Object.keys(error.details).length > 0;

  return (
    <div className="banner banner--error" role="alert">
      <div className="banner__row">
        <span className="banner__badge">{error.code}</span>
        <strong className="banner__title">{title}</strong>
      </div>
      <p className="banner__message">{error.message}</p>
      {hasDetails && (
        <pre className="banner__details">
          {JSON.stringify(error.details, null, 2)}
        </pre>
      )}
    </div>
  );
}
