# ADR-0002：鉴权选型（登录凭证签发库 + 密码哈希库）

- **状态**：**Approved**（开发者 2026-09-12 批复"全部批准"，随 W5 第 3 组落地）
- **日期**：2026-09-12
- **决策来源**：`openspec/changes/add-doc-ingest-pipeline/tasks.md` 3.1 / 3.2；`docs/HANDOFF.md` 第二节第 1 条（第 3 组整组阻塞在停机点）
- **影响范围**：`backend/pyproject.toml` 依赖清单 → `backend/Dockerfile` 镜像内容；`users.password_hash` 的写入格式；3.1–3.3 及后续所有需要"当前用户"的接口

---

## 背景

### 这次选型为什么不得不做

第 3 组（账号体系）整组阻塞：`3.1` 注册要把密码落成不可还原的摘要，`3.2` 登录要签发可校验的凭证，而这两件事当前**一个库都没有**。

实测当前状态（命令见文末"验证证据"）：

- `backend/pyproject.toml` 的 `dependencies` 只有 FastAPI / SQLAlchemy / Celery 等运行件，**无任何 JWT 或密码哈希包**
- `backend/.venv` 内 `pip list` 过滤 `jwt|jose|passlib|argon|bcrypt|crypt` → **0 命中**
- `backend/app/` 下**没有** `core/security.py`；`app/api/deps.py` 只是 `Settings` 的转发壳子，注释已预留"3.x 起在此基础上加鉴权依赖"
- 本仓库依赖只声明在 `pyproject.toml`（无 `requirements.txt`、无 lockfile）；镜像构建是 `python:3.12-slim` + `pip install .`
  → **新增依赖必须落进 `pyproject.toml` 才会进镜像**，只在本地 venv 里装是无效的

新增依赖按 `AGENTS.md` §3 / §6 属**架构级决策**，须先出 ADR 等批，不得自行选型。

### 已经就位、本次不再重议的约束

| 约束 | 出处 | 对选型的影响 |
| --- | --- | --- |
| `users.password_hash` 为 `VARCHAR(255)`，模型注释写明"长度按 argon2id 输出留余量" | `backend/app/models/user.py`（任务 2.1） | 255 对 bcrypt（60 字符）与 argon2id（**实测 97 字符**）都绰绰有余；**但列宽是按 argon2id 预留的** |
| `JWT_ALGORITHM=HS256`（对称）、`TOKEN_EXPIRE_MINUTES=1440`、`PASSWORD_MIN_LENGTH=8` 已在配置系统内 | `backend/app/core/config.py`；任务 1.4 | 选型只需覆盖 **HS256 对称签名**，不需要非对称能力；有效期与强度阈值都不在本次决策范围 |
| `SECRET_KEY` 已是"本期必需项"，缺失即启动失败 | 同上 | 凭证签名密钥**不新增配置项**，直接用 `SECRET_KEY` |
| 密码 MUST NOT 可还原存储；用户名唯一；登录失败**不区分**"用户不存在"与"密码错误" | `openspec/changes/.../specs/user-auth/spec.md` | 哈希必须是单向慢哈希；登录失败文案与错误码必须同一条 |
| 状态列用 `VARCHAR(20)` + 应用层枚举，避免 PG 原生枚举的 `ALTER TYPE` 负担 | 第 2 组决策（`docs/findings.md` D-025 上下文） | 只影响 3.x 的写法风格，不影响选型 |

### 与宪法两条原则的合规声明（`AGENTS.md` §1 强制）

- **原则 I（原生实现保护清单）**：保护清单列举的是分块 / 双路召回 / RRF / 重排 / 上下文压缩 / mini-agent 工具循环 / 引用对齐 / 语义缓存，**不含密码学与令牌签发**。反过来说，密码学是"**不该自研**"的领域——本 ADR 用库，不违反原则 I，反而是合规方向。
- **原则 II（技术栈锁定）**：技术栈清单（Python 3.12 / FastAPI / Pydantic v2 / SQLAlchemy 2.0 async / Alembic / PG16 / Milvus / Celery+Redis / LangGraph；前端 React 18 + TS + Vite）**未列任何鉴权库**，所以本次属"技术栈新增"，必须经本 ADR 批准后落地。

---

## 决策

### 结论

| 用途 | 选型 | 版本约束 | 理由一句话 |
| --- | --- | --- | --- |
| 登录凭证签发与校验 | **PyJWT** | `pyjwt>=2.9` | 维护活跃、纯 Python 零编译依赖、API 面窄、是 FastAPI 官方安全文档的默认选择 |
| 密码哈希 | **argon2-cffi**（直接用，不经任何门面库） | `argon2-cffi>=23.1` | argon2id 是当前密码哈希的推荐算法，且 `password_hash` 列宽本就是按它预留的 |

**两个库，不引入第三个。** 传输层提取凭证用 FastAPI 自带的 `OAuth2PasswordBearer`（零新依赖）。

### D1. 凭证签发用 PyJWT

- 算法**只用配置里的 `JWT_ALGORITHM`（当前 HS256）**，密钥取 `SECRET_KEY`。单后端签发、单后端校验，无第三方验签需求，对称签名足够；RS256 要管密钥对与轮换，本项目无收益（见"被否方案"）。
- 校验时**显式传算法白名单**：`jwt.decode(token, SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])`。
  绝不允许 `algorithms=None`，也绝不允许拿 token header 里的 `alg` 当依据——**这正是 2024 年 python-jose 那个算法混淆漏洞（CVE-2024-33663）的根因**，写代码时把这条当红线。
- 为什么不用门面库：`OAuth2PasswordBearer` 负责"从 `Authorization: Bearer` 里取字符串"，取出后的解析与校验是我们自己的两行代码，没有抽象空间。

### D2. 密码哈希用 argon2-cffi 的 argon2id

- 直接调 `argon2.PasswordHasher()`（默认算法即 argon2id）的 `hash()` / `verify()` / `check_needs_rehash()`，**不套 passlib**。
- 参数用**库默认**（`time_cost=3`、`memory_cost=64 MiB`、`parallelism=4`），且**不暴露成 `Settings` 配置项**。
  理由：这两个参数是"抗爆破强度"的直接旋钮，做成环境变量只会给人"随手调小一点跑得快些"的机会，而调小的后果是密码库整体变弱——它属于代码常量，不属于部署配置。
  （若后续测试耗时确实难以接受，用依赖注入替换一个低开销 profile，**仍然不进配置**。）

  > 对照澄清（2026-09-12 追加）：`PASSWORD_MIN_LENGTH` / `PASSWORD_MAX_LENGTH` **是**进 `Settings` 的。
  > 它们只决定"多长算合法输入"，不改变每次哈希的计算代价，属输入护栏；上面两个才是抗爆破旋钮。两者性质不同，别混为一谈。
- `password_hash VARCHAR(255)` 的列宽按 argon2id 的编码输出预留，本次选型与任务 2.1 的模型设计一致，**无需改 DDL**（这一点很重要：改列宽会再触发一次 DDL 停机点）。

### D3. 依赖落点与写法

- 加进 `backend/pyproject.toml` 的 `dependencies`（**不是** `[project.optional-dependencies].dev`）——镜像构建走 `pip install .`，只有 `dependencies` 会进生产镜像。
- 版本写法沿用仓库既有风格（只给下限）：`"pyjwt>=2.9"`、`"argon2-cffi>=23.1"`。
- **顺带记一个已存在的欠账**：本仓库没有任何 lockfile，依赖解析结果不可重现（同一份 `pyproject.toml` 在不同时间装出的版本可能不同）。这超出本 ADR 范围，不在本次决策内，建议单独立项处理。

### D4. 配套约定（不属选型，但与选型同时定下，免得 3.x 实现时反复）

选型本身会引出几个"必须现在说清、否则实现时各写各的"的接口约定，一并记在这里：

- **payload 只放三个声明**：`sub`（user_id 的字符串形式）、`iat`、`exp`（= `iat` + `TOKEN_EXPIRE_MINUTES` × 60）。
  **不放** `username`、`role` 之类的业务字段——3.3 要求"身份只由凭证推导"，凭证里字段越多，"某个字段被当权限用"的口子就越多；归属一律回库按 `sub` 查。
- **传输**：`Authorization: Bearer <token>`。
- **校验失败一律 401**（过期 / 签名不符 / 结构非法 / `sub` 不是合法 id 都算），响应体走 1.6 的错误契约 `{code, message}`，文案提示需要重新登录；**不外泄失败细节**（不区分"过期"与"伪造"）。
- **登录失败不区分两种原因，且要防时序侧信道**：用户名不存在时也要**跑一次假的哈希校验**再返回同一个错误码，否则"响应快 = 用户不存在"本身就是泄漏。这一条是 `user-auth` spec「凭证不正确」场景的实现要点，光对齐文案不够。

---

## 被否方案

| 方案 | 否决理由 |
| --- | --- |
| **python-jose** | 2024 年连出两个高危公告（CVE-2024-33663 算法混淆 / CVE-2024-33664 JWT bomb，GHSA 评级 Critical/CVSS 7.4），**虽然 3.4.0 已修、现行 3.5.0 不再受影响**，但它是本项目唯一需要额外跟踪 CVE 历史的候选；且算法后端拆在 extras 里，默认安装的能力集与文档示例不一致，容易在运行时才暴露。功能上它能做的事 PyJWT 都能做，换不来任何东西。 |
| **自研 HS256**（`hmac` + `hashlib` + `base64` + `json`，约 40 行） | 唯一优势是"少一个依赖"，但代价是把 JWT 的坑重踩一遍——坑几乎全在**校验侧**：算法白名单、`exp`/`nbf` 的类型与时钟容差、base64url 去 padding、header 与 payload 的分段校验、`alg=none` 拒绝。<br>更关键的是：这是整个 W5 里**唯一会被安全审计问"你为什么自己写"**的地方。保护清单要求原生实现的是"面试要讲清为什么"的算法；密码学恰恰相反——自研等于给自己制造一个讲不清的理由。 |
| **passlib 做哈希门面**（`CryptContext`，FastAPI 老教程的写法） | 上游**已实质停滞**：PyPI 最新版 `1.7.4` 发布于 **2020-10-08，至今 5 年无新版**；与 `bcrypt>=4.1` 不兼容（`bcrypt.__about__` 被移除），Gentoo / Debian / pyca 均有实证 bug（Gentoo#925289、Debian#1082011、pyca/bcrypt#684），下游发行版只能各自打补丁。<br>而且它提供的是"多算法统一门面 + 自动迁移"的抽象，本项目**只用一种算法**，这层抽象没有服务对象。 |
| **直接用 bcrypt** | 成熟、有预编译 wheel（实测可解析），但它有 72 字节输入截断的永久性设计限制；抗 GPU/ASIC 能力弱于 argon2id；且任务 2.1 已经把 `password_hash` 列宽**按 argon2id 预留**，选 bcrypt 会让这条预留失去意义。 |
| **stdlib `hashlib.scrypt` / `pbkdf2_hmac`** | 零依赖是唯一优势。但参数调优、salt 生成与编码、摘要格式的版本标记与迁移，全部要自己维护——等于自研了半套密码格式。用加密库解决"零依赖"，得不偿失。 |
| **`authlib`** | 它是 OAuth2 / OIDC 的完整框架（授权服务器、客户端、JWKS、各类 grant）。我们只有"用户名 + 密码换 token"一条路径，引入它属于用大炮打蚊子，依赖面积和概念负担都远超需求。 |
| **RS256 非对称签名** | 只在"有第三方需要独立验签"或"签名服务与验签服务必须分权"时才值。本项目签名与校验同进程、同一份 `SECRET_KEY`，RS256 只增加密钥管理成本，不带来安全收益。 |

> 注：**`cryptography` 从未进入候选**——本项目只用对称 HS256，不需要非对称密码学能力；引入它会把依赖闭包里多出一个需要常年跟安全公告的重型包。

---

## 请重点确认的三点

本 ADR 只出方案，选型由你拍板。需要你确认的是：

1. **JWT 用 PyJWT**（而不是 python-jose）——同意 / 换人。
2. **密码哈希用 argon2id**（而不是 bcrypt 或 stdlib）——注意选它等于**不改 DDL**；若你更倾向 bcrypt，请一并说明，因为那会让 2.1 的列宽预留失去意义（但仍不需要改列宽，255 装得下）。
3. **D4 的四条配套约定**（payload 只放 `sub/iat/exp`、401 归一、登录失败防时序侧信道、算法白名单）——这几条是我按规格推出的实现口径，若你有不同意见，纠正后我再进 3.x。

---

## 验证证据（可复现命令）

以下事实均为 2026-09-12 实测，非文档推测。

```bash
export PATH="/d/Docker/App/resources/bin:/c/Users/ASUS/.workbuddy/binaries/PortableGit/versions/1.2.0/cmd:/c/Users/ASUS/.workbuddy/binaries/PortableGit/versions/1.2.0/bin:/c/Users/ASUS/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:/d/nvm/nodejs:/usr/bin:/bin"
cd backend

# 1) 当前确实没有任何 JWT / 密码哈希依赖
.venv/Scripts/python.exe -m pip list | grep -iE "jwt|jose|passlib|argon|bcrypt|crypt"
# → 0 命中

# 2) 候选库在本机（cp312 / win_amd64）能否解析
.venv/Scripts/python.exe -m pip install --dry-run --no-deps pyjwt argon2-cffi bcrypt python-jose passlib
# → 解析出 PyJWT-2.14.0 / argon2-cffi-25.1.0 / bcrypt-5.0.0 / python-jose-3.5.0 / passlib-1.7.4

# 3) 含传递依赖的完整闭包（确认 Win 侧无源码编译）
.venv/Scripts/python.exe -m pip install --dry-run pyjwt argon2-cffi
# → Would install PyJWT-2.14.0 argon2-cffi-25.1.0 argon2-cffi-bindings-26.1.0 cffi-2.1.1 pycparser-3.0
.venv/Scripts/python.exe -m pip download --no-deps --dest /tmp/depchk pyjwt argon2-cffi argon2-cffi-bindings cffi
# → 全部为预编译 wheel：argon2_cffi_bindings-26.1.0-**cp310-abi3-win_amd64**.whl、cffi-2.1.1-**cp312-cp312-win_amd64**.whl
```

| 事实 | 结果 | 来源 |
| --- | --- | --- |
| PyJWT 最新版 | **2.14.0**，2026-09-11 发布 | PyPI JSON API |
| argon2-cffi 最新版 | **25.1.0**，2025-06-03 发布 | PyPI JSON API |
| bcrypt 最新版 | 5.0.0，2025-09-25 发布 | PyPI JSON API |
| python-jose 最新版 | 3.5.0，2025-05-28 发布 | PyPI JSON API |
| passlib 最新版 | **1.7.4，2020-10-08 发布（停更 5 年）** | PyPI JSON API |
| passlib × bcrypt≥4.1 不兼容 | `AttributeError: module 'bcrypt' has no attribute '__about__'`；部分下游（keystone、ansible）直接失败 | Gentoo bug 925289、Debian bug 1082011、pyca/bcrypt issue 684 |
| python-jose CVE | CVE-2024-33663 / CVE-2024-33664，**3.4.0 已修**（现 3.5.0 不受影响） | GHSA-6c5p-j8vq-pqhj、Debian #1070375 |

---

## 批准后要做的动作

1. `backend/pyproject.toml` 的 `dependencies` 追加 `"pyjwt>=2.9"` 与 `"argon2-cffi>=23.1"`（**注意：同一文件的编辑串行提交，改完复核内容**——第 1 组曾因并行编辑丢过字段，代价是 worker/beat 反复重启）
2. 本机安装：`cd backend && .venv/Scripts/python.exe -m pip install -e ".[dev]"`
3. **重建镜像（不是 restart）**：`docker compose up -d --build`。依赖变更必须重建；建完进容器复核一遍，因为 **linux manylinux wheel 我这台机器没实测过**：
   `docker exec docmind-api python -c "import jwt, argon2; print(jwt.__version__, argon2.__version__)"`
   并再次经 nginx 打真实请求（第 1 组的教训：`docker compose ps` 报 healthy ≠ 对外链路可用）
4. 落地位置：`backend/app/core/security.py` 放"哈希 + 签发/校验"两组纯函数（无 IO、无 DB）；`backend/app/api/deps.py` 放 3.3 的鉴权依赖（`get_current_user`）
5. 验证：`pytest -q` 汇总行必须确认 **0 skipped**——第 3 组起有真实库断言，"依赖不可达就跳过"仍会伪装成通过
6. 回写：`docs/findings.md` 追加决策条目；本 ADR 状态改 **Approved**；`docs/progress.md` 记一条

## 待验证 / 风险

1. ~~**镜像侧未实测**~~ → **已验证（2026-09-12）**：`docker compose up -d --build` 后进容器复核，
   `docker exec docmind-api python -c "import jwt, argon2"` → `pyjwt 2.14.0` / `argon2-cffi 25.1.0`，`sys.platform = linux`，
   `PasswordHasher()` 产出 `$argon2id$v=19$m=65536,t=3,p=4$…` → **linux manylinux wheel 直接可用，无需编译，也没有新增构建依赖**。
2. **argon2id 的耗时**：实测默认参数（`time_cost=3` / `memory_cost=64MiB` / `parallelism=4`）单次哈希 **56ms**、校验 **55ms**。
   已按此处置：`app/services/auth.py` 一律 `asyncio.to_thread` 丢线程池，不在事件循环里算——否则一次登录请求会把整个进程卡住 56ms。
   若后续测试耗时明显恶化，按 D2 用依赖注入换低开销 profile，**不改成配置项**。
3. **`SECRET_KEY` 轮换 = 全体凭证立即失效**：本期只有一份密钥，无 kid / 双密钥并存机制。属可接受的开发期取舍，但要在 3.2 的实现注释里写明，避免把"换密钥"当成一次无害操作。
4. **无 lockfile**（见 D3）：依赖解析不可重现，与本 ADR 无关但确实存在，建议单独立项。
