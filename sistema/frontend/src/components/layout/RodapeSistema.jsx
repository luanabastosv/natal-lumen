export default function RodapeSistema() {
  return (
    <footer className="rodape">
      <span>Natal Lumen · sistema interno</span>
      {/* Link absoluto de proposito: sai do /acesso e volta ao site publico. */}
      <a href="/" className="rodape__voltar">
        Voltar ao site
      </a>
    </footer>
  );
}
