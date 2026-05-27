export default function MetricCard({ icon: Icon, label, value, tone }) {
  return (
    <article className={`metric metric-${tone}`}>
      <div className="metric-icon">
        <Icon size={20} aria-hidden="true" />
      </div>
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
      </div>
    </article>
  );
}
