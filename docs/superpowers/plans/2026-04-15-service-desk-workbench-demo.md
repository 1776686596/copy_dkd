# Service Desk Workbench Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增一个独立的客服工作台 Demo 页面，用静态假数据演示概览态/工作态双态切换、左侧队列固定、右侧聊天主展示和 AI 建议展开交互。

**Architecture:** 在现有 `HomeLayout` 下新增独立路由 `/home/service-desk-demo`，页面内部使用本地静态数据和 `IntersectionObserver` 驱动概览态与工作态切换。Demo 页面不接真实接口，不复用正式客服台的加载逻辑，但尽量延续现有 UI 组件和视觉语言，确保后续可回填到正式页。

**Tech Stack:** React 19, TypeScript, React Router, Tailwind CSS, Radix UI, Vite

---

### Task 1: 接入独立 Demo 路由

**Files:**
- Modify: `LangBot/web/src/router.tsx`
- Create: `LangBot/web/src/app/home/service-desk-demo/page.tsx`

- [ ] **Step 1: 先运行失败断言**

```bash
node - <<'NODE'
const fs = require('fs');
const router = fs.readFileSync('/home/daisheng/code/copy_dkd/LangBot/web/src/router.tsx', 'utf8');
const demoPagePath = '/home/daisheng/code/copy_dkd/LangBot/web/src/app/home/service-desk-demo/page.tsx';
function assert(cond, msg) { if (!cond) throw new Error(msg); }
assert(router.includes('/home/service-desk-demo'), '缺少客服工作台 demo 路由');
assert(fs.existsSync(demoPagePath), '缺少客服工作台 demo 页面文件');
console.log('demo route exists');
NODE
```

Expected: FAIL，提示缺少 demo 路由或页面文件

- [ ] **Step 2: 新增最小路由和页面骨架**

在 `router.tsx` 中新增 lazy import 和 `/home/service-desk-demo` 路由，使用 `HomeLayout` 包裹。  
创建 `page.tsx`，先导出一个最小可渲染组件，例如：

```tsx
export default function ServiceDeskDemoPage() {
  return <div className="h-full">Service Desk Demo</div>;
}
```

- [ ] **Step 3: 重跑失败断言**

Run the same `node` command from Step 1.  
Expected: PASS

### Task 2: 实现双态工作台 Demo 页面

**Files:**
- Modify: `LangBot/web/src/app/home/service-desk-demo/page.tsx`

- [ ] **Step 1: 先补失败断言**

```bash
node - <<'NODE'
const fs = require('fs');
const demoPage = fs.readFileSync('/home/daisheng/code/copy_dkd/LangBot/web/src/app/home/service-desk-demo/page.tsx', 'utf8');
function assert(cond, msg) { if (!cond) throw new Error(msg); }
assert(demoPage.includes('IntersectionObserver'), '缺少双态切换监听');
assert(demoPage.includes('AI 建议'), '缺少 AI 建议入口');
assert(demoPage.includes('会话队列'), '缺少左侧会话队列区域');
assert(demoPage.includes('全部会话'), '缺少工作态顶部筛选工具条');
console.log('demo layout contract ok');
NODE
```

Expected: FAIL，因为当前页面骨架尚未包含这些结构

- [ ] **Step 2: 实现页面主体**

页面至少包含以下部分：

```tsx
const DEMO_SESSIONS = [...];
const DEMO_MESSAGES = {...};
const DEMO_SUGGESTIONS = {...};

export default function ServiceDeskDemoPage() {
  const [activeTab, setActiveTab] = useState<'workbench' | 'rules' | 'materials'>('workbench');
  const [selectedSessionId, setSelectedSessionId] = useState(DEMO_SESSIONS[0].id);
  const [queueFilter, setQueueFilter] = useState('all');
  const [query, setQuery] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [replyText, setReplyText] = useState('');
  const [isWorkbenchMode, setIsWorkbenchMode] = useState(false);
  const overviewRef = useRef<HTMLDivElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const root = scrollRef.current;
    const target = overviewRef.current;
    if (!root || !target) return;
    const observer = new IntersectionObserver(
      ([entry]) => setIsWorkbenchMode(entry.intersectionRatio < 0.05),
      { root, threshold: [0, 0.05, 1] },
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={scrollRef} className="h-full overflow-y-auto">
      ...
    </div>
  );
}
```

实现要求：

- 滑动前显示完整概览区
- 滑动后顶部固定显示页签 + 队列筛选工具条
- 左侧 `会话队列` 固定
- 右侧直接展示聊天内容
- 底部操作区固定
- `AI 建议` 按钮点击后，在按钮上方展开建议区

- [ ] **Step 3: 重跑失败断言**

Run the same `node` command from Step 1.  
Expected: PASS

### Task 3: 预览前验证

**Files:**
- Verify: `LangBot/web/src/router.tsx`
- Verify: `LangBot/web/src/app/home/service-desk-demo/page.tsx`

- [ ] **Step 1: 运行前端构建**

Run:

```bash
cd /home/daisheng/code/copy_dkd/LangBot/web && npm run build
```

Expected: PASS，`tsc` 和 `vite build` 均成功

- [ ] **Step 2: 启动本地预览**

Run:

```bash
cd /home/daisheng/code/copy_dkd/LangBot/web && npm run dev -- --host 127.0.0.1 --port 4173
```

Expected: 能输出本地访问地址，供用户查看 demo 页面

- [ ] **Step 3: 记录关闭命令**

在交付预览地址时同时记录进程 ID 或关闭方式。  
用户确认看完后，执行停止命令释放端口，例如：

```bash
kill <PID>
```
