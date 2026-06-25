# 2026 世界杯模拟盘

单文件 Python 项目，浏览器访问即可投注。

## 部署

```bash
# 方式1：直接用预生成的 index.html
python3 -m http.server 8765
# 访问 http://<ip>:8765/

# 方式2：重新生成 index.html
python3 build.py   # 生成 index.html（53KB build.py -> 111KB index.html）
python3 -m http.server 8765
```

## 功能

- 登录注册（SHA256 密码 + 盐，注册赠送 ¥2000 体验金）
- 小组赛积分榜
- 赛程与投注
- 投注单 + 历史记录 + 中奖查询

## 数据存储

纯前端 localStorage，每个用户隔离：
- `wc_users`: `[{username, salt, hash, balance, createdAt}]`
- `wc_session`: 当前登录用户名
- `wc_u_<username>_slip/bets/parlayOn/parlayN`: 用户投注数据

## 文件说明

- `build.py` (53KB): 生成器，从 JSON 数据 + 模板生成 `index.html`
- `index.html` (111KB): 最终部署文件，单文件应用（含 CSS/JS/数据）
- `wc_*.json`: 球队/分组/比赛数据源
- `inject_data.py`: 数据注入辅助脚本
