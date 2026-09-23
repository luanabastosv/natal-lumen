export default function StoreBanner({ open = true }) {
  if (!open) return null;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 20,
        background: "var(--white)",
        color: "var(--navy-700)",
        padding: "16px 24px",
        borderTop: "var(--stroke-hairline) solid var(--stroke-hairline-color)",
        borderBottom: "var(--stroke-hairline) solid var(--stroke-hairline-color)",
        fontFamily: "var(--font-body)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <span
          style={{
            fontFamily: "var(--font-condensed)",
            fontWeight: 900,
            fontSize: 12,
            letterSpacing: ".08em",
            color: "var(--amber-700)",
            border: "1.5px solid var(--amber-500)",
            padding: "3px 9px",
            borderRadius: "var(--radius-pill)",
          }}
        >
          LOJA ABERTA
        </span>
        <span style={{ fontWeight: 700, fontSize: 15 }}>
          Camisetas e produtos da edição 2025 já estão disponíveis
        </span>
      </div>
      <a
        href="#"
        style={{
          color: "var(--navy-700)",
          fontSize: 14,
          fontWeight: 700,
          textDecoration: "underline",
          textDecorationColor: "var(--amber-500)",
          textUnderlineOffset: 3,
        }}
      >
        Visitar loja →
      </a>
    </div>
  );
}
