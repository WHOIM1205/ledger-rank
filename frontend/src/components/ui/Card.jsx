// Layout wrapper for a feature panel. Pure / props-only.

export default function Card({ title, subtitle, children, footer }) {
  return (
    <section className="card">
      {(title || subtitle) && (
        <header className="card__header">
          {title && <h2 className="card__title">{title}</h2>}
          {subtitle && <p className="card__subtitle">{subtitle}</p>}
        </header>
      )}
      <div className="card__body">{children}</div>
      {footer && <footer className="card__footer">{footer}</footer>}
    </section>
  );
}
