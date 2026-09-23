import Button from "../core/Button.jsx";

const COPY = {
  donate: {
    eyebrow: "Doe",
    title: "Sua doação vira sorriso na véspera de Natal",
    body: "Cada real ajuda a levar brincadeiras, alimentação e presentes para milhares de crianças.",
    cta: "Quero doar",
  },
  sponsor: {
    eyebrow: "Apadrinhe",
    title: "Apadrinhe o Natal de uma criança",
    body: "Escolha uma cartinha e realize o pedido de Natal de uma criança em situação de vulnerabilidade.",
    cta: "Apadrinhar agora",
  },
  volunteer: {
    eyebrow: "Voluntariado",
    title: "Venha brincar com a gente",
    body: "Times de voluntários fazem o dia acontecer: recepção, brincadeiras, alimentação e logística.",
    cta: "Ser voluntário",
  },
};

export default function CTASection({ kind = "sponsor" }) {
  const c = COPY[kind];

  return (
    <section
      style={{
        background: "var(--navy-700)",
        color: "var(--white)",
        padding: "56px 40px",
        borderRadius: "var(--radius-lg)",
        fontFamily: "var(--font-body)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 32,
      }}
    >
      <div style={{ maxWidth: 520 }}>
        <div
          style={{
            fontFamily: "var(--font-condensed)",
            fontWeight: 800,
            fontSize: 13,
            letterSpacing: ".12em",
            color: "var(--amber-500)",
            marginBottom: 12,
          }}
        >
          {c.eyebrow.toUpperCase()}
        </div>
        <h3 style={{ fontSize: 32, margin: "0 0 12px", fontWeight: 800 }}>{c.title}</h3>
        <p style={{ fontSize: 16, color: "var(--navy-200)", margin: "0 0 24px", lineHeight: 1.6 }}>
          {c.body}
        </p>
        <Button variant="primary" size="lg">
          {c.cta}
        </Button>
      </div>
      <img src="/images/two-stars-scene.svg" alt="" style={{ width: 180, opacity: 0.9 }} />
    </section>
  );
}
