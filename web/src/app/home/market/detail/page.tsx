import { Button } from '@/components/ui/button';
import {
  ArrowLeft,
  Bot,
  BrainCircuit,
  Clock3,
  Gem,
  HeartHandshake,
  MessageCircleWarning,
  ShieldAlert,
  Sparkles,
  Star,
  TimerReset,
  TriangleAlert,
  Users,
} from 'lucide-react';
import type { CSSProperties } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import styles from './page.module.css';

const accentPalette = [
  {
    accent: '#FF3AF2',
    border: '#FFE600',
    shadowA: '#00F5D4',
    shadowB: '#7B2FFF',
  },
  {
    accent: '#00F5D4',
    border: '#FF6B35',
    shadowA: '#FF3AF2',
    shadowB: '#FFE600',
  },
  {
    accent: '#FFE600',
    border: '#FF3AF2',
    shadowA: '#7B2FFF',
    shadowB: '#FF6B35',
  },
  {
    accent: '#FF6B35',
    border: '#00F5D4',
    shadowA: '#FFE600',
    shadowB: '#FF3AF2',
  },
  {
    accent: '#7B2FFF',
    border: '#FF6B35',
    shadowA: '#00F5D4',
    shadowB: '#FFE600',
  },
];

const userLevels = [
  {
    title: '普通用户',
    description: '别让基础问题堵住人工，把标准答复和常见问法先交给 AI 扛住。',
  },
  {
    title: '高潜用户',
    description: '识别出有价值但还没被认真接住的人，响应更快，话术更稳，别让机会白白滑走。',
  },
  {
    title: 'VIP',
    description: '不再排队，不再重复描述，第一时间接人工，把服务密度直接拉满。',
  },
  {
    title: '大 R',
    description: '速度、态度、升级路径全部优先，主管介入要前置，不能让用户觉得自己被当普通工单处理。',
  },
];

const stageCards = [
  {
    icon: Bot,
    title: '第一步接待，让 AI 先顶上去',
    description:
      '简单问题直接答，用户着急、生气、反复追问时先被识别出来。碰到 VIP 和大 R，不浪费一秒，立刻转人工。',
  },
  {
    icon: HeartHandshake,
    title: '转人工后，继续做最贴心的辅助',
    description:
      '把用户信息、问题摘要、历史记录直接摆在眼前，再给到安抚话术和计时提醒，让客服不慌、不漏、不超时。',
  },
  {
    icon: Gem,
    title: 'VIP 跟进必须全程盯紧',
    description:
      '工单优先级、专人负责、进度同步、超时提醒，尤其是大 R，要能把主管及时拉进来，保证服务不掉链。',
  },
  {
    icon: TimerReset,
    title: '最后把流程真正收拢成闭环',
    description:
      '满意度、24 小时回访、不满意自动升级、最终自动归档，全流程不再靠人工脑子硬记。',
  },
];

const supportCards = [
  {
    icon: BrainCircuit,
    title: '先“看懂这个人”',
    description:
      '不是简单看一条消息，而是综合角色、活跃度、付费价值和情绪状态，先判断该用什么优先级和服务语气。',
  },
  {
    icon: MessageCircleWarning,
    title: '识别情绪，不让矛盾继续升温',
    description:
      '用户一急、一冲、一反复，系统就该知道这是需要安抚、需要提速，还是需要马上交给真人。',
  },
  {
    icon: Clock3,
    title: '把人工从重复问题里解放出来',
    description:
      '把最标准、最重复、最机械的环节自动化，客服才有余力去处理真正要经验和判断的沟通。',
  },
];

const guardrailItems = [
  '账号安全、充值纠纷、舆情风险、大额补偿，必须优先交给人工。',
  '大 R 最在意的，往往不只是问题本身，还有被重视的感觉，这部分不能让 AI 硬顶。',
  'AI 只做重复、繁琐、标准化、可审计的事；现金、风险、关系、面子，全都要给人工留足主动权。',
];

const realityNotes = [
  '现在只完成了企微客服平台的第一段接入，已经能开始为人工节省时间。',
  '“简单问题自动答、识别情绪、VIP 和大 R 自动转人工”这套 agent 还在后续规划里。',
  'AI 识别不了游戏等级，本质上更像数据接入问题，不完全是 AI 能力问题。',
  '如果游戏后台能提供可信接口，理论上就能拿到等级、价值分层和活跃度标签。',
  '真正难点在于账号映射、接口权限、实时性、数据一致性和风控边界，这些都需要一起设计。',
];

const floatingDecorations = [
  { emoji: '✨', className: styles.floatA, top: '4%', left: '4%' },
  { emoji: '🎯', className: styles.floatB, top: '14%', right: '8%' },
  { emoji: '💬', className: styles.floatC, top: '48%', left: '2%' },
  { emoji: '🔥', className: styles.floatA, top: '72%', right: '6%' },
  { emoji: '⚡', className: styles.floatB, bottom: '12%', left: '12%' },
  { emoji: '💎', className: styles.floatC, bottom: '18%', right: '18%' },
];

function getAccentVars(index: number): CSSProperties {
  const accent = accentPalette[index % accentPalette.length];
  return {
    ['--panel-accent' as string]: accent.accent,
    ['--panel-border' as string]: accent.border,
    ['--panel-shadow-a' as string]: accent.shadowA,
    ['--panel-shadow-b' as string]: accent.shadowB,
  };
}

export default function MarketDetailPage() {
  const navigate = useNavigate();
  const { author = 'developer', pluginName = 'coming-soon' } = useParams();
  const pluginKey = `${decodeURIComponent(author)}/${decodeURIComponent(pluginName)}`;

  return (
    <div className={styles.pageShell}>
      <div className={styles.patternLayer} aria-hidden="true" />
      <div className={styles.meshLayer} aria-hidden="true" />

      {floatingDecorations.map((item) => (
        <span
          key={`${item.emoji}-${item.top ?? item.bottom}-${item.left ?? item.right}`}
          aria-hidden="true"
          className={`${styles.floatingEmoji} ${item.className}`}
          style={item}
        >
          {item.emoji}
        </span>
      ))}

      <div className="relative z-10 mx-auto flex max-w-7xl flex-col gap-8 px-4 py-6 sm:px-6 lg:px-10 lg:py-10">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Button
            variant="outline"
            onClick={() => navigate('/home/market')}
            className="h-12 rounded-full border-4 border-[#00f5d4] bg-[#120d24]/80 px-6 text-sm font-black uppercase tracking-[0.25em] text-[#f9f7ff] shadow-[0_0_24px_rgba(0,245,212,0.24)] hover:scale-[1.03] hover:bg-[#1d1337]"
          >
            <ArrowLeft className="size-4" />
            返回插件市场
          </Button>

          <div className="flex flex-wrap items-center gap-2 text-[11px] font-black uppercase tracking-[0.3em] text-[#fff1fe]">
            <span className={styles.statusChip}>开发者暂未上线</span>
            <span className={styles.miniChip}>彩蛋页</span>
            <span className={styles.miniChip}>占位详情</span>
          </div>
        </div>

        <section
          className={`${styles.panel} ${styles.heroPanel}`}
          style={getAccentVars(0)}
        >
          <div className={styles.heroWord} aria-hidden="true">
            NOT LIVE
          </div>
          <div className="grid gap-8 xl:grid-cols-[1.15fr_0.85fr]">
            <div className="relative z-10 space-y-6">
              <div className="flex flex-wrap items-center gap-3 text-xs font-black uppercase tracking-[0.35em] text-[#fff4fd]">
                <span className={styles.ribbonTag}>开发者暂未上线</span>
                <span className={styles.inlineBadge}>当前占位：{pluginKey}</span>
              </div>

              <div className="space-y-4">
                <p className={styles.kicker}>插件市场详情页彩蛋</p>
                <h1 className={styles.heroTitle}>
                  我希望它先帮我们
                  <span className={styles.gradientWord}>“看懂这个人”</span>
                </h1>
                <p className={styles.heroDescription}>
                  这个项目最初不是为了再造一个会说话的机器人，而是想把客服一线最容易掉链子的地方，交给一个能按标准执行的系统：先判断这个用户是谁、值不值得提速、该不该马上转人工，再决定怎么接待。
                </p>
                <p className={styles.heroDescription}>
                  不用客服再去翻数据、翻聊天记录、翻工单历史；系统自己先把“普通用户、高潜、VIP、大
                  R”分出来，把速度、态度、升级路径都按培训标准推到位。
                </p>
              </div>

              <div className="flex flex-wrap gap-3">
                <div className={styles.badgePill}>
                  <Sparkles className="size-4" />
                  先看懂用户，再决定服务力度
                </div>
                <div className={styles.badgePill}>
                  <Users className="size-4" />
                  重复问题交给 AI，重要沟通留给人工
                </div>
              </div>
            </div>

            <div className="relative z-10 grid gap-4 sm:grid-cols-2 xl:grid-cols-1">
              {userLevels.map((item, index) => (
                <article
                  key={item.title}
                  className={styles.chaosCard}
                  style={getAccentVars(index + 1)}
                >
                  <p className={styles.cardEyebrow}>用户分层</p>
                  <h2 className={styles.cardTitle}>{item.title}</h2>
                  <p className={styles.cardBody}>{item.description}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="grid gap-6 lg:grid-cols-4">
          {stageCards.map((item, index) => {
            const Icon = item.icon;
            return (
              <article
                key={item.title}
                className={styles.panel}
                style={getAccentVars(index + 1)}
              >
                <div className="relative z-10 flex h-full flex-col gap-5">
                  <div className={styles.iconWrap}>
                    <Icon className="size-7" />
                  </div>
                  <div className="space-y-3">
                    <p className={styles.kicker}>服务链路 0{index + 1}</p>
                    <h2 className={styles.sectionTitle}>{item.title}</h2>
                    <p className={styles.sectionText}>{item.description}</p>
                  </div>
                </div>
              </article>
            );
          })}
        </section>

        <section
          className={`${styles.panel} ${styles.storyPanel}`}
          style={getAccentVars(2)}
        >
          <div className="relative z-10 grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
            <div className="space-y-4">
              <p className={styles.kicker}>为什么要做这个</p>
              <h2 className={styles.sectionHeadline}>让人工把精力放回真正重要的沟通</h2>
              <p className={styles.sectionText}>
                如果简单问题都还靠人工逐条回，真正要经验、判断、安抚和关系维护的那部分就永远做不深。这个系统的意义，不是替代客服，而是把他们从重复劳动里解放出来，让每一次高价值沟通都更稳、更快、更像样。
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              {supportCards.map((item, index) => {
                const Icon = item.icon;
                return (
                  <article
                    key={item.title}
                    className={styles.storyCard}
                    style={getAccentVars(index + 3)}
                  >
                    <Icon className="size-8 text-[var(--panel-border)]" />
                    <h3 className={styles.storyTitle}>{item.title}</h3>
                    <p className={styles.storyText}>{item.description}</p>
                  </article>
                );
              })}
            </div>
          </div>
        </section>

        <section className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
          <article className={styles.panel} style={getAccentVars(3)}>
            <div className="relative z-10 space-y-5">
              <p className={styles.kicker}>边界感</p>
              <h2 className={styles.sectionHeadline}>有些事情，AI 就不该硬顶</h2>
              <div className="grid gap-4">
                {guardrailItems.map((item, index) => (
                  <div key={item} className={styles.guardrailItem}>
                    {index === 0 ? (
                      <ShieldAlert className="size-5 shrink-0 text-[#ffe600]" />
                    ) : index === 1 ? (
                      <TriangleAlert className="size-5 shrink-0 text-[#ff6b35]" />
                    ) : (
                      <HeartHandshake className="size-5 shrink-0 text-[#00f5d4]" />
                    )}
                    <p className={styles.sectionText}>{item}</p>
                  </div>
                ))}
              </div>
            </div>
          </article>

          <article className={styles.panel} style={getAccentVars(4)}>
            <div className="relative z-10 space-y-5">
              <p className={styles.kicker}>当前阶段</p>
              <h2 className={styles.sectionHeadline}>现在已经做到哪一步，还差什么</h2>
              <div className="grid gap-3">
                {realityNotes.map((item) => (
                  <div key={item} className={styles.realityItem}>
                    <Star className="size-4 shrink-0 text-[#ffe600]" />
                    <p className={styles.sectionText}>{item}</p>
                  </div>
                ))}
              </div>
            </div>
          </article>
        </section>
      </div>
    </div>
  );
}
