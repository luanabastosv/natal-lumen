export default function DecorativeBackground({ variant = "sparkles", children }) {
  const sparkleStyle = {
    backgroundImage: "url(/images/sparkle-pattern.svg)",
    backgroundSize: "260px",
    backgroundRepeat: "repeat",
  };

  return (
    <div style={{ position: "relative", overflow: "hidden" }}>
      {variant === "sparkles" && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            ...sparkleStyle,
            opacity: 0.18,
            pointerEvents: "none",
          }}
        />
      )}
      {variant === "blob" && (
        <svg
          viewBox="0 0 400 400"
          style={{
            position: "absolute",
            top: "-15%",
            right: "-15%",
            width: "40%",
            zIndex: 0,
            pointerEvents: "none",
          }}
        >
          <path
            fill="var(--amber-100)"
            d="M320,60Q380,120,360,200Q340,280,260,330Q180,380,110,320Q40,260,50,170Q60,80,150,50Q240,20,320,60Z"
          />
        </svg>
      )}
      <div style={{ position: "relative", zIndex: 1 }}>{children}</div>
    </div>
  );
}
