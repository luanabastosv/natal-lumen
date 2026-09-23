import { useId } from "react";

export default function Badge({
  label = "APADRINHANDO SORRISOS",
  year = "2025",
  size = 160,
}) {
  const id = useId().replace(/:/g, "");

  return (
    <div style={{ width: size, height: size, position: "relative" }}>
      <svg viewBox="0 0 200 200" width={size} height={size}>
        <defs>
          <path id={`circleTop-${id}`} d="M 20,100 A 80,80 0 1 1 180,100" fill="none" />
          <path id={`circleBottom-${id}`} d="M 30,145 A 80,80 0 0 0 170,145" fill="none" />
        </defs>
        <circle cx="100" cy="100" r="98" fill="var(--navy-700)" />
        <circle
          cx="100"
          cy="100"
          r="98"
          fill="none"
          stroke="var(--amber-500)"
          strokeWidth="2"
          opacity="0.5"
        />
        <text
          fill="var(--cream-500)"
          fontFamily="var(--font-condensed)"
          fontWeight="800"
          fontSize="12"
          letterSpacing="1.5"
        >
          <textPath href={`#circleTop-${id}`} startOffset="50%" textAnchor="middle">
            {label}
          </textPath>
        </text>
        <text
          fill="var(--cream-500)"
          fontFamily="var(--font-condensed)"
          fontWeight="800"
          fontSize="12"
          letterSpacing="1.5"
        >
          <textPath href={`#circleBottom-${id}`} startOffset="50%" textAnchor="middle">
            NATAL LUMEN {year}
          </textPath>
        </text>
        <image
          href="/images/star-mascot-outline.svg"
          x="55"
          y="55"
          width="90"
          height="90"
          style={{ filter: "invert(1) brightness(2)" }}
        />
      </svg>
    </div>
  );
}
