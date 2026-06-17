import type { DesignSystem, Page, SlideMeta, SlideTransition } from '@open-slide/core';
import type { CSSProperties, ReactNode } from 'react';

export const design: DesignSystem = {
  palette: {
    bg: '#f7f6f2',
    text: '#111315',
    accent: '#16a34a',
  },
  fonts: {
    display:
      'Inter, "SF Pro Display", ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif',
    body:
      'Inter, "SF Pro Text", ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif',
  },
  typeScale: {
    hero: 156,
    body: 36,
  },
  radius: 8,
};

const c = {
  bg: '#f7f6f2',
  paper: '#ffffff',
  paperWarm: '#fbfaf7',
  ink: '#111315',
  soft: '#565c62',
  muted: '#8b9197',
  line: '#dadde0',
  lineSoft: '#eceef0',
  green: '#16a34a',
  greenSoft: '#dcfce7',
  red: '#dc2626',
  redSoft: '#fee2e2',
  amber: '#d97706',
  amberSoft: '#fef3c7',
  blue: '#0369a1',
  blueSoft: '#e0f2fe',
  purple: '#7c3aed',
  purpleSoft: '#ede9fe',
};

const EASE = 'cubic-bezier(0.25, 0.1, 0.25, 1)';
const OPENING_TIMELINE = '15s';
const AGENTS_TIMELINE = '11s';
const PRODUCT_MARK_TIMELINE = '12s';
const RELEASE_CHECK_TIMELINE = '15s';
const EVIDENCE_TIMELINE = '15s';
const DEMO_TRANSITION_TIMELINE = '6s';
const CLOSING_TOTAL_HOLD = '8s';
const FINAL_TOTAL_HOLD = '7s';

const openingStyles = `
  @keyframes v2-bg-in {
    0% { opacity: 0; }
    6.7% { opacity: 1; }
    100% { opacity: 1; }
  }

  @keyframes v2-line1 {
    0%, 8% { opacity: 0; }
    12% { opacity: 1; }
    34.7% { opacity: 1; }
    38.7% { opacity: 0; }
    100% { opacity: 0; }
  }

  @keyframes v2-line2 {
    0%, 41.3% { opacity: 0; }
    46% { opacity: 1; }
    100% { opacity: 1; }
  }

  @keyframes v2-zoom {
    0%, 48% { transform: scale(1); }
    100% { transform: scale(1.1); }
  }

  .v2-opening-bg {
    opacity: 0;
    animation: v2-bg-in ${OPENING_TIMELINE} ${EASE} forwards;
  }

  .v2-opening-stage {
    animation: v2-zoom ${OPENING_TIMELINE} ${EASE} forwards;
    transform-origin: center center;
  }

  .v2-opening-line1 {
    opacity: 0;
    animation: v2-line1 ${OPENING_TIMELINE} ${EASE} forwards;
  }

  .v2-opening-line2 {
    opacity: 0;
    animation: v2-line2 ${OPENING_TIMELINE} ${EASE} forwards;
  }
`;

const agentsStyles = `
  @keyframes v2-agents-title {
    0%, 7.3% { opacity: 0; }
    12.7% { opacity: 1; }
    100% { opacity: 1; }
  }

  @keyframes v2-agents-chip-a {
    0%, 29.1% { opacity: 0; transform: translateY(18px); }
    34.5% { opacity: 1; transform: translateY(0); }
    100% { opacity: 1; transform: translateY(0); }
  }

  @keyframes v2-agents-chip-b {
    0%, 39.1% { opacity: 0; transform: translateY(18px); }
    44.5% { opacity: 1; transform: translateY(0); }
    100% { opacity: 1; transform: translateY(0); }
  }

  @keyframes v2-agents-chip-c {
    0%, 49.1% { opacity: 0; transform: translateY(18px); }
    54.5% { opacity: 1; transform: translateY(0); }
    100% { opacity: 1; transform: translateY(0); }
  }

  .v2-agents-title {
    opacity: 0;
    animation: v2-agents-title ${AGENTS_TIMELINE} ${EASE} forwards;
  }

  .v2-agents-chip-a {
    opacity: 0;
    animation: v2-agents-chip-a ${AGENTS_TIMELINE} ${EASE} forwards;
  }

  .v2-agents-chip-b {
    opacity: 0;
    animation: v2-agents-chip-b ${AGENTS_TIMELINE} ${EASE} forwards;
  }

  .v2-agents-chip-c {
    opacity: 0;
    animation: v2-agents-chip-c ${AGENTS_TIMELINE} ${EASE} forwards;
  }
`;

const productStyles = `
  @keyframes v2-pm-lane-card {
    0% { opacity: 0; transform: translateY(14px); }
    6.7% { opacity: 1; transform: translateY(0); }
    100% { opacity: 1; transform: translateY(0); }
  }

  @keyframes v2-pm-lane-line {
    0%, 8.3% { transform: scaleX(0); }
    16.7% { transform: scaleX(1); }
    100% { transform: scaleX(1); }
  }

  @keyframes v2-pm-connector-line {
    0%, 17.5% { transform: scaleX(0); }
    25% { transform: scaleX(1); }
    100% { transform: scaleX(1); }
  }

  @keyframes v2-pm-arrow {
    0%, 25.8% { opacity: 0; }
    28.3% { opacity: 1; }
    100% { opacity: 1; }
  }

  @keyframes v2-pm-brand {
    0%, 30% { opacity: 0; transform: translateY(14px); }
    36.7% { opacity: 1; transform: translateY(0); }
    100% { opacity: 1; transform: translateY(0); }
  }

  @keyframes v2-pm-tagline {
    0%, 40% { opacity: 0; transform: translateY(14px); }
    46.7% { opacity: 1; transform: translateY(0); }
    100% { opacity: 1; transform: translateY(0); }
  }

  @keyframes v2-pm-question {
    0%, 50% { opacity: 0; transform: translateY(14px); }
    56.7% { opacity: 1; transform: translateY(0); }
    100% { opacity: 1; transform: translateY(0); }
  }

  @keyframes v2-gate-pulse-ring {
    0%, 100% { box-shadow: 0 0 0 0 rgba(21, 128, 61, 0); }
    50% { box-shadow: 0 0 0 14px rgba(21, 128, 61, 0.26); }
  }

  .v2-up {
    opacity: 0;
    animation: v2-pm-lane-card ${PRODUCT_MARK_TIMELINE} ${EASE} forwards;
  }

  .v2-line-draw {
    transform-origin: left center;
    transform: scaleX(0);
  }

  .v2-line-draw-lane {
    animation: v2-pm-lane-line ${PRODUCT_MARK_TIMELINE} ${EASE} forwards;
  }

  .v2-line-draw-connector {
    animation: v2-pm-connector-line ${PRODUCT_MARK_TIMELINE} ${EASE} forwards;
  }

  .v2-gate-pulse {
    animation: v2-gate-pulse-ring 1.8s ease-in-out infinite;
    animation-delay: 0.9s;
  }

  .v2-connector {
    display: flex;
    align-items: center;
    flex-shrink: 0;
  }

  .v2-connector-arrow {
    opacity: 0;
    flex-shrink: 0;
    animation: v2-pm-arrow ${PRODUCT_MARK_TIMELINE} ${EASE} forwards;
  }

  .v2-product-brand {
    opacity: 0;
    animation: v2-pm-brand ${PRODUCT_MARK_TIMELINE} ${EASE} forwards;
  }

  .v2-product-tagline {
    opacity: 0;
    animation: v2-pm-tagline ${PRODUCT_MARK_TIMELINE} ${EASE} forwards;
  }

  .v2-product-question {
    opacity: 0;
    animation: v2-pm-question ${PRODUCT_MARK_TIMELINE} ${EASE} forwards;
  }
`;

const releaseCheckStyles = `
  @keyframes v2-rc-eyebrow {
    0%, 6.7% { opacity: 0; }
    10% { opacity: 1; }
    100% { opacity: 1; }
  }

  @keyframes v2-rc-card-a {
    0%, 14.7% { opacity: 0; transform: translateY(12px); }
    20% { opacity: 1; transform: translateY(0); }
    100% { opacity: 1; transform: translateY(0); }
  }

  @keyframes v2-rc-card-b {
    0%, 26.7% { opacity: 0; transform: translateY(12px); }
    32% { opacity: 1; transform: translateY(0); }
    100% { opacity: 1; transform: translateY(0); }
  }

  @keyframes v2-rc-card-c {
    0%, 38.7% { opacity: 0; transform: translateY(12px); }
    44% { opacity: 1; transform: translateY(0); }
    100% { opacity: 1; transform: translateY(0); }
  }

  @keyframes v2-rc-card-d {
    0%, 50.7% { opacity: 0; transform: translateY(12px) scale(1); }
    56% { opacity: 1; transform: translateY(0) scale(1); }
    80% { opacity: 1; transform: translateY(0) scale(1); }
    84% { opacity: 1; transform: translateY(0) scale(1.045); }
    100% { opacity: 1; transform: translateY(0) scale(1.035); }
  }

  @keyframes v2-rc-arrows {
    0%, 62.7% { opacity: 0; }
    68% { opacity: 1; }
    100% { opacity: 1; }
  }

  @keyframes v2-rc-footer {
    0%, 70.7% { opacity: 0; }
    74.7% { opacity: 1; }
    100% { opacity: 1; }
  }

  .v2-rc-eyebrow {
    opacity: 0;
    animation: v2-rc-eyebrow ${RELEASE_CHECK_TIMELINE} ${EASE} forwards;
  }

  .v2-rc-card-a {
    opacity: 0;
    animation: v2-rc-card-a ${RELEASE_CHECK_TIMELINE} ${EASE} forwards;
  }

  .v2-rc-card-b {
    opacity: 0;
    animation: v2-rc-card-b ${RELEASE_CHECK_TIMELINE} ${EASE} forwards;
  }

  .v2-rc-card-c {
    opacity: 0;
    animation: v2-rc-card-c ${RELEASE_CHECK_TIMELINE} ${EASE} forwards;
  }

  .v2-rc-card-d {
    opacity: 0;
    animation: v2-rc-card-d ${RELEASE_CHECK_TIMELINE} ${EASE} forwards;
    transform-origin: center center;
  }

  .v2-rc-arrows {
    opacity: 0;
    animation: v2-rc-arrows ${RELEASE_CHECK_TIMELINE} ${EASE} forwards;
  }

  .v2-rc-footer {
    opacity: 0;
    animation: v2-rc-footer ${RELEASE_CHECK_TIMELINE} ${EASE} forwards;
  }
`;

const demoTransitionStyles = `
  @keyframes v2-demo-frame {
    0% { opacity: 0; }
    6.7% { opacity: 1; }
    100% { opacity: 1; }
  }

  @keyframes v2-demo-title {
    0%, 13.3% { opacity: 0; }
    21.7% { opacity: 1; }
    100% { opacity: 1; }
  }

  @keyframes v2-demo-subtitle {
    0%, 36.7% { opacity: 0; }
    46.7% { opacity: 1; }
    100% { opacity: 1; }
  }

  .v2-demo-frame {
    opacity: 0;
    animation: v2-demo-frame ${DEMO_TRANSITION_TIMELINE} ${EASE} forwards;
  }

  .v2-demo-title {
    opacity: 0;
    animation: v2-demo-title ${DEMO_TRANSITION_TIMELINE} ${EASE} forwards;
  }

  .v2-demo-subtitle {
    opacity: 0;
    animation: v2-demo-subtitle ${DEMO_TRANSITION_TIMELINE} ${EASE} forwards;
  }
`;

const evidenceStyles = `
  @keyframes v2-ep-eyebrow {
    0%, 5.3% { opacity: 0; }
    8% { opacity: 1; }
    100% { opacity: 1; }
  }

  @keyframes v2-ep-left {
    0%, 8% { opacity: 0; transform: translateY(12px); }
    13.3% { opacity: 1; transform: translateY(0); }
    100% { opacity: 1; transform: translateY(0); }
  }

  @keyframes v2-ep-middle {
    0%, 21.3% { opacity: 0; transform: translateY(12px); }
    28% { opacity: 1; transform: translateY(0); }
    100% { opacity: 1; transform: translateY(0); }
  }

  @keyframes v2-ep-right {
    0%, 41.3% { opacity: 0; transform: translateY(12px); }
    48% { opacity: 1; transform: translateY(0); }
    100% { opacity: 1; transform: translateY(0); }
  }

  @keyframes v2-ep-arrows {
    0%, 56% { opacity: 0; }
    63.3% { opacity: 1; }
    100% { opacity: 1; }
  }

  .v2-ep-eyebrow {
    opacity: 0;
    animation: v2-ep-eyebrow ${EVIDENCE_TIMELINE} ${EASE} forwards;
  }

  .v2-ep-left {
    opacity: 0;
    animation: v2-ep-left ${EVIDENCE_TIMELINE} ${EASE} forwards;
  }

  .v2-ep-mid-a,
  .v2-ep-mid-b {
    opacity: 0;
    animation: v2-ep-middle ${EVIDENCE_TIMELINE} ${EASE} forwards;
  }

  .v2-ep-right {
    opacity: 0;
    animation: v2-ep-right ${EVIDENCE_TIMELINE} ${EASE} forwards;
  }

  .v2-ep-arrows {
    opacity: 0;
    animation: v2-ep-arrows ${EVIDENCE_TIMELINE} ${EASE} forwards;
  }
`;

const CLOSING_EASE = 'cubic-bezier(0.2, 0.7, 0.2, 1)';

const closingStyles = `
  @keyframes v2-closing-up {
    from { opacity: 0; transform: translateY(18px); }
    to { opacity: 1; transform: translateY(0); }
  }

  @keyframes v2-closing-hold {
    0%, 70% { opacity: 1; }
    100% { opacity: 1; }
  }

  @keyframes v2-final-hold {
    0%, 18.6% { opacity: 1; }
    100% { opacity: 1; }
  }

  .v2-closing-stage {
    animation: v2-closing-hold ${CLOSING_TOTAL_HOLD} linear forwards;
  }

  .v2-final-stage {
    animation: v2-final-hold ${FINAL_TOTAL_HOLD} linear forwards;
  }

  .v2-up-closing {
    opacity: 0;
    animation: v2-closing-up 1.4s ${CLOSING_EASE} forwards;
  }

  .v2-up-final-logo {
    opacity: 0;
    animation: v2-closing-up 1.04s ${CLOSING_EASE} forwards;
  }

  .v2-final-up {
    opacity: 0;
    animation: v2-closing-up 0.78s ${CLOSING_EASE} forwards;
  }
`;

const motionStyles = `
  @media (prefers-reduced-motion: reduce) {
    .v2-opening-bg,
    .v2-opening-line1,
    .v2-opening-line2,
    .v2-opening-stage,
    .v2-agents-title,
    .v2-agents-chip-a,
    .v2-agents-chip-b,
    .v2-agents-chip-c,
    .v2-up,
    .v2-line-draw,
    .v2-product-brand,
    .v2-product-tagline,
    .v2-product-question,
    .v2-connector-arrow,
    .v2-gate-pulse,
    .v2-rc-eyebrow,
    .v2-rc-card-a,
    .v2-rc-card-b,
    .v2-rc-card-c,
    .v2-rc-card-d,
    .v2-rc-arrows,
    .v2-rc-footer,
    .v2-ep-eyebrow,
    .v2-ep-left,
    .v2-ep-mid-a,
    .v2-ep-mid-b,
    .v2-ep-right,
    .v2-ep-arrows,
    .v2-demo-frame,
    .v2-demo-title,
    .v2-demo-subtitle,
    .v2-closing-stage,
    .v2-final-stage,
    .v2-up-closing,
    .v2-up-final-logo,
    .v2-final-up {
      animation: none !important;
      opacity: 1 !important;
      transform: none !important;
    }
    .v2-opening-line1 { display: none !important; }
  }
`;

const OpeningStyles = () => <style>{openingStyles}</style>;
const AgentsStyles = () => <style>{agentsStyles + motionStyles}</style>;
const ProductStyles = () => <style>{productStyles + motionStyles}</style>;
const ReleaseCheckStyles = () => <style>{releaseCheckStyles + motionStyles}</style>;
const EvidencePipelineStyles = () => <style>{evidenceStyles + motionStyles}</style>;
const DemoTransitionStyles = () => <style>{demoTransitionStyles + motionStyles}</style>;
const ClosingStyles = () => <style>{closingStyles + motionStyles}</style>;

const fill: CSSProperties = {
  width: '100%',
  height: '100%',
  position: 'relative',
  overflow: 'hidden',
  background: c.bg,
  color: c.ink,
  fontFamily: 'var(--osd-font-body)',
  letterSpacing: 0,
};

const heroLine: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--osd-font-display)',
  fontSize: 112,
  lineHeight: 1.02,
  fontWeight: 860,
  letterSpacing: 0,
  textAlign: 'center',
  maxWidth: 1560,
};

const agentsChip: CSSProperties = {
  padding: '17px 34px',
  borderRadius: 999,
  border: `1px solid ${c.line}`,
  background: c.paperWarm,
  fontSize: 36,
  fontWeight: 750,
  color: c.soft,
  letterSpacing: 0,
  lineHeight: 1,
  whiteSpace: 'nowrap',
};

const card: CSSProperties = {
  background: c.paper,
  border: `1px solid ${c.line}`,
  borderRadius: 'var(--osd-radius)',
  boxShadow: '0 24px 70px -46px rgba(17, 19, 21, 0.38)',
};

const flowCard: CSSProperties = {
  ...card,
  width: 390,
  minHeight: 300,
  padding: '44px 36px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  position: 'relative',
  flexShrink: 0,
};

const flowCardTitle: CSSProperties = {
  margin: 0,
  fontFamily: 'var(--osd-font-display)',
  fontSize: 54,
  lineHeight: 1.15,
  fontWeight: 850,
  letterSpacing: 0,
  textAlign: 'center',
  color: c.ink,
};

const TONE_BORDER = 3;

const toneFlowCard = (
  tone: 'red' | 'purple' | 'green',
  overrides: CSSProperties = {},
): CSSProperties => {
  const color = tone === 'red' ? c.red : tone === 'purple' ? c.purple : c.green;
  return {
    ...flowCard,
    ...overrides,
    border: `${TONE_BORDER}px solid ${color}`,
  };
};

const agentFlowCard: CSSProperties = {
  ...flowCard,
  minHeight: 228,
};

const EP_LINK_STROKE = 1.5;
const EP_AGENT_GAP = 24;
const EP_AGENT_STACK_H = agentFlowCard.minHeight! * 2 + EP_AGENT_GAP;
const EP_AGENT_MID_Y = agentFlowCard.minHeight! / 2;
const EP_AGENT_BOT_Y = agentFlowCard.minHeight! + EP_AGENT_GAP + EP_AGENT_MID_Y;
const EP_HUB_Y = EP_AGENT_STACK_H / 2;

const EpArrowMarker = ({ id }: { id: string }) => (
  <marker
    id={id}
    markerWidth="7"
    markerHeight="7"
    refX="6"
    refY="3.5"
    orient="auto"
    markerUnits="strokeWidth"
  >
    <path d="M0 0 L7 3.5 L0 7 Z" fill={c.muted} />
  </marker>
);

const ForkToAgents = ({ className }: { className?: string }) => (
  <svg
    className={className}
    width={96}
    height={EP_AGENT_STACK_H}
    viewBox={`0 0 96 ${EP_AGENT_STACK_H}`}
    fill="none"
    aria-hidden="true"
    style={{ flexShrink: 0, overflow: 'visible' }}
  >
    <defs>
      <EpArrowMarker id="v2-ep-arrow-ab" />
    </defs>
    <path
      d={`M0 ${EP_HUB_Y} H44 V${EP_AGENT_MID_Y} H88`}
      stroke={c.muted}
      strokeWidth={EP_LINK_STROKE}
      strokeLinecap="round"
      strokeLinejoin="round"
      markerEnd="url(#v2-ep-arrow-ab)"
    />
    <path
      d={`M0 ${EP_HUB_Y} H44 V${EP_AGENT_BOT_Y} H88`}
      stroke={c.muted}
      strokeWidth={EP_LINK_STROKE}
      strokeLinecap="round"
      strokeLinejoin="round"
      markerEnd="url(#v2-ep-arrow-ab)"
    />
  </svg>
);

const MergeToCandidates = ({ className }: { className?: string }) => (
  <svg
    className={className}
    width={96}
    height={EP_AGENT_STACK_H}
    viewBox={`0 0 96 ${EP_AGENT_STACK_H}`}
    fill="none"
    aria-hidden="true"
    style={{ flexShrink: 0, overflow: 'visible' }}
  >
    <defs>
      <EpArrowMarker id="v2-ep-arrow-bc" />
    </defs>
    <path
      d={`M0 ${EP_AGENT_MID_Y} H44 V${EP_HUB_Y} H88`}
      stroke={c.muted}
      strokeWidth={EP_LINK_STROKE}
      strokeLinecap="round"
      strokeLinejoin="round"
      markerEnd="url(#v2-ep-arrow-bc)"
    />
    <path
      d={`M0 ${EP_AGENT_BOT_Y} H44 V${EP_HUB_Y} H88`}
      stroke={c.muted}
      strokeWidth={EP_LINK_STROKE}
      strokeLinecap="round"
      strokeLinejoin="round"
      markerEnd="url(#v2-ep-arrow-bc)"
    />
  </svg>
);

const FlowArrow = ({ className = 'v2-rc-arrows' }: { className?: string }) => (
  <div
    className={className}
    style={{
      width: 56,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flexShrink: 0,
    }}
  >
    <svg width="48" height="16" viewBox="0 0 36 12" fill="none" aria-hidden="true">
      <path d="M0 6H28" stroke={c.muted} strokeWidth="1.5" strokeLinecap="round" />
      <path
        d="M28 6L32 2V10L28 6Z"
        fill={c.muted}
        stroke={c.muted}
        strokeWidth="1"
        strokeLinejoin="round"
      />
    </svg>
  </div>
);

const BigTitle = ({
  children,
  size = 132,
  maxWidth = 1280,
  style,
  className,
}: {
  children: ReactNode;
  size?: number;
  maxWidth?: number;
  style?: CSSProperties;
  className?: string;
}) => (
  <h1
    className={className}
    style={{
      margin: 0,
      maxWidth,
      fontFamily: 'var(--osd-font-display)',
      fontSize: size,
      lineHeight: 1.02,
      fontWeight: 860,
      letterSpacing: 0,
      ...style,
    }}
  >
    {children}
  </h1>
);

const Body = ({
  children,
  maxWidth = 900,
  color = c.soft,
  size = 38,
  style,
  className,
}: {
  children: ReactNode;
  maxWidth?: number;
  color?: string;
  size?: number;
  style?: CSSProperties;
  className?: string;
}) => (
  <p
    className={className}
    style={{
      margin: 0,
      maxWidth,
      color,
      fontSize: size,
      lineHeight: 1.35,
      fontWeight: 520,
      ...style,
    }}
  >
    {children}
  </p>
);

const Mark = ({ size = 28 }: { size?: number }) => (
  <span
    style={{
      width: size,
      height: size,
      borderRadius: Math.max(3, size / 7),
      background: c.green,
      display: 'inline-block',
      boxShadow: `0 0 0 1px rgba(0,0,0,0.04), 0 12px 28px -18px ${c.green}`,
    }}
  />
);

const LaneStep = ({
  label,
  emphasize = false,
  pulse = false,
}: {
  label: string;
  emphasize?: boolean;
  pulse?: boolean;
}) => (
  <div style={{ position: 'relative', display: 'grid', justifyItems: 'center', gap: 19, zIndex: 1 }}>
    <span
      className={pulse ? 'v2-gate-pulse' : undefined}
      style={{
        width: 62,
        height: 62,
        borderRadius: '50%',
        background: c.greenSoft,
        border: `6px solid ${pulse ? '#15803d' : c.green}`,
        display: 'block',
        flexShrink: 0,
      }}
    />
    <span
      style={{
        fontSize: 29,
        fontWeight: emphasize ? 820 : 760,
        color: emphasize ? c.ink : c.muted,
      }}
    >
      {label}
    </span>
  </div>
);

const Opening: Page = () => (
  <div style={fill}>
    <OpeningStyles />
    <style>{motionStyles}</style>
    <div
      className="v2-opening-bg"
      style={{
        ...fill,
        background: c.bg,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '0 120px',
      }}
    >
      <div
        className="v2-opening-stage"
        style={{
          position: 'relative',
          width: '100%',
          height: 248,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <p className="v2-opening-line1" style={{ ...heroLine, position: 'absolute', color: c.ink }}>
          Wrong answers became
          <br />
          business risk.
        </p>
        <p
          className="v2-opening-line2"
          style={{ ...heroLine, position: 'absolute', color: c.ink, fontWeight: 820 }}
        >
          <span style={{ color: c.red }}>Wrong actions</span> become
          <br />
          <span style={{ fontWeight: 880 }}>release risk</span>.
        </p>
      </div>
    </div>
  </div>
);

const AgentsAct: Page = () => (
  <div
    style={{
      ...fill,
      background: c.bg,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '0 120px',
    }}
  >
    <AgentsStyles />
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 56,
      }}
    >
      <h1
        className="v2-agents-title"
        style={{
          margin: 0,
          fontFamily: 'var(--osd-font-display)',
          fontSize: 112,
          lineHeight: 1.02,
          fontWeight: 860,
          letterSpacing: 0,
          textAlign: 'center',
          color: c.ink,
        }}
      >
        Agents can now act.
      </h1>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 24 }}>
        <div className="v2-agents-chip-a" style={agentsChip}>
          Call tools
        </div>
        <div className="v2-agents-chip-b" style={agentsChip}>
          Trigger workflows
        </div>
        <div className="v2-agents-chip-c" style={agentsChip}>
          Touch internal systems
        </div>
      </div>
    </div>
  </div>
);

const ProductMark: Page = () => (
  <div
    style={{
      ...fill,
      background: c.bg,
      display: 'grid',
      gridTemplateColumns: '1fr auto 1fr',
      alignItems: 'center',
      padding: '115px 134px',
      gap: 48,
      fontFamily: 'var(--osd-font-body)',
      color: c.ink,
    }}
  >
    <ProductStyles />
    <div
      className="v2-up"
      style={{
        ...card,
        width: '100%',
        maxWidth: 816,
        padding: '58px 53px',
        justifySelf: 'end',
      }}
    >
      <div
        style={{
          position: 'relative',
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          alignItems: 'start',
          justifyItems: 'center',
          paddingTop: 14,
        }}
      >
        <div
          className="v2-line-draw v2-line-draw-lane"
          style={{
            position: 'absolute',
            left: 62,
            right: 62,
            top: 43,
            height: 5,
            background: c.green,
          }}
        />
        <LaneStep label="Build" />
        <LaneStep label="Test" />
        <LaneStep label="Gate" emphasize pulse />
        <LaneStep label="Ship" />
      </div>
    </div>
    <div className="v2-connector">
      <div
        className="v2-line-draw v2-line-draw-connector"
        style={{ width: 115, height: 5, background: c.green, flexShrink: 0 }}
      />
      <div
        className="v2-connector-arrow"
        style={{
          width: 0,
          height: 0,
          borderTop: '12px solid transparent',
          borderBottom: '12px solid transparent',
          borderLeft: `17px solid ${c.green}`,
        }}
      />
    </div>
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        paddingLeft: 10,
      }}
    >
      <div className="v2-product-brand" style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
        <div style={{ padding: 17, display: 'flex', alignItems: 'center' }}>
          <Mark size={34} />
        </div>
        <div
          style={{
            fontFamily: 'var(--osd-font-display)',
            fontSize: 125,
            fontWeight: 880,
            lineHeight: 1,
            letterSpacing: 0,
          }}
        >
          AgentGate
        </div>
      </div>
      <p
        className="v2-product-tagline"
        style={{
          margin: '14px 0 0',
          maxWidth: 828,
          fontSize: 48,
          lineHeight: 1.35,
          fontWeight: 520,
          color: c.soft,
        }}
      >
        Release Authority
        <br />
        for AI Agents
      </p>
      <p
        className="v2-product-question"
        style={{
          margin: '34px 0 0',
          maxWidth: 828,
          fontSize: 55,
          lineHeight: 1.2,
          fontWeight: 780,
          color: c.ink,
        }}
      >
        Can this version ship?
      </p>
    </div>
  </div>
);

const ReleaseCheck: Page = () => (
  <div
    style={{
      ...fill,
      background: c.bg,
      display: 'flex',
      flexDirection: 'column',
      padding: '72px 88px 64px',
      fontFamily: 'var(--osd-font-body)',
      color: c.ink,
    }}
  >
    <ReleaseCheckStyles />
    <p
      className="v2-rc-eyebrow"
      style={{
        margin: 0,
        fontFamily: 'var(--osd-font-display)',
        fontSize: 104,
        lineHeight: 1.02,
        fontWeight: 860,
        letterSpacing: 0,
        color: c.ink,
      }}
    >
      Run a release check.
    </p>
    <div
      style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        paddingTop: 24,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'stretch', justifyContent: 'center' }}>
        <div className="v2-rc-card-a" style={flowCard}>
          <p style={flowCardTitle}>Candidate version</p>
        </div>
        <FlowArrow />
        <div className="v2-rc-card-b" style={flowCard}>
          <p style={flowCardTitle}>Agent behavior</p>
          <span
            style={{
              position: 'absolute',
              right: 24,
              bottom: 20,
              fontSize: 32,
              fontWeight: 650,
              color: c.muted,
              letterSpacing: 0,
            }}
          >
            Phoenix traces
          </span>
        </div>
        <FlowArrow />
        <div className="v2-rc-card-c" style={flowCard}>
          <p style={flowCardTitle}>Release rules</p>
        </div>
        <FlowArrow />
        <div className="v2-rc-card-d" style={flowCard}>
          <p style={flowCardTitle}>Audit report</p>
        </div>
      </div>
    </div>
    <p
      className="v2-rc-footer"
      style={{
        margin: 0,
        textAlign: 'center',
        fontSize: 56,
        fontWeight: 680,
        color: c.soft,
        letterSpacing: 0,
      }}
    >
      From agent behavior to release decision.
    </p>
  </div>
);

const DemoTransition: Page = () => (
  <div style={fill}>
    <DemoTransitionStyles />
    <div
      className="v2-demo-frame"
      style={{
        ...fill,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '0 120px',
      }}
    >
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 28,
          maxWidth: 1560,
        }}
      >
        <h1
          className="v2-demo-title"
          style={{
            margin: 0,
            fontFamily: 'var(--osd-font-display)',
            fontSize: 118,
            lineHeight: 1.02,
            fontWeight: 820,
            letterSpacing: 0,
            textAlign: 'center',
            color: c.ink,
          }}
        >
          A real agent release report
        </h1>
        <p
          className="v2-demo-subtitle"
          style={{
            margin: 0,
            fontFamily: 'var(--osd-font-body)',
            fontSize: 44,
            lineHeight: 1.35,
            fontWeight: 520,
            letterSpacing: 0,
            textAlign: 'center',
            color: c.soft,
          }}
        >
          v2 candidate review
        </p>
      </div>
    </div>
  </div>
);

const EvidencePipeline: Page = () => (
  <div
    style={{
      ...fill,
      background: c.bg,
      display: 'flex',
      flexDirection: 'column',
      padding: '72px 88px',
      fontFamily: 'var(--osd-font-body)',
      color: c.ink,
    }}
  >
    <EvidencePipelineStyles />
    <p
      className="v2-ep-eyebrow"
      style={{
        margin: 0,
        fontFamily: 'var(--osd-font-display)',
        fontSize: 104,
        lineHeight: 1.02,
        fontWeight: 860,
        letterSpacing: 0,
        color: c.ink,
      }}
    >
      Review agents turn
      <br />
      failures into tests.
    </p>
    <div
      style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 28,
      }}
    >
      <div className="v2-ep-left" style={toneFlowCard('red')}>
        <p style={flowCardTitle}>Dangerous traces</p>
      </div>
      <ForkToAgents className="v2-ep-arrows" />
      <div style={{ display: 'flex', flexDirection: 'column', gap: EP_AGENT_GAP }}>
        <div className="v2-ep-mid-a" style={toneFlowCard('purple', agentFlowCard)}>
          <p style={flowCardTitle}>Pattern agent</p>
        </div>
        <div className="v2-ep-mid-b" style={toneFlowCard('purple', agentFlowCard)}>
          <p style={flowCardTitle}>Regression agent</p>
        </div>
      </div>
      <MergeToCandidates className="v2-ep-arrows" />
      <div className="v2-ep-right" style={toneFlowCard('green')}>
        <p style={flowCardTitle}>
          Future test
          <br />
          candidates
        </p>
      </div>
    </div>
  </div>
);

const CLOSING_LINE_DURATION_S = 1.4;
const CLOSING_LINE_GAP_S = 0.7;
const closingLineDelay = (index: number) =>
  `${index * (CLOSING_LINE_DURATION_S + CLOSING_LINE_GAP_S)}s`;

const ClosingStack: Page = () => (
  <div
    style={{
      ...fill,
      display: 'grid',
      alignItems: 'center',
      padding: '0 132px',
    }}
  >
    <ClosingStyles />
    <div className="v2-closing-stage" style={{ transform: 'translateY(-24px)' }}>
      <div style={{ display: 'grid', justifyItems: 'start' }}>
        <div
          className="v2-up-closing"
          style={{
            fontFamily: 'var(--osd-font-display)',
            fontSize: 118,
            lineHeight: 0.98,
            fontWeight: 820,
            color: '#c9ced4',
            letterSpacing: 0,
            animationDelay: closingLineDelay(0),
          }}
        >
          Phoenix provides evidence
        </div>
        <div
          className="v2-up-closing"
          style={{
            marginTop: 24,
            fontFamily: 'var(--osd-font-display)',
            fontSize: 118,
            lineHeight: 0.98,
            fontWeight: 880,
            color: c.ink,
            letterSpacing: 0,
            animationDelay: closingLineDelay(1),
          }}
        >
          AgentGate enforces policy
        </div>
        <div
          className="v2-up-closing"
          style={{
            marginTop: 24,
            fontFamily: 'var(--osd-font-display)',
            fontSize: 118,
            lineHeight: 0.98,
            fontWeight: 820,
            color: '#c9ced4',
            letterSpacing: 0,
            animationDelay: closingLineDelay(2),
          }}
        >
          Gemini suggests future tests
        </div>
      </div>
    </div>
  </div>
);

const FINAL_SCALE = 1.1;

const Final: Page = () => (
  <div
    style={{
      ...fill,
      display: 'grid',
      placeItems: 'center',
      textAlign: 'center',
      padding: 128,
    }}
  >
    <ClosingStyles />
    <div
      className="v2-final-stage"
      style={{
        transform: `scale(${FINAL_SCALE})`,
        transformOrigin: 'center center',
      }}
    >
      <div
        className="v2-up-final-logo"
        style={{ display: 'flex', justifyContent: 'center', marginBottom: 42 }}
      >
        <Mark size={36} />
      </div>
      <BigTitle className="v2-final-up" size={166} maxWidth={1200}>
        AgentGate
      </BigTitle>
      <Body
        className="v2-final-up"
        size={50}
        maxWidth={920}
        style={{ margin: '42px auto 0', fontWeight: 780, color: c.ink, animationDelay: '.3s' }}
      >
        Ship with evidence, not vibes.
      </Body>
      <Body
        className="v2-final-up"
        size={34}
        maxWidth={920}
        color={c.soft}
        style={{ margin: '24px auto 0', fontWeight: 520, animationDelay: '.45s' }}
      >
        Blocked failures become future release requirements.
      </Body>
    </div>
  </div>
);

export const transition: SlideTransition = {
  duration: 0,
};

Opening.transition = { duration: 0 };
AgentsAct.transition = { duration: 0 };
ProductMark.transition = { duration: 0 };
ReleaseCheck.transition = { duration: 0 };
EvidencePipeline.transition = { duration: 0 };
DemoTransition.transition = { duration: 0 };
ClosingStack.transition = { duration: 0 };
Final.transition = { duration: 0 };

export const notes = [
  `P1 Opening — 15s total. TTS-friendly: elements appear early, then hold.
0:00 — Canvas fades in. 0:01 — Background complete.
0:01.2 — Line 1 begins. 0:01.8 — "Wrong answers became / business risk." readable.
0:01.8–0:05.2 — Line 1 stable hold (~3.4s) for hook narration.
0:05.2 — Line 1 fades out. 0:05.8 — Line 1 gone.
0:06.2 — Line 2 begins. 0:06.9 — "Wrong actions become / release risk." readable.
0:07.2 — Slow zoom to 110% begins. 0:07.2–0:15 — Line 2 + zoom hold.
0:15 — Advance to P2.`,
  `P2 Agents Act — 11s total. Chips finish by 0:06, then 5s stable hold.
0:00.8 — Title begins. 0:01.4 — "Agents can now act." readable.
0:03.2 — Call tools chip. 0:03.8 — Chip 1 in place.
0:04.3 — Trigger workflows. 0:04.9 — Chip 2 in place.
0:05.4 — Touch internal systems. 0:06.0 — All chips in place.
0:06–0:11 — Full frame stable for release-risk closing line.
0:11 — Advance to P3.`,
  `P3 ProductMark — 12s total. Build complete by 0:06.8, then absorb positioning.
0:00 — Build→Test→Gate→Ship lane fades in. 0:00.8 — Lane readable; Gate pulse from 0:00.9.
0:01.0 — Lane green line draws. 0:02.0 — Lane line complete.
0:02.1 — Connector line draws. 0:03.0 — Connector complete. 0:03.1 — Arrow fades in. 0:03.4 — Arrow done.
0:03.6 — AgentGate logo + wordmark. 0:04.4 — Brand complete.
0:04.8 — "Release Authority / for AI Agents". 0:05.6 — Tagline complete.
0:06.0 — "Can this version ship?". 0:06.8 — Question complete.
0:06.8–0:12 — Stable hold (release authority positioning).
0:12 — Advance to P4.`,
  `P4 Release Check — 15s total. Pipeline complete by 0:11.2, then 3s+ hold.
0:01.0 — Eyebrow begins. 0:01.5 — "Run a release check." readable.
0:02.2 — Candidate version. 0:03.0 — Card A in place.
0:04.0 — Agent behavior (+ Phoenix traces). 0:04.8 — Card B in place.
0:05.8 — Release rules. 0:06.6 — Card C in place.
0:07.6 — Audit report. 0:08.4 — Card D in place.
0:09.4 — Arrows fade in. 0:10.2 — Arrows complete.
0:10.6 — Footer begins. 0:11.2 — "From agent behavior to release decision." readable.
0:12.0–0:12.6 — Audit report card subtle scale bump.
0:12.6–0:15 — Stable hold. 0:15 — Advance to P5.`,
  `P5 Evidence Pipeline — 15s total. Full diagram by 0:09.5, then 5.5s trust-boundary hold.
0:00.8 — Eyebrow begins. 0:01.2 — "Review agents turn / failures into tests." readable.
0:01.2 — Dangerous traces card appears. 0:02.0 — Left card in place.
0:03.2 — Pattern + Regression agents together. 0:04.2 — Mid cards in place.
0:06.2 — Future test candidates. 0:07.2 — Right card in place.
0:08.4 — Fork/merge arrows. 0:09.5 — Arrows complete.
0:09.5–0:15 — Stable hold for advisory / humans approve / gate decides narration.
0:15 — Advance to P6.`,
  `P6 Demo Transition — 6s total. Short handoff to browser report.
0:00 — Canvas fades in. 0:00.4 — Canvas complete.
0:00.8 — "A real agent release report" begins. 0:01.3 — Title readable.
0:02.2 — "v2 candidate review" subtitle begins. 0:02.8 — Subtitle readable.
0:02.8–0:06 — Stable hold, then hard cut to report hero.
0:06 — Cut to browser.`,
  `P7 Closing Stack — 8s total. One line per beat; hold after line 3.
0:00 — Phoenix provides evidence (gray). 0:01.4 — Line 1 in place.
0:02.1 — AgentGate enforces policy (bold). 0:03.5 — Line 2 in place.
0:04.2 — Gemini suggests future tests (gray). 0:05.6 — Line 3 in place.
0:05.6–0:08 — Stable hold for "That is the loop." 0:08 — Advance to P8.`,
  `P8 Final — 7s total. Taglines need weight; do not end early.
0:00 — Logo + AgentGate wordmark. 0:00.8 — Wordmark in place.
0:00.3 — "Ship with evidence, not vibes." 0:01.1 — Primary tagline complete.
0:00.5 — Secondary tagline begins. 0:01.3 — "Blocked failures become future release requirements." complete.
0:01.3–0:07 — Stable hold on closing frame. 0:07 — End recording.`,
];

export const meta: SlideMeta = {
  title: 'AgentGate Launch v2',
  createdAt: '2026-06-08T14:25:23.671Z',
};

export default [
  Opening,
  AgentsAct,
  ProductMark,
  ReleaseCheck,
  EvidencePipeline,
  DemoTransition,
  ClosingStack,
  Final,
] satisfies Page[];
