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
  iconLeft,
  children,
  onClick,
  as = "button",
  href,
}) {
  const style = {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    justifyContent: "center",
    fontFamily: "var(--font-body)",
    fontWeight: 700,
    borderRadius: "var(--radius-pill)",
    border: "2px solid transparent",
    cursor: disabled ? "not-allowed" : "pointer",
    transition:
      "background-color .15s ease, color .15s ease, border-color .15s ease, transform .1s ease",
    textDecoration: "none",
    ...SIZES[size],
    ...VARIANTS[variant](disabled),
  };

  const Tag = as === "a" ? "a" : "button";
  const baseBackground = VARIANTS[variant](disabled).background;

  return (
    <Tag
      href={as === "a" ? href : undefined}
      disabled={as === "button" ? disabled : undefined}
      onClick={disabled ? undefined : onClick}
      style={style}
      onMouseEnter={(e) => {
        if (disabled) return;
        e.currentTarget.style.background = HOVER_BG[variant];
      }}
      onMouseLeave={(e) => {
        if (disabled) return;
        e.currentTarget.style.background = baseBackground;
      }}
    >
      {iconLeft}
      {children}
    </Tag>
  );
}
