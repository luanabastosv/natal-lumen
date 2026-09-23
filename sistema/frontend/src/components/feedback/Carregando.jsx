export default function Carregando({ children = "Carregando...", tela = false }) {
  const conteudo = (
    <div className="carregando" role="status">
      <span className="carregando__roda" />
      <span>{children}</span>
    </div>
  );

  return tela ? <div className="carregando-tela">{conteudo}</div> : conteudo;
}
