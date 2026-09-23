// Portado do site (site/src/components/core/Button.jsx), mantendo as mesmas
// variantes e tamanhos. Acrescentado: type, largura total e estado "carregando",
// que uma aplicacao com formularios precisa e um site institucional nao.

const SIZES = {
  sm: { padding: "10px 18px", fontSize: 14 },
  md: { padding: "14px 28px", fontSize: 16 },
  lg: { padding: "18px 36px", fontSize: 18 },
};

const VARIANTS = {
  primary: (disabled) => ({
    background: disabled ? "var(--color-disabled-bg)" : "var(--color-cta)",
    color: disabled ? "var(--color-disabled-text)" : "var(--navy-900)",
  }),
  secondary: (disabled) => ({
    background: disabled ? "var(--color-disabled-bg)" : "var(--color-primary)",
    color: disabled ? "var(--color-disabled-text)" : "var(--white)",
  }),
  ghost: (disabled) => ({
    background: "transparent",
    borderColor: disabled ? "var(--color-disabled-bg)" : "var(--color-primary)",
    color: disabled ? "var(--color-disabled-text)" : "var(--color-primary)",
  }),
};

const HOVER_BG = {
  primary: "var(--color-cta-hover)",
  secondary: "var(--color-primary-hover)",
  ghost: "var(--navy-100)",
};

export default function Button({
  variant = "primary",
  size = "md",
  disabled = false,
  carregando = false,
  larguraTotal = false,
  type = "button",
  iconLeft,
  children,
  onClick,
  as = "button",
  href,
}) {
  const inativo = disabled || carregando;

  const style = {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    justifyContent: "center",
    fontFamily: "var(--font-body)",
    fontWeight: 700,
    borderRadius: "var(--radius-pill)",
    border: "2px solid transparent",
    cursor: inativo ? "not-allowed" : "pointer",
    transition:
      "background-color .15s ease, color .15s ease, border-color .15s ease, transform .1s ease",
    textDecoration: "none",
    width: larguraTotal ? "100%" : undefined,
    ...SIZES[size],
    ...VARIANTS[variant](inativo),
  };

  const Tag = as === "a" ? "a" : "button";
  const fundoBase = VARIANTS[variant](inativo).background;

  return (
    <Tag
      href={as === "a" ? href : undefined}
      type={as === "button" ? type : undefined}
      disabled={as === "button" ? inativo : undefined}
      aria-busy={carregando || undefined}
      onClick={inativo ? undefined : onClick}
      style={style}
      onMouseEnter={(e) => {
        if (inativo) return;
        e.currentTarget.style.background = HOVER_BG[variant];
      }}
      onMouseLeave={(e) => {
        if (inativo) return;
        e.currentTarget.style.background = fundoBase;
      }}
    >
      {iconLeft}
      {children}
    </Tag>
  );
}
