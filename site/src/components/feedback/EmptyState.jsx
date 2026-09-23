export default function EmptyState({ illustration = "mascot", title, body, action }) {
  const src =
    illustration === "mascot" ? "/images/star-mascot-outline.svg" : "/images/criancas-2.svg";

  return (
    <div
      style={{
        textAlign: "center",
        padding: "48px 24px",
        fontFamily: "var(--font-body)",
        maxWidth: 420,
        margin: "0 auto",
      }}
    >
      <img src={src} alt="" style={{ width: 120, marginBottom: 20 }} />
      <h4 style={{ fontSize: 20, fontWeight: 800, color: "var(--text-on-light-primary)", margin: "0 0 8px" }}>
        {title}
      </h4>
      {body && (
        <p style={{ fontSize: 14, color: "var(--text-on-light-secondary)", margin: "0 0 20px", lineHeight: 1.6 }}>
          {body}
        </p>
      )}
      {action}
    </div>
  );
}
