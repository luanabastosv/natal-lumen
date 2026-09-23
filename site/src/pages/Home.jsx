import SiteHeader from "../components/navigation/SiteHeader.jsx";
import SiteFooter from "../components/navigation/SiteFooter.jsx";
import DuotonePhoto from "../components/media/DuotonePhoto.jsx";
import "./Home.css";

const PURPOSES = [
  {
    title: "Um dia inesquecível",
    body: "Transformar um único dia em uma lembrança de alegria para cada criança.",
  },
  {
    title: "Solidariedade em prática",
    body: "Aproximar voluntários, famílias e empresas em torno de uma causa comum.",
  },
  {
    title: "Dignidade no Natal",
    body: "Garantir que nenhuma criança fique sem presente, comida e diversão no Natal.",
  },
];

const EDITIONS = [
  {
    number: "20",
    date: "Dez · 2025",
    city: "Fortaleza, CE",
    desc: "Mais de 3.200 crianças participaram da edição na capital cearense.",
    dark: true,
  },
  {
    number: "13",
    date: "Dez · 2025",
    city: "Caucaia, CE",
    desc: "Uma tarde de brincadeiras e presentes para famílias da região metropolitana.",
  },
  {
    number: "06",
    date: "Dez · 2025",
    city: "Guiné-Bissau",
    desc: "O projeto chegou à África pela parceria com a Obra Lumen Ser Feliz.",
  },
];

export default function Home() {
  return (
    <div className="home">
      <SiteHeader storeOpen />

      <section className="hero">
        <div className="hero__copy">
          <div className="hero__eyebrow">Edição 2026 · Fortaleza</div>
          <h1 className="hero__title">natal lumen</h1>
          <p className="hero__lede">
            Um dia de brincadeiras, comida boa e presentes para milhares de crianças em Fortaleza
            e em outras cidades.
          </p>
          <a href="#" className="hero__cta">
            Como ajudar
          </a>
        </div>
        <div className="hero__photo">
          <DuotonePhoto
            src="/images/city-photo.jpg"
            alt="Crianças na edição do Natal Lumen"
            tone="navy"
            radius="none"
          />
        </div>
      </section>

      <section className="split-section">
        <div className="section-label">Sobre o projeto</div>
        <div>
          <h2 className="about__title">Trinta anos de Natal para quem mais precisa</h2>
          <p className="about__body">
            O Natal Lumen é um projeto social ligado à Obra Lumen Ser Feliz. Há mais de 30 anos,
            leva um dia de brincadeiras, alimentação e presentes a crianças em situação de
            vulnerabilidade em Fortaleza, em outras cidades do Brasil e na Guiné-Bissau.
          </p>
          <p className="about__body">
            Cada edição é feita por voluntários, famílias e empresas parceiras.
          </p>
          <a href="#" className="btn-outline">
            Conhecer a história
          </a>
        </div>
      </section>

      <div className="wide-photo">
        <div>
          <DuotonePhoto
            src="/images/about-photo.jpg"
            alt="Voluntários e crianças em uma edição do Natal Lumen"
            tone="navy"
            radius="lg"
          />
        </div>
      </div>

      <section className="split-section split-section--bordered">
        <div className="section-label">Nossos propósitos</div>
        <div className="purpose-list">
          {PURPOSES.map((p, i) => (
            <div className="purpose-item" key={p.title}>
              <div className="purpose-item__index">{String(i + 1).padStart(2, "0")}</div>
              <div>
                <h3 className="purpose-item__title">{p.title}</h3>
                <p className="purpose-item__body">{p.body}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="editions">
        <div className="editions__header">
          <div>
            <div className="editions__eyebrow">Edições</div>
            <h2 className="editions__title">Onde já chegamos</h2>
          </div>
          <a href="#" className="btn-outline editions__see-all">
            Ver todas as cidades
          </a>
        </div>
        <div className="editions__grid">
          {EDITIONS.map((e) => (
            <div
              className={`edition-card ${e.dark ? "edition-card--dark" : "edition-card--light"}`}
              key={e.city}
            >
              <div className="edition-card__top">
                <div className="edition-card__number">{e.number}</div>
                <div className="edition-card__date">{e.date}</div>
              </div>
              <div>
                <h3 className="edition-card__city">{e.city}</h3>
                <p className="edition-card__desc">{e.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <div className="store-bar">
        <div className="store-bar__left">
          <span className="store-bar__label">Loja aberta</span>
          <span className="store-bar__text">
            Camisetas e produtos da edição 2025 já estão disponíveis.
          </span>
        </div>
        <a href="#" className="store-bar__link">
          Visitar loja
        </a>
      </div>

      <section className="final-cta">
        <div>
          <h3 className="final-cta__title">participe</h3>
          <p className="final-cta__body">
            Cada contribuição leva brincadeiras, comida e presentes para mais crianças neste
            Natal.
          </p>
        </div>
        <div className="final-cta__actions">
          <a href="#" className="final-cta__link final-cta__link--primary">
            Apadrinhar agora<span>→</span>
          </a>
          <a href="#" className="final-cta__link final-cta__link--ghost">
            Quero doar<span>→</span>
          </a>
          <a href="#" className="final-cta__link final-cta__link--ghost">
            Ser voluntário<span>→</span>
          </a>
        </div>
      </section>

      <SiteFooter />

      <div className="bottom-bar">
        <div className="bottom-bar__mark">natal lumen</div>
        <div className="bottom-bar__meta">
          CNPJ 00.000.000/0001-00 · contato@natallumen.org.br · @natallumen
        </div>
      </div>
    </div>
  );
}
