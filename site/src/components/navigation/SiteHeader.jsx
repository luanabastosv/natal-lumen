const LINKS = ["Sobre", "Edições", "Apadrinhe", "Doe", "Voluntariado", "Contato"];

export default function SiteHeader({ storeOpen = true }) {
  return (
    <header className="site-header">
      <div className="site-header__inner">
        <div className="site-header__brand">
          <img src="/images/star-mascot-outline.svg" alt="" className="site-header__mascot" />
          Natal Lumen
        </div>
        <nav className="site-header__nav">
          {LINKS.map((l) => (
            <a key={l} href="#">
              {l}
            </a>
          ))}
        </nav>
        {storeOpen && (
          <a href="#" className="site-header__store-pill">
            Loja aberta
          </a>
        )}
      </div>
    </header>
  );
}
