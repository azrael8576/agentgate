import type { CSSProperties, ReactNode } from 'react';
import type { DesignSystem, Page, SlideMeta } from '@open-slide/core';

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

const root: CSSProperties = {
  width: '100%',
  height: '100%',
  background: 'var(--osd-bg)',
  color: 'var(--osd-text)',
  fontFamily: 'var(--osd-font-body)',
  position: 'relative',
  overflow: 'hidden',
  letterSpacing: 0,
};

const shell: CSSProperties = {
  ...root,
  padding: '96px 112px',
};

const styles = `
  @keyframes ag-fade-up {
    from { opacity: 0; transform: translateY(18px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @keyframes ag-fade-in {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  @keyframes ag-draw {
    from { transform: scaleX(0); }
    to { transform: scaleX(1); }
  }
  @keyframes ag-pulse-red {
    0%, 100% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0); }
    50% { box-shadow: 0 0 0 14px rgba(220, 38, 38, 0.12); }
  }
  @keyframes ag-pulse-green {
    0%, 100% { box-shadow: 0 0 0 0 rgba(22, 163, 74, 0); }
    50% { box-shadow: 0 0 0 14px rgba(22, 163, 74, 0.14); }
  }
  @keyframes ag-scan {
    0% { transform: translateX(-220px); opacity: 0; }
    15%, 80% { opacity: 1; }
    100% { transform: translateX(1180px); opacity: 0; }
  }
  .ag-up { opacity: 0; animation: ag-fade-up .78s cubic-bezier(.2,.7,.2,1) forwards; }
  .ag-up-closing { opacity: 0; animation: ag-fade-up 1.4s cubic-bezier(.2,.7,.2,1) forwards; }
  .ag-up-final-logo { opacity: 0; animation: ag-fade-up 1.04s cubic-bezier(.2,.7,.2,1) forwards; }
  .ag-in { opacity: 0; animation: ag-fade-in .85s ease forwards; }
  .ag-line { transform-origin: left center; transform: scaleX(0); animation: ag-draw .9s cubic-bezier(.2,.7,.2,1) forwards; }
  .ag-red-pulse { animation: ag-pulse-red 1.8s ease-in-out infinite; }
  .ag-green-pulse { animation: ag-pulse-green 1.8s ease-in-out infinite; }
  .ag-scan { animation: ag-scan 2.8s cubic-bezier(.2,.7,.2,1) infinite; }
`;

const Styles = () => <style>{styles}</style>;

const Footer = () => null;

const Mark = ({ size = 28, color = c.green }: { size?: number; color?: string }) => (
  <span
    style={{
      width: size,
      height: size,
      borderRadius: Math.max(3, size / 7),
      background: color,
      display: 'inline-block',
      boxShadow: `0 0 0 1px rgba(0,0,0,0.04), 0 12px 28px -18px ${color}`,
    }}
  />
);

const Eyebrow = ({ children, color = c.soft }: { children: ReactNode; color?: string }) => (
  <div style={{ fontSize: 24, fontWeight: 750, color, letterSpacing: 0, textTransform: 'uppercase' }}>
    {children}
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

const Card = ({
  children,
  style,
  className,
}: {
  children: ReactNode;
  style?: CSSProperties;
  className?: string;
}) => (
  <div
    className={className}
    style={{
      background: c.paper,
      border: `1px solid ${c.line}`,
      borderRadius: 'var(--osd-radius)',
      boxShadow: '0 24px 70px -46px rgba(17, 19, 21, 0.38)',
      ...style,
    }}
  >
    {children}
  </div>
);

const Pill = ({
  children,
  tone = 'neutral',
  style,
  showDot = false,
}: {
  children: ReactNode;
  tone?: 'neutral' | 'green' | 'red' | 'amber' | 'blue' | 'purple';
  style?: CSSProperties;
  showDot?: boolean;
}) => {
  const toneMap = {
    neutral: { bg: c.paperWarm, fg: c.soft, border: c.line },
    green: { bg: c.greenSoft, fg: c.green, border: '#b7e7c7' },
    red: { bg: c.redSoft, fg: c.red, border: '#f8b8b8' },
    amber: { bg: c.amberSoft, fg: c.amber, border: '#efd58b' },
    blue: { bg: c.blueSoft, fg: c.blue, border: '#7dd3fc' },
    purple: { bg: c.purpleSoft, fg: c.purple, border: '#c4b5fd' },
  }[tone];
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 9,
        padding: '10px 16px',
        borderRadius: 999,
        border: `1px solid ${toneMap.border}`,
        background: toneMap.bg,
        color: toneMap.fg,
        fontSize: 22,
        fontWeight: 750,
        lineHeight: 1,
        whiteSpace: 'nowrap',
        ...style,
      }}
    >
      {showDot ? <Dot color={toneMap.fg} size={10} /> : null}
      {children}
    </span>
  );
};

const Dot = ({ color = c.green, size = 9 }: { color?: string; size?: number }) => (
  <span style={{ width: size, height: size, borderRadius: '50%', background: color, display: 'inline-block' }} />
);

const CheckMark = ({ color = c.green, size = 22 }: { color?: string; size?: number }) => (
  <span
    style={{
      width: size,
      height: size,
      borderRadius: '50%',
      display: 'inline-grid',
      placeItems: 'center',
      background: color,
      color: '#fff',
      fontSize: Math.round(size * 0.64),
      fontWeight: 900,
      lineHeight: 1,
    }}
  >
    ✓
  </span>
);

const Arrow = ({ color = c.line }: { color?: string }) => (
  <div style={{ width: 86, display: 'flex', alignItems: 'center' }}>
    <div className="ag-line" style={{ height: 2, width: 70, background: color }} />
    <div
      className="ag-in"
      style={{
        width: 0,
        height: 0,
        borderTop: '7px solid transparent',
        borderBottom: '7px solid transparent',
        borderLeft: `10px solid ${color}`,
        animationDelay: '.6s',
      }}
    />
  </div>
);

const GateRail = ({
  title,
  steps,
  tone = 'green',
  delay = 0,
}: {
  title: string;
  steps: string[];
  tone?: 'green' | 'amber';
  delay?: number;
}) => {
  const color = tone === 'green' ? c.green : c.amber;
  const soft = tone === 'green' ? c.greenSoft : c.amberSoft;
  return (
    <Card className="ag-up" style={{ padding: 28, minHeight: 284, animationDelay: `${delay}s` }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
        <div style={{ fontSize: 33, fontWeight: 840 }}>{title}</div>
        <Pill tone={tone === 'green' ? 'green' : 'amber'}>{tone === 'green' ? 'known gate' : 'missing gate'}</Pill>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${steps.length}, 1fr)`, alignItems: 'center', gap: 0 }}>
        {steps.map((step, i) => {
          const isGap = step === '?';
          const stepKey = isGap ? `gap-${i}` : step;
          return (
          <div key={stepKey} style={{ position: 'relative', minHeight: 154, display: 'grid', justifyItems: 'center' }}>
            {i < steps.length - 1 ? (
              <div
                className="ag-line"
                style={{
                  position: 'absolute',
                  top: 34,
                  left: '58%',
                  width: '84%',
                  height: 3,
                  background: tone === 'amber' && steps[i + 1] === '?' ? c.red : color,
                  animationDelay: `${0.18 + i * 0.1}s`,
                }}
              />
            ) : null}
            <div
              className={tone === 'amber' && isGap ? 'ag-red-pulse' : undefined}
              style={{
                width: 68,
                height: 68,
                borderRadius: '50%',
                display: 'grid',
                placeItems: 'center',
                background: isGap ? c.redSoft : soft,
                border: `2px solid ${isGap ? c.red : color}`,
                color: isGap ? c.red : color,
                fontSize: isGap ? 40 : 20,
                fontWeight: 900,
                zIndex: 1,
              }}
            >
              {isGap ? '?' : <CheckMark color={color} size={24} />}
            </div>
            {!isGap ? (
              <div
                style={{
                  marginTop: 18,
                  textAlign: 'center',
                  fontSize: 23,
                  lineHeight: 1.16,
                  fontWeight: 760,
                  color: c.ink,
                  maxWidth: 138,
                }}
              >
                {step}
              </div>
            ) : null}
          </div>
        );
        })}
      </div>
    </Card>
  );
};

const MiniNode = ({
  title,
  sub,
  titleSize = 25,
  subSize = 19,
  tone = 'neutral',
  delay = 0,
  width = 250,
}: {
  title: string;
  sub?: string;
  titleSize?: number;
  subSize?: number;
  tone?: 'neutral' | 'green' | 'red' | 'amber' | 'blue' | 'purple';
  delay?: number;
  width?: number;
}) => {
  const color =
    tone === 'green'
      ? c.green
      : tone === 'red'
        ? c.red
        : tone === 'amber'
          ? c.amber
          : tone === 'blue'
            ? c.blue
            : tone === 'purple'
              ? c.purple
              : c.soft;
  return (
    <Card
      className="ag-up"
      style={{
        width,
        minHeight: sub ? 132 : 156,
        padding: sub ? 24 : 32,
        animationDelay: `${delay}s`,
        borderColor: tone === 'neutral' ? c.line : color,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: sub ? 16 : 0 }}>
        <Dot color={color} size={sub ? 9 : 11} />
        <div style={{ fontSize: titleSize, fontWeight: 800, color: c.ink, lineHeight: 1.15 }}>{title}</div>
      </div>
      {sub ? <div style={{ fontSize: subSize, lineHeight: 1.25, color: c.muted, fontWeight: 520 }}>{sub}</div> : null}
    </Card>
  );
};

const Chrome = ({ children, title = 'release.agentgate.dev' }: { children: ReactNode; title?: string }) => (
  <Card style={{ overflow: 'hidden' }}>
    <div
      style={{
        height: 54,
        borderBottom: `1px solid ${c.lineSoft}`,
        display: 'flex',
        alignItems: 'center',
        padding: '0 20px',
        gap: 14,
        background: c.paperWarm,
      }}
    >
      <span style={{ width: 12, height: 12, borderRadius: '50%', background: '#ff6257' }} />
      <span style={{ width: 12, height: 12, borderRadius: '50%', background: '#ffbd2f' }} />
      <span style={{ width: 12, height: 12, borderRadius: '50%', background: '#29c840' }} />
      <div
        style={{
          marginLeft: 18,
          padding: '8px 18px',
          borderRadius: 999,
          background: c.paper,
          border: `1px solid ${c.lineSoft}`,
          color: c.muted,
          fontSize: 18,
          fontWeight: 650,
          width: 360,
          textAlign: 'center',
        }}
      >
        {title}
      </div>
    </div>
    {children}
  </Card>
);

const CenterStack = ({ children }: { children: ReactNode }) => (
  <div
    style={{
      ...root,
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      padding: '0 128px',
    }}
  >
    <Styles />
    {children}
    <Footer />
  </div>
);

const Opening: Page = () => (
  <CenterStack>
    <BigTitle className="ag-up" size={108} maxWidth={1320}>
      A wrong AI answer can become a real business consequence.
    </BigTitle>
    <Card
      className="ag-up"
      style={{
        marginTop: 52,
        padding: '32px 40px',
        maxWidth: 820,
        animationDelay: '.14s',
      }}
    >
      <div style={{ fontSize: 28, fontWeight: 760, color: c.muted, marginBottom: 16 }}>2024</div>
      <div style={{ fontSize: 34, lineHeight: 1.32, fontWeight: 720, color: c.ink }}>
        Wrong chatbot guidance → real business consequence
      </div>
    </Card>
    <Body
      className="ag-up"
      size={32}
      maxWidth={720}
      color={c.muted}
      style={{ marginTop: 52, animationDelay: '.28s' } as CSSProperties}
    >
      Wrong answer was only the beginning.
    </Body>
  </CenterStack>
);

const AgentsAct: Page = () => (
  <div style={shell}>
    <Styles />
    <div className="ag-up">
      <BigTitle size={96} maxWidth={1280}>
        Agents are moving from answers to actions.
      </BigTitle>
    </div>
    <div style={{ marginTop: 96, display: 'flex', alignItems: 'stretch', gap: 18 }}>
      <MiniNode title="Answer" sub="Static response" titleSize={38} delay={0.12} width={296} />
      <Arrow />
      <MiniNode title="Call tools" sub="Internal APIs" titleSize={38} delay={0.28} width={296} />
      <Arrow />
      <MiniNode title="Trigger workflows" sub="Operational actions" titleSize={38} delay={0.44} width={326} />
      <Arrow color={c.red} />
      <MiniNode title="Touch systems" sub="Internal systems" titleSize={38} tone="red" delay={0.6} width={336} />
    </div>
    <div
      className="ag-up"
      style={{
        position: 'absolute',
        left: '50%',
        transform: 'translateX(-50%)',
        bottom: 120,
        fontSize: 54,
        fontWeight: 820,
        color: c.red,
        textAlign: 'center',
        maxWidth: 900,
        animationDelay: '.88s',
      }}
    >
      A wrong action is a release risk.
    </div>
    <Footer />
  </div>
);

const ReleaseGap: Page = () => (
  <div style={shell}>
    <Styles />
    <BigTitle size={96} maxWidth={1420}>
      Agent releases need gates too.
    </BigTitle>
    <div style={{ display: 'grid', gridTemplateRows: '1fr 1fr', gap: 24, marginTop: 38 }}>
      <GateRail
        title="Traditional software"
        steps={['Code', 'Review', 'Tests', 'CI/CD gate', 'Deploy']}
        tone="green"
      />
      <GateRail
        title="AI agent version"
        steps={['Prompt', 'Model', 'Tools', 'Permissions', '?', 'Production']}
        tone="amber"
        delay={0.16}
      />
    </div>
    <Footer />
  </div>
);

const ProductMark: Page = () => (
  <div
    style={{
      ...root,
      display: 'grid',
      gridTemplateColumns: '1fr auto 1fr',
      alignItems: 'center',
      padding: '96px 112px',
      gap: 40,
    }}
  >
    <Styles />
    <Card className="ag-up" style={{ width: '100%', maxWidth: 680, padding: '48px 44px', justifySelf: 'end' }}>
      <div style={{ fontSize: 32, fontWeight: 760, color: c.soft, marginBottom: 40 }}>CI/CD release lane</div>
      <div
        style={{
          position: 'relative',
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          alignItems: 'start',
          justifyItems: 'center',
          paddingTop: 12,
        }}
      >
        <div
          className="ag-line"
          style={{
            position: 'absolute',
            left: 52,
            right: 52,
            top: 36,
            height: 4,
            background: c.green,
            animationDelay: '.35s',
          }}
        />
        {[
          ['Build', c.green],
          ['Test', c.green],
          ['Gate', c.green],
          ['Ship', c.green],
        ].map(([label, color]) => (
          <div key={label} style={{ position: 'relative', display: 'grid', justifyItems: 'center', gap: 16, zIndex: 1 }}>
            <span
              className={label === 'Gate' ? 'ag-green-pulse' : undefined}
              style={{
                width: 52,
                height: 52,
                borderRadius: '50%',
                background: color,
                display: 'grid',
                placeItems: 'center',
              }}
            >
              <CheckMark color={String(color)} size={26} />
            </span>
            <span style={{ fontSize: 24, fontWeight: label === 'Gate' ? 820 : 760, color: label === 'Gate' ? c.ink : c.muted }}>
              {label}
            </span>
          </div>
        ))}
      </div>
    </Card>
    <div className="ag-up" style={{ display: 'flex', alignItems: 'center', animationDelay: '.45s' }}>
      <div className="ag-line" style={{ width: 96, height: 4, background: c.green, animationDelay: '.45s' }} />
      <div
        style={{
          width: 0,
          height: 0,
          borderTop: '10px solid transparent',
          borderBottom: '10px solid transparent',
          borderLeft: `14px solid ${c.green}`,
        }}
      />
    </div>
    <div
      className="ag-up"
      style={{
        animationDelay: '.2s',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        paddingLeft: 8,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
        <div style={{ padding: 14, display: 'flex', alignItems: 'center' }}>
          <Mark size={28} />
        </div>
        <div style={{ fontSize: 104, fontWeight: 880, lineHeight: 1 }}>AgentGate</div>
      </div>
      <Body size={40} maxWidth={690} color={c.soft} style={{ marginTop: 32 }}>
        Release authority for AI agents.
      </Body>
      <Body size={46} maxWidth={690} style={{ marginTop: 28, fontWeight: 780 }}>
        Can this version ship?
      </Body>
    </div>
    <Footer />
  </div>
);

const ReleaseCheck: Page = () => (
  <div style={shell}>
    <Styles />
    <BigTitle size={104} maxWidth={1200}>
      Ship or no-ship, from evidence.
    </BigTitle>
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', marginTop: 72, gap: 28 }}>
      <MiniNode title="Candidate" titleSize={34} delay={0.12} width={340} />
      <Arrow />
      <MiniNode title="Release Check" titleSize={34} tone="green" delay={0.28} width={380} />
      <Arrow />
      <MiniNode title="Approve / Block" titleSize={34} delay={0.44} width={360} />
    </div>
    <Body
      className="ag-up"
      size={44}
      maxWidth={980}
      color={c.soft}
      style={{
        marginTop: 44,
        textAlign: 'center',
        marginLeft: 'auto',
        marginRight: 'auto',
        animationDelay: '.58s',
        fontWeight: 680,
      } as CSSProperties}
    >
      Audit report + regression candidates
    </Body>
    <div className="ag-up" style={{ marginTop: 48, display: 'flex', justifyContent: 'center', gap: 18, animationDelay: '.8s' }}>
      <Pill tone="green">APPROVED</Pill>
      <Pill tone="red">BLOCKED</Pill>
      <Pill tone="blue" showDot>deterministic</Pill>
    </div>
    <Footer />
  </div>
);

const EvidenceStack: Page = () => (
  <div style={shell}>
    <Styles />
    <BigTitle size={92} maxWidth={1360}>
      Trace. Decide. Improve.
    </BigTitle>
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 28, marginTop: 86 }}>
      {[
        ['Phoenix', 'What happened?', 'Trace evidence', c.blue, c.blueSoft],
        ['AgentGate', 'Can it ship?', 'Policy + blocker metrics', c.green, c.greenSoft],
        ['Gemini', 'Why did it fail?', 'Advisory explanation', c.purple, c.purpleSoft],
      ].map(([name, q, sub, color, bg], i) => (
        <Card key={name} className="ag-up" style={{ padding: 34, minHeight: 390, animationDelay: `${0.16 + i * 0.16}s` }}>
          <div style={{ width: 62, height: 62, borderRadius: 8, background: bg, display: 'grid', placeItems: 'center' }}>
            <Dot color={color} size={20} />
          </div>
          <div style={{ fontSize: 44, fontWeight: 850, marginTop: 64 }}>{name}</div>
          <div style={{ fontSize: 34, fontWeight: 760, color, marginTop: 20 }}>{q}</div>
          <div style={{ fontSize: 27, color: c.soft, marginTop: 18, lineHeight: 1.3 }}>{sub}</div>
        </Card>
      ))}
    </div>
    <div className="ag-up" style={{ textAlign: 'center', marginTop: 46, animationDelay: '.64s' }}>
      <Body size={36} maxWidth={1200} color={c.soft} style={{ margin: '0 auto', fontWeight: 650, textAlign: 'center' }}>
        LLMs explain. Policies decide.
      </Body>
    </div>
    <Footer />
  </div>
);

const DemoRequest: Page = () => (
  <div style={{ ...root, display: 'grid', placeItems: 'center', padding: 128 }}>
    <Styles />
    <Chrome title="reference-ops.agentgate.dev">
      <div style={{ width: 1120, height: 560, padding: 52, position: 'relative' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: 42, fontWeight: 840 }}>Reference Ops AI</div>
            <div style={{ marginTop: 14, display: 'flex', gap: 12 }}>
              <Pill>User role: general_employee</Pill>
              <Pill tone="green">Candidate: v2</Pill>
            </div>
          </div>
          <Mark size={24} />
        </div>
        <Card
          style={{ marginTop: 74, padding: 34, borderColor: c.lineSoft, boxShadow: 'none' }}
        >
          <div style={{ fontSize: 24, fontWeight: 760, color: c.muted, marginBottom: 20 }}>REQUEST</div>
          <div style={{ fontSize: 42, lineHeight: 1.22, fontWeight: 760, maxWidth: 850 }}>
            VIP users are reporting checkout failures. Check whether this is causing revenue impact.
          </div>
        </Card>
      </div>
    </Chrome>
    <Footer />
  </div>
);

const Preflight: Page = () => (
  <div style={shell}>
    <Styles />
    <BigTitle size={112} maxWidth={1280}>
      The policy says no.
    </BigTitle>
    <div style={{ marginTop: 100, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 44 }}>
      <Card style={{ padding: 42 }}>
        <div style={{ fontSize: 28, fontWeight: 760, color: c.muted }}>User role</div>
        <div style={{ marginTop: 28, fontSize: 58, fontWeight: 840 }}>general_employee</div>
      </Card>
      <Card className="ag-red-pulse" style={{ padding: 42, borderColor: c.red, borderWidth: 2, background: c.redSoft }}>
        <div style={{ fontSize: 28, fontWeight: 760, color: c.red }}>Policy preflight</div>
        <div style={{ marginTop: 28, fontSize: 88, fontWeight: 890, color: c.red }}>DENY</div>
      </Card>
    </div>
    <Footer />
  </div>
);

const DenyExecuted: Page = () => (
  <div style={shell}>
    <Styles />
    <BigTitle size={104} maxWidth={1350}>
      DENY, then EXECUTED.
    </BigTitle>
    <Card style={{ marginTop: 76, padding: 36, position: 'relative', overflow: 'hidden' }}>
      <div
        className="ag-scan"
        style={{
          position: 'absolute',
          top: 0,
          bottom: 0,
          width: 120,
          background: 'linear-gradient(90deg, transparent, rgba(220,38,38,.10), transparent)',
        }}
      />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 22 }}>
        {[
          ['Request', 'deep investigation', 'neutral'],
          ['Preflight', 'DENY', 'red'],
          ['Tool call', 'EXECUTED', 'red'],
          ['Risk', 'critical', 'red'],
        ].map(([label, value, tone], i) => (
          <div
            key={label}
            style={{
              padding: 24,
              minHeight: 180,
              borderRadius: 8,
              border: `1px solid ${tone === 'red' ? c.red : c.lineSoft}`,
              background: tone === 'red' ? c.redSoft : c.paperWarm,
            }}
          >
            <div style={{ fontSize: 22, fontWeight: 780, color: tone === 'red' ? c.red : c.muted }}>{label}</div>
            <div style={{ marginTop: 38, fontSize: 35, fontWeight: 850, color: tone === 'red' ? c.red : c.ink }}>{value}</div>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 42, display: 'flex', alignItems: 'center', gap: 24 }}>
        <Pill tone="red">Policy DENY</Pill>
        <Arrow color={c.red} />
        <Pill tone="red">Dangerous tool executed</Pill>
      </div>
    </Card>
    <Footer />
  </div>
);

const DeterministicBlock: Page = () => (
  <div style={{ ...root, display: 'grid', gridTemplateColumns: '1fr 1fr', alignItems: 'center', padding: 128, gap: 72 }}>
    <Styles />
    <div>
      <BigTitle size={132} maxWidth={760}>
        v2 BLOCKED
      </BigTitle>
      <Body size={40} maxWidth={690} style={{ marginTop: 38 }}>
        Metrics and policy. Not an LLM vote.
      </Body>
    </div>
    <Card style={{ padding: 42 }}>
      {[
        'unauthorized dangerous tool attempt',
        'dangerous tool policy violation',
        'sensitive output violation',
      ].map((item, i) => (
        <div
          key={item}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 18,
            minHeight: 86,
            borderTop: i === 0 ? 'none' : `1px solid ${c.lineSoft}`,
            fontSize: 29,
            color: c.ink,
            fontWeight: 720,
          }}
        >
          <Dot color={c.red} />
          <span>{item}</span>
        </div>
      ))}
      <div style={{ marginTop: 28, padding: 24, borderRadius: 8, background: c.paperWarm, border: `1px solid ${c.lineSoft}` }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 24, fontWeight: 720, color: c.soft }}>
          <span>LLM diagnosis</span>
          <span>advisory only</span>
        </div>
      </div>
    </Card>
    <Footer />
  </div>
);

const AdvisoryAgents: Page = () => (
  <div style={shell}>
    <Styles />
    <BigTitle size={88} maxWidth={1420}>
      Agents investigate. Humans approve. Gates decide.
    </BigTitle>
    <div style={{ marginTop: 74, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 34 }}>
      <Card className="ag-up" style={{ padding: 40, borderTop: `4px solid ${c.purple}`, animationDelay: '.1s' }}>
        <Pill tone="purple" showDot style={{ fontSize: 24, padding: '12px 18px' }}>
          Investigation
        </Pill>
        <div style={{ fontSize: 44, fontWeight: 850, marginTop: 54 }}>Investigation Agent</div>
        <Body size={34} maxWidth={610} style={{ marginTop: 24 }}>
          Explains dangerous traces. Groups failures into patterns.
        </Body>
      </Card>
      <Card className="ag-up" style={{ padding: 40, borderTop: `4px solid ${c.blue}`, animationDelay: '.26s' }}>
        <Pill tone="blue" showDot style={{ fontSize: 24, padding: '12px 18px' }}>
          Curation
        </Pill>
        <div style={{ fontSize: 44, fontWeight: 850, marginTop: 54 }}>Curation Agent</div>
        <Body size={34} maxWidth={610} style={{ marginTop: 24 }}>
          Proposes controls. Suggests golden dataset candidates.
        </Body>
      </Card>
    </div>
    <div className="ag-up" style={{ marginTop: 52, textAlign: 'center', animationDelay: '.36s' }}>
      <Body size={38} maxWidth={1200} color={c.soft} style={{ margin: '0 auto', fontWeight: 700, textAlign: 'center' }}>
        Advisory only.
      </Body>
    </div>
    <Footer />
  </div>
);

const TurnFailures: Page = () => (
  <CenterStack>
    <BigTitle size={134} maxWidth={1340}>
      Blocked failures become future release requirements.
    </BigTitle>
    <div style={{ display: 'flex', gap: 18, marginTop: 40 }}>
      <Pill tone="red">failure pattern</Pill>
      <Pill tone="amber">human review</Pill>
      <Pill tone="green">inherited control</Pill>
    </div>
  </CenterStack>
);

const Verification: Page = () => (
  <div style={shell}>
    <Styles />
    <BigTitle size={104} maxWidth={1260}>
      v2.1 passes inherited controls.
    </BigTitle>
    <div style={{ marginTop: 72, display: 'grid', gridTemplateColumns: '560px 1fr', gap: 42, alignItems: 'stretch' }}>
      <Card style={{ padding: 38 }}>
        {['v2 BLOCKED', 'Human-approved controls', 'v2.1 verification'].map((item, i) => (
          <div key={item} style={{ display: 'flex', alignItems: 'center', gap: 18, minHeight: 104 }}>
            <Dot color={i === 0 ? c.red : i === 1 ? c.amber : c.green} size={13} />
            <span style={{ fontSize: 31, fontWeight: 780, color: c.ink }}>{item}</span>
          </div>
        ))}
      </Card>
      <Card style={{ padding: 38, borderColor: c.green }}>
        <Pill tone="green">v2.1 APPROVED</Pill>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 46 }}>
          {[
            ['4', 'inherited controls loaded'],
            ['4', 'passed'],
            ['0', 'blocking failures'],
            ['warnings', 'remain visible'],
          ].map(([num, label]) => (
            <div key={label} style={{ padding: 24, border: `1px solid ${c.lineSoft}`, borderRadius: 8, background: c.paperWarm }}>
              <div style={{ fontSize: 52, fontWeight: 880, color: num === 'warnings' ? c.amber : c.green }}>{num}</div>
              <div style={{ marginTop: 10, fontSize: 22, fontWeight: 650, color: c.soft }}>{label}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
    <Footer />
  </div>
);

const TrustBoundary: Page = () => (
  <CenterStack>
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 34, marginTop: 0 }}>
      <div>
        <BigTitle size={112} maxWidth={780}>
          Gemini explains.
        </BigTitle>
        <BigTitle size={112} maxWidth={820} style={{ color: c.green, marginTop: 22 }}>
          AgentGate decides.
        </BigTitle>
      </div>
      <Card style={{ padding: 42, alignSelf: 'center' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 30, fontWeight: 790, marginBottom: 30 }}>
          <span>Decision source</span>
          <Pill tone="green">deterministic</Pill>
        </div>
        <div style={{ fontSize: 30, lineHeight: 1.45, color: c.soft, fontWeight: 560 }}>
          Policy thresholds decide. Not the model.
        </div>
      </Card>
    </div>
  </CenterStack>
);

const AuditArtifact: Page = () => (
  <div style={shell}>
    <Styles />
    <BigTitle size={96} maxWidth={1320}>
      Every release leaves a trail.
    </BigTitle>
    <Chrome title="agentgate release report" >
      <div style={{ width: 1290, height: 460, padding: 34 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1.1fr .9fr', gap: 26 }}>
          <Card style={{ padding: 28, boxShadow: 'none', borderColor: c.lineSoft, minHeight: 360 }}>
            <Pill tone="red">v2 BLOCKED</Pill>
            <div style={{ marginTop: 40, fontSize: 34, fontWeight: 830 }}>Blocking metrics</div>
            {['dangerous policy violation', 'unauthorized tool attempt', 'sensitive output'].map((item, i) => (
              <div key={item} style={{ marginTop: 24, display: 'flex', gap: 14, alignItems: 'center', fontSize: 24, color: c.soft }}>
                <Dot color={c.red} />
                <span>{item}</span>
              </div>
            ))}
          </Card>
          <Card style={{ padding: 28, boxShadow: 'none', borderColor: c.lineSoft, minHeight: 360 }}>
            <Pill tone="blue">Regression candidates</Pill>
            <div style={{ marginTop: 18, fontSize: 20, fontWeight: 650, color: c.muted }}>
              From v2 dangerous sessions
            </div>
            <div style={{ marginTop: 24, display: 'grid', gap: 16 }}>
              {['DENY → EXECUTED trace', 'Policy violation pattern', 'Sensitive output case'].map((label) => (
                <div
                  key={label}
                  style={{
                    height: 58,
                    borderRadius: 8,
                    background: c.paperWarm,
                    border: `1px solid ${c.lineSoft}`,
                    display: 'flex',
                    alignItems: 'center',
                    padding: '0 18px',
                    fontSize: 20,
                    fontWeight: 650,
                    color: c.soft,
                  }}
                >
                  {label}
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </Chrome>
    <Footer />
  </div>
);

const CLOSING_LINE_DURATION_S = 1.4;
const CLOSING_LINE_GAP_S = 0.7;
const closingLineDelay = (index: number) =>
  `${index * (CLOSING_LINE_DURATION_S + CLOSING_LINE_GAP_S)}s`;

const ClosingStack: Page = () => (
  <div
    style={{
      ...root,
      display: 'grid',
      alignItems: 'center',
      padding: '0 132px',
    }}
  >
    <Styles />
    <div style={{ transform: 'translateY(-24px)' }}>
      <div
        style={{
          display: 'grid',
          justifyItems: 'start',
        }}
      >
        <div
          className="ag-up-closing"
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
          Phoenix provides evidence.
        </div>
        <div
          className="ag-up-closing"
          style={{
            marginTop: -8,
            marginLeft: 74,
            fontFamily: 'var(--osd-font-display)',
            fontSize: 142,
            lineHeight: 0.94,
            fontWeight: 880,
            color: c.ink,
            letterSpacing: 0,
            animationDelay: closingLineDelay(1),
          }}
        >
          AgentGate enforces release policy.
        </div>
        <div
          className="ag-up-closing"
          style={{
            marginTop: -6,
            marginLeft: 188,
            fontFamily: 'var(--osd-font-display)',
            fontSize: 118,
            lineHeight: 0.98,
            fontWeight: 820,
            color: '#c9ced4',
            letterSpacing: 0,
            animationDelay: closingLineDelay(2),
          }}
        >
          Gemini suggests regression coverage.
        </div>
      </div>
    </div>
    <Footer />
  </div>
);

const Final: Page = () => (
  <div style={{ ...root, display: 'grid', placeItems: 'center', textAlign: 'center', padding: 128 }}>
    <Styles />
    <div>
      <div className="ag-up-final-logo" style={{ display: 'flex', justifyContent: 'center', marginBottom: 42 }}>
        <Mark size={36} />
      </div>
      <BigTitle className="ag-up" size={166} maxWidth={1200}>
        AgentGate
      </BigTitle>
      <Body
        className="ag-up"
        size={50}
        maxWidth={920}
        style={{ margin: '42px auto 0', fontWeight: 780, color: c.ink, animationDelay: '.3s' }}
      >
        Ship with evidence, not vibes.
      </Body>
      <Body
        className="ag-up"
        size={34}
        maxWidth={920}
        color={c.soft}
        style={{ margin: '24px auto 0', fontWeight: 520, animationDelay: '.45s' }}
      >
        Blocked failures become future release requirements.
      </Body>
    </div>
    <Footer />
  </div>
);

export const notes = [
  `In 2024, a chatbot's wrong refund guidance became a real business consequence. That was not an agent taking action — only a chatbot giving the wrong answer. Wrong answer was only the beginning.`,
  `AI agents are moving from answers to actions. They call tools, trigger workflows, and touch internal systems. Once an agent can act, a wrong behavior becomes a release risk.`,
  `Software already has CI/CD gates. Agent versions change prompts, models, tools, permissions, and orchestration. That gap needs a release authority.`,
  `That is where AgentGate sits. Release authority for AI agents. Before production, it asks one question — can this candidate ship from evidence?`,
  `Submit a candidate, run a release check, get an approve-or-block decision, and keep the audit trail for future regression coverage.`,
  `Phoenix records what happened. AgentGate decides whether it can ship. Gemini explains dangerous sessions and suggests future regression candidates — advisory only. LLMs explain. Policies decide.`,
  `Two review agents help humans — one investigates dangerous traces, one curates release controls and golden dataset candidates. They advise. They do not approve releases. Humans approve. The gate still decides. Cut to the live release report after this slide.`,
  `[Deck reference — do not show on recording.] Reasonable ops request from a general employee: VIP checkout failures, check revenue impact.`,
  `[Deck reference — do not show on recording.] Policy preflight says DENY for this role.`,
  `[Deck reference — do not show on recording.] Phoenix trace: preflight DENY, tool EXECUTED, critical risk.`,
  `[Deck reference — do not show on recording.] v2 BLOCKED from blocker metrics, not an LLM opinion.`,
  `[Deck reference — do not show on recording.] Blocked failures become future release requirements.`,
  `[Deck reference — do not show on recording.] v2.1 passes inherited controls; warnings remain.`,
  `[Deck reference — do not show on recording.] Gemini explains. AgentGate decides. Deterministic gate.`,
  `[Deck reference — do not show on recording.] Every release leaves metrics, diagnosis, and regression candidates.`,
  `Phoenix provides evidence. AgentGate enforces release policy. Gemini suggests regression coverage. That is the loop.`,
  `Ship with evidence, not vibes. Blocked failures become future release requirements.`,
];

export const meta: SlideMeta = {
  title: 'AgentGate Launch',
  createdAt: '2026-06-06T15:18:23.089Z',
};

export default [
  Opening,
  AgentsAct,
  ReleaseGap,
  ProductMark,
  ReleaseCheck,
  EvidenceStack,
  AdvisoryAgents,
  DemoRequest,
  Preflight,
  DenyExecuted,
  DeterministicBlock,
  TurnFailures,
  Verification,
  TrustBoundary,
  AuditArtifact,
  ClosingStack,
  Final,
] satisfies Page[];
