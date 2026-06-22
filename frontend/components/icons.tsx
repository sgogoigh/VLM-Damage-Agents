import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function base({ size = 18, ...props }: IconProps) {
  return {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    ...props,
  };
}

export const CarIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M5 11l1.5-4A2 2 0 0 1 8.4 5.7h7.2a2 2 0 0 1 1.9 1.3L19 11" />
    <path d="M3 11h18v5a1 1 0 0 1-1 1h-1v1a1 1 0 0 1-2 0v-1H8v1a1 1 0 0 1-2 0v-1H5a1 1 0 0 1-1-1v-5z" />
    <circle cx="7.5" cy="14" r="1" />
    <circle cx="16.5" cy="14" r="1" />
  </svg>
);

export const LaptopIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <rect x="4" y="5" width="16" height="11" rx="1.5" />
    <path d="M2 19h20" />
  </svg>
);

export const PackageIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3z" />
    <path d="M4 7.5l8 4.5 8-4.5" />
    <path d="M12 21v-9" />
  </svg>
);

export const ShieldIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M12 3l7 3v5c0 4.5-3 7.8-7 9-4-1.2-7-4.5-7-9V6l7-3z" />
    <path d="M9 12l2 2 4-4" />
  </svg>
);

export const CheckIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M5 12l4.5 4.5L19 7" />
  </svg>
);

export const CrossIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M6 6l12 12M18 6L6 18" />
  </svg>
);

export const QuestionIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <circle cx="12" cy="12" r="9" />
    <path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.8.4-1 .8-1 1.7" />
    <path d="M12 17h.01" />
  </svg>
);

export const SendIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M4 12l16-7-7 16-2.5-6.5L4 12z" />
  </svg>
);

export const ClipIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M8 12l6-6a3 3 0 1 1 4 4l-8 8a5 5 0 1 1-7-7l7-7" />
  </svg>
);

export const SparkIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M18 6l-2.5 2.5M8.5 15.5L6 18" />
  </svg>
);

export const AlertIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M12 4l9 16H3l9-16z" />
    <path d="M12 10v4M12 17h.01" />
  </svg>
);

export const ImageIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <circle cx="8.5" cy="9.5" r="1.5" />
    <path d="M21 16l-5-5L5 20" />
  </svg>
);

export const UploadIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M12 16V4" />
    <path d="M7 9l5-5 5 5" />
    <path d="M5 16v2a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-2" />
  </svg>
);

export const RefreshIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M4 12a8 8 0 0 1 13.5-5.8L20 8" />
    <path d="M20 4v4h-4" />
    <path d="M20 12a8 8 0 0 1-13.5 5.8L4 16" />
    <path d="M4 20v-4h4" />
  </svg>
);

export const CloseIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M6 6l12 12M18 6L6 18" />
  </svg>
);

export const OBJECT_ICON = {
  car: CarIcon,
  laptop: LaptopIcon,
  package: PackageIcon,
} as const;
