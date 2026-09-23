export default function BrowserCard({ title, children, imageSlot, dark = false }) {
  return (
    <div
      style={{
        borderRadius: "var(--radius-lg)",
        overflow: "hidden",
        background: dark ? "var(--navy-800)" : "var(--surface-card)",
        boxShadow: "none",
        border: "var(--stroke-hairline) solid var(--stroke-hairline-color)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "10px 14px",
          background: dark ? "var(--navy-900)" : "var(--white)",
          borderBottom: "var(--stroke-hairline) solid var(--stroke-hairline-color)",
        }}
      >
        <span style={{ width: 10, height: 10, borderRadius: "50%", background: "var(--amber-500)" }} />
        <span style={{ width: 10, height: 10, borderRadius: "50%", background: "var(--navy-300)" }} />
        <span style={{ width: 10, height: 10, borderRadius: "50%", background: "var(--navy-300)" }} />
        {title && (
          <span
            style={{
              margin: "0 auto",
              fontFamily: "var(--font-body)",
              fontSize: 12,
              fontWeight: 700,
              color: dark ? "var(--text-on-dark-muted)" : "var(--text-on-light-muted)",
            }}
          >
            {title}
          </span>
        )}
      </div>
      {imageSlot && (
        <div style={{ aspectRatio: "16/9", background: "var(--navy-100)" }}>{imageSlot}</div>
      )}
      <div
        style={{
          padding: "var(--space-5)",
          color: dark ? "var(--text-on-dark-primary)" : "var(--text-on-light-primary)",
        }}
      >
        {children}
      </div>
    </div>
  );
}
