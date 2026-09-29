// Portado do site (site/src/components/feedback/EmptyState.jsx).
// So o caminho da imagem mudou: aqui a aplicacao vive sob /acesso/.
//
// O vazio tem DOIS tons, e a diferenca nao e enfeite.
//
//   neutro  ainda nao existe nada. "Nenhuma crianca ainda."
//   bom     existia trabalho e acabou. "Nenhuma pendencia hoje."
//
// Com um tom so, "nenhuma pendencia hoje" — que e noticia boa — sai com cara
// de falta. A estrela de contorno apagada diz "vazio"; a amarela inteira diz
// "feito". E a mesma tela dizendo duas coisas opostas.
//
// A pose de comemoracao ainda nao existe como arquivo; ate ela chegar, o tom
// bom usa a estrela amarela de pe, que ja e diferente o bastante da apagada.

const TONS = {
  neutro: { arquivo: "star-mascot-outline.svg", opacidade: 0.7 },
  bom: { arquivo: "star-mascot-amarelo.svg", opacidade: 1 },
};

export default function EmptyState({ titulo, corpo, acao, tom = "neutro" }) {
  const { arquivo, opacidade } = TONS[tom] ?? TONS.neutro;

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
        src={`/acesso/images/${arquivo}`}
        alt=""
        style={{ width: 96, marginBottom: 20, opacity: opacidade }}
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
