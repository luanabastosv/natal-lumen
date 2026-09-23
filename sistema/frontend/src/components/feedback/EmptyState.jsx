// Portado do site (site/src/components/feedback/EmptyState.jsx).
// So o caminho da imagem mudou: aqui a aplicacao vive sob /acesso/.

export default function EmptyState({ titulo, corpo, acao }) {
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
      <img
        src="/acesso/images/star-mascot-outline.svg"
        alt=""
        style={{ width: 96, marginBottom: 20, opacity: 0.7 }}
      />
      <h4
        style={{
          fontSize: 20,
          fontWeight: 800,
          color: "var(--text-on-light-primary)",
          margin: "0 0 8px",
        }}
      >
        {titulo}
      </h4>
      {corpo && (
        <p
          style={{
            fontSize: 14,
            color: "var(--text-on-light-secondary)",
            margin: "0 0 20px",
            lineHeight: 1.6,
          }}
        >
          {corpo}
        </p>
      )}
      {acao}
    </div>
  );
}
