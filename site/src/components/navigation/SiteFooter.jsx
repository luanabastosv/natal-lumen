const COLUMNS = [
  { title: "Sobre", links: ["O projeto", "Obra Lumen Ser Feliz", "Edições anteriores"] },
  {
    title: "Participe",
    links: ["Apadrinhe uma criança", "Doe", "Seja voluntário", "Empresas parceiras"],
  },
  { title: "Contato", links: ["Fale conosco", "Imprensa", "Loja"] },
];

export default function SiteFooter() {
  return (
    <footer
      style={{
        background: "var(--navy-900)",
        color: "var(--cream-500)",
        padding: "48px 32px 24px",
        fontFamily: "var(--font-body)",
      }}
    >
      <div style={{ display: "flex", gap: 64, flexWrap: "wrap" }}>
        <div style={{ maxWidth: 260 }}>
          <div style={{ fontWeight: 800, fontSize: 20, color: "var(--white)", marginBottom: 8 }}>
            Natal Lumen
          </div>
          <p style={{ fontSize: 13, color: "var(--navy-300)", lineHeight: 1.6 }}>
            Um projeto social natalino ligado à Obra Lumen Ser Feliz, há mais de 30 anos levando
            alegria a crianças em situação de vulnerabilidade.
          </p>
        </div>
        {COLUMNS.map((c) => (
          <div key={c.title}>
            <div
              style={{
                fontFamily: "var(--font-condensed)",
                fontWeight: 800,
                fontSize: 12,
                letterSpacing: ".08em",
                color: "var(--amber-500)",
                marginBottom: 12,
              }}
            >
              {c.title.toUpperCase()}
            </div>
            {c.links.map((l) => (
              <div key={l} style={{ marginBottom: 8 }}>
                <a href="#" style={{ color: "var(--cream-500)", fontSize: 14, textDecoration: "none" }}>
                  {l}
                </a>
              </div>
            ))}
          </div>
        ))}
      </div>
      <div
        style={{
          borderTop: "1px solid var(--border-dark)",
          marginTop: 32,
          paddingTop: 16,
          fontSize: 12,
          color: "var(--navy-300)",
        }}
      >
        © {new Date().getFullYear()} Natal Lumen — Obra Lumen Ser Feliz. Fortaleza · Brasil ·
        Guiné-Bissau.
      </div>
    </footer>
  );
}
