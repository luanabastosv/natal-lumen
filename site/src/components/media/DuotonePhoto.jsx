import { useId } from "react";

const TONES = {
  navy: "#153377",
  amber: "#ffb000",
};

const RADII = {
  none: 0,
  md: "var(--radius-md)",
  lg: "var(--radius-lg)",
};

function hexPart(hex, i) {
  const n = parseInt(hex.slice(1 + i * 2, 3 + i * 2), 16);
  return (n / 255).toFixed(2);
}

export default function DuotonePhoto({ src, alt = "", tone = "navy", radius = "md" }) {
  const id = useId().replace(/:/g, "");
  const color = TONES[tone];

  return (
    <div
      style={{
        position: "relative",
        overflow: "hidden",
        borderRadius: RADII[radius],
        lineHeight: 0,
      }}
    >
      <svg width="0" height="0" style={{ position: "absolute" }}>
        <filter id={`duotone-${id}`}>
          <feColorMatrix
            type="matrix"
            values="0.33 0.33 0.33 0 0  0.33 0.33 0.33 0 0  0.33 0.33 0.33 0 0  0 0 0 1 0"
          />
          <feComponentTransfer>
            <feFuncR type="table" tableValues={`${hexPart(color, 0)} 1`} />
            <feFuncG type="table" tableValues={`${hexPart(color, 1)} 1`} />
            <feFuncB type="table" tableValues={`${hexPart(color, 2)} 1`} />
          </feComponentTransfer>
        </filter>
      </svg>
      <img
        src={src}
        alt={alt}
        style={{ width: "100%", display: "block", filter: `url(#duotone-${id})` }}
      />
    </div>
  );
}
