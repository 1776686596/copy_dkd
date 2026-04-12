# WeCom CS AI Service Desk V2 Acceptance Checklist

## 自动化验证

- [x] AI assist draft can be generated without auto-sending
- [x] Operator can claim, release, and return sessions to AI
- [x] Workbench search and grouping behave as expected
- [x] Session detail shows context and timeline
- [x] Quick replies can be inserted and sent manually

## 构建与质量

- [x] Service-desk unit test suite passes
- [x] Frontend lint passes
- [x] Frontend build passes

## 待单独确认

- [ ] WeCom real-chain verification is marked separately from automated verification

说明：
- 自动化验证覆盖后端 service-desk 单测、前端 lint、前端 build。
- 真实企微链路联调依赖外部环境与真实账号，不纳入本地自动化通过条件。
