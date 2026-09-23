const TONES = {
  amber: {
    background: "var(--amber-500)",
    color: "var(--navy-900)",
    border: "1.5px solid transparent",
  },
  "amber-outline": {
    background: "var(--white)",
    color: "var(--amber-700)",
    border: "1.5px solid var(--amber-500)",
  },
  navy: {
    background: "var(--navy-700)",
    color: "var(--cream-500)",
    border: "1.5px solid transparent",
  },
  white: {
    background: "var(--white)",
    color: "var(--navy-700)",
    border: "var(--stroke-hairline) solid var(--stroke-hairline-color)",
  },
};

export default function CampaignPill({
  children = "APADRINHANDO SORRISOS",
  tone = "amber",
  rotate = -6,
}) {
  return (
    <div
      style={{
        display: "inline-block",
        transform: `rotate(${rotate}deg)`,
        padding: "10px 28px",
        borderRadius: "var(--radius-pill)",
        fontFamily: "var(--font-condensed)",
        fontWeight: 800,
        fontSize: 15,
        letterSpacing: ".08em",
        whiteSpace: "nowrap",
        boxShadow: "var(--shadow-sm)",
        ...TONES[tone],
      }}
    >
      {children}
    </div>
  );
}
