// 原型中用到的 SVG 图标，统一封装。stroke 默认 currentColor。
import React from "react";

type P = { size?: number; color?: string; fill?: string; sw?: number; style?: React.CSSProperties };

const Svg = ({ size = 18, children, fill = "none", stroke, sw = 1.8, style }: any) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill={fill} stroke={stroke} strokeWidth={sw} style={style}>
    {children}
  </svg>
);

export const Bolt = ({ size = 20, fill = "#fff" }: P) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <path d="M13 2L4 14h6l-1 8 9-12h-6l1-8z" fill={fill} />
  </svg>
);

export const Spark = ({ size = 14, fill = "#A78BFA", style }: P) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill={fill} style={style}>
    <path d="M12 2l1.6 4.8L18 8.4l-4.4 1.6L12 15l-1.6-5L6 8.4l4.4-1.6z" />
  </svg>
);

export const Feed = ({ size, color = "currentColor" }: P) => (
  <Svg size={size} stroke={color} sw={1.8}>
    <rect x="3" y="4" width="18" height="4" rx="1.5" />
    <rect x="3" y="11" width="11" height="3" rx="1.5" />
    <rect x="3" y="17" width="14" height="3" rx="1.5" />
  </Svg>
);

export const Book = ({ size, color = "currentColor" }: P) => (
  <Svg size={size} stroke={color}>
    <path d="M4 5a2 2 0 0 1 2-2h12v18H6a2 2 0 0 1-2-2z" />
    <path d="M9 3v18" />
  </Svg>
);

export const GraphIcon = ({ size, color = "currentColor" }: P) => (
  <Svg size={size} stroke={color}>
    <circle cx="6" cy="6" r="2.5" />
    <circle cx="18" cy="7" r="2.5" />
    <circle cx="12" cy="18" r="2.5" />
    <path d="M8 7l8 .5M7.5 8.5L11 16M16.5 9L13 16" />
  </Svg>
);

export const Bell = ({ size, color = "currentColor" }: P) => (
  <Svg size={size} stroke={color}>
    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
    <path d="M10.5 21a1.5 1.5 0 0 0 3 0" />
  </Svg>
);

export const Globe = ({ size, color = "currentColor" }: P) => (
  <Svg size={size} stroke={color}>
    <circle cx="12" cy="12" r="9" />
    <path d="M3 12h18M12 3a14 14 0 0 1 0 18 14 14 0 0 1 0-18z" />
  </Svg>
);

export const Gear = ({ size, color = "currentColor" }: P) => (
  <Svg size={size} stroke={color}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1V21a2 2 0 0 1-4 0v-.1A1.6 1.6 0 0 0 7 19.4a1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0-1.1-2.7H1a2 2 0 0 1 0-4h.1A1.6 1.6 0 0 0 4.6 7a1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V1a2 2 0 0 1 4 0v.1a1.6 1.6 0 0 0 2.7 1.1l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H23a2 2 0 0 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z" />
  </Svg>
);

export const Search = ({ size = 16, color = "#5E6A82" }: P) => (
  <Svg size={size} stroke={color} sw={2}>
    <circle cx="11" cy="11" r="7" />
    <path d="m21 21-4.3-4.3" />
  </Svg>
);

export const Plus = ({ size = 14, color = "#0A0E17" }: P) => (
  <Svg size={size} stroke={color} sw={2.4}>
    <path d="M12 5v14M5 12h14" />
  </Svg>
);

export const Check = ({ size = 14, color = "currentColor", sw = 2.6 }: P & { sw?: number }) => (
  <Svg size={size} stroke={color} sw={sw}>
    <path d="M20 6 9 17l-5-5" />
  </Svg>
);

export const Link = ({ size = 12, color = "#3B9EFF" }: P) => (
  <Svg size={size} stroke={color} sw={2}>
    <path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1.5 1.5" />
    <path d="M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1.5-1.5" />
  </Svg>
);

export const Send = ({ size = 15, color = "#0A0E17" }: P) => (
  <Svg size={size} stroke={color} sw={2.4}>
    <path d="m22 2-7 20-4-9-9-4z" />
  </Svg>
);

export const X = ({ size = 12, color = "currentColor", onClick, style }: P & { onClick?: () => void }) => (
  <svg onClick={onClick} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2.2} style={{ cursor: onClick ? "pointer" : undefined, ...style }}>
    <path d="M18 6 6 18M6 6l12 12" />
  </svg>
);

export const Sort = ({ size = 14, color = "currentColor" }: P) => (
  <Svg size={size} stroke={color}>
    <path d="M4 6h16M7 12h10M10 18h4" />
  </Svg>
);

export const Triangle = ({ size = 18, color = "#FBBF24" }: P) => (
  <Svg size={size} stroke={color}>
    <path d="M10.3 3.6 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.6a2 2 0 0 0-3.4 0z" />
    <path d="M12 9v4M12 17h.01" />
  </Svg>
);

export const Mail = ({ size = 18, color = "#6B7689" }: P) => (
  <Svg size={size} stroke={color}>
    <rect x="2" y="4" width="20" height="16" rx="2" />
    <path d="m2 7 10 6 10-6" />
  </Svg>
);

export const Doc = ({ size = 18, color = "currentColor" }: P) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.7}>
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <path d="M14 2v6h6M9 13h6M9 17h6" />
  </svg>
);
