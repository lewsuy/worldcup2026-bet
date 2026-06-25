"""生成 index.html — 2026 世界杯模拟盘单文件应用。"""
import json
from pathlib import Path

proj = Path(r'D:\VSCodeProject\worldcup2026-bet')
with open(proj / 'wc_games_slim.json', encoding='utf-8') as f:
    games = json.load(f)['games']
with open(proj / 'wc_groups.json', encoding='utf-8') as f:
    groups = json.load(f)['groups']
with open(proj / 'wc_teams.json', encoding='utf-8') as f:
    teams = json.load(f)['teams']

# 国家英文 -> 中文 映射
COUNTRY_CN = {
    'Mexico': '墨西哥', 'South Africa': '南非', 'South Korea': '韩国', 'Czech Republic': '捷克',
    'Canada': '加拿大', 'Bosnia and Herzegovina': '波黑', 'Qatar': '卡塔尔', 'Switzerland': '瑞士',
    'Brazil': '巴西', 'Morocco': '摩洛哥', 'Haiti': '海地', 'Scotland': '苏格兰',
    'United States': '美国', 'Paraguay': '巴拉圭', 'Australia': '澳大利亚', 'Turkey': '土耳其',
    'Germany': '德国', 'Curaçao': '库拉索', 'Ivory Coast': '科特迪瓦', 'Ecuador': '厄瓜多尔',
    'Netherlands': '荷兰', 'Japan': '日本', 'Sweden': '瑞典', 'Tunisia': '突尼斯',
    'Belgium': '比利时', 'Egypt': '埃及', 'Iran': '伊朗', 'New Zealand': '新西兰',
    'Spain': '西班牙', 'Cape Verde': '佛得角', 'Saudi Arabia': '沙特', 'Uruguay': '乌拉圭',
    'France': '法国', 'Senegal': '塞内加尔', 'Iraq': '伊拉克', 'Norway': '挪威',
    'Argentina': '阿根廷', 'Algeria': '阿尔及利亚', 'Austria': '奥地利', 'Jordan': '约旦',
    'Portugal': '葡萄牙', 'Democratic Republic of the Congo': '刚果(金)', 'Uzbekistan': '乌兹别克斯坦',
    'Colombia': '哥伦比亚', 'England': '英格兰', 'Croatia': '克罗地亚', 'Ghana': '加纳',
    'Panama': '巴拿马',
}

# 给 teams 加 name_cn 字段
for t in teams:
    t['name_cn'] = COUNTRY_CN.get(t['name_en'], t['name_en'])

# 给 games 里 home/away_team_name_en 也补一个 *_cn（方便直接用）
def _name_cn(en):
    return COUNTRY_CN.get(en, en)
for g in games:
    g['home_team_name_cn'] = _name_cn(g.get('home_team_name_en', ''))
    g['away_team_name_cn'] = _name_cn(g.get('away_team_name_en', ''))

games_json = json.dumps(games, ensure_ascii=False)
groups_json = json.dumps(groups, ensure_ascii=False)
teams_json = json.dumps(teams, ensure_ascii=False)

html = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>🏆 2026 世界杯模拟盘</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  background: #0f1419; color: #e8eef5; min-height: 100vh; padding-bottom: 60px; }
header { position: sticky; top: 0; z-index: 100; background: linear-gradient(180deg, #1a2332 0%, #0f1419 100%);
  border-bottom: 2px solid #00d4ff; padding: 14px 24px; display: flex; justify-content: space-between; align-items: center;
  box-shadow: 0 2px 12px rgba(0, 212, 255, 0.15); }
header h1 { font-size: 20px; color: #00d4ff; }
.balance { display: flex; align-items: center; gap: 12px; font-size: 14px; }
.balance .amount { color: #ffd700; font-weight: bold; font-size: 18px; }
.btn { background: #00d4ff; color: #0f1419; border: none; padding: 6px 14px; border-radius: 4px; cursor: pointer; font-weight: 600; font-size: 13px; transition: all 0.2s; }
.btn:hover { background: #00b8e6; transform: translateY(-1px); }
.btn-sm { padding: 4px 10px; font-size: 12px; }
.btn-danger { background: #ff4757; color: #fff; }
.btn-danger:hover { background: #ee3344; }
.btn-ghost { background: transparent; border: 1px solid #00d4ff; color: #00d4ff; }
.tabs { display: flex; background: #1a2332; border-bottom: 1px solid #2a3445; padding: 0 16px; position: sticky; top: 60px; z-index: 99; }
.tab { padding: 14px 20px; cursor: pointer; color: #8a96a8; font-weight: 500; border-bottom: 3px solid transparent; transition: all 0.2s; }
.tab:hover { color: #e8eef5; }
.tab.active { color: #00d4ff; border-bottom-color: #00d4ff; }
.container { max-width: 1400px; margin: 0 auto; padding: 20px; }
.filter-bar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; align-items: center; }
.filter-bar select, .filter-bar input { background: #1a2332; color: #e8eef5; border: 1px solid #2a3445; padding: 6px 10px; border-radius: 4px; font-size: 13px; }
.filter-bar label { color: #8a96a8; font-size: 13px; }
.live-indicator { display: inline-flex; align-items: center; gap: 4px; color: #ff4757; font-size: 12px; font-weight: 500; margin-left: auto; }
.refresh-btn { background: #1a2332; color: #00d4ff; border: 1px solid #2a3445; padding: 6px 12px; border-radius: 4px; font-size: 12px; cursor: pointer; transition: all 0.2s; }
.refresh-btn:hover { border-color: #00d4ff; background: #00d4ff22; }
.refresh-btn.loading { color: #8a96a8; border-color: #8a96a8; }
.groups-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
.group-card { background: #1a2332; border-radius: 8px; padding: 16px; border: 1px solid #2a3445; }
.group-card h3 { color: #00d4ff; margin-bottom: 12px; font-size: 18px; display: flex; align-items: center; gap: 8px; }
.group-card h3 .badge { background: #00d4ff; color: #0f1419; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: left; padding: 6px 4px; color: #8a96a8; font-weight: 500; font-size: 11px; text-transform: uppercase; border-bottom: 1px solid #2a3445; }
th.num, td.num { text-align: center; }
td { padding: 8px 4px; border-bottom: 1px solid #1f2937; }
tr:hover { background: rgba(0, 212, 255, 0.04); }
.team-cell { display: flex; align-items: center; gap: 8px; }
.team-cell img { width: 22px; height: 16px; object-fit: cover; border-radius: 2px; }
.pts-cell { color: #ffd700; font-weight: bold; }
.games-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 14px; }
.game-card { background: #1a2332; border-radius: 8px; padding: 14px; border: 1px solid #2a3445; position: relative; transition: all 0.2s; }
.game-card:hover { border-color: #00d4ff; transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0, 212, 255, 0.1); }
.game-card.finished { opacity: 0.6; }
.game-card.finished:hover { transform: none; border-color: #2a3445; box-shadow: none; }
.game-card.live { border-color: #ff4757; box-shadow: 0 0 12px rgba(255,71,87,0.25); background: linear-gradient(135deg, #1a2332 0%, #2a1a24 100%); }
.game-card.live:hover { border-color: #ff6b81; box-shadow: 0 4px 20px rgba(255,71,87,0.4); }
.status-live { display: inline-flex; align-items: center; gap: 4px; color: #ff4757; font-weight: 600; font-size: 11px; }
.live-dot { display: inline-block; width: 8px; height: 8px; background: #ff4757; border-radius: 50%; animation: live-pulse 1.2s ease-in-out infinite; }
@keyframes live-pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(1.3); } }
.score.live { color: #ff4757; font-weight: 700; }
.game-card .meta { display: flex; justify-content: space-between; color: #8a96a8; font-size: 11px; margin-bottom: 10px; }
.game-card .meta .type-tag { background: #2a3445; color: #00d4ff; padding: 2px 6px; border-radius: 3px; font-weight: 500; }
.game-card .meta .status-finished { color: #8a96a8; }
.game-card .meta .status-upcoming { color: #ffd700; }
.matchup { display: flex; align-items: center; justify-content: space-between; margin: 12px 0; }
.matchup .team { flex: 1; display: flex; align-items: center; gap: 8px; }
.matchup .team.away { flex-direction: row-reverse; text-align: right; }
.matchup .team img { width: 28px; height: 20px; object-fit: cover; border-radius: 2px; }
.matchup .team-name { font-size: 14px; font-weight: 500; }
.matchup .vs { padding: 0 12px; color: #8a96a8; font-size: 13px; }
.matchup .score { font-size: 22px; font-weight: bold; color: #00d4ff; padding: 0 12px; }
.scorers { font-size: 11px; color: #8a96a8; margin-top: 8px; line-height: 1.5; padding-top: 8px; border-top: 1px dashed #2a3445; }
.game-card .footer { display: flex; justify-content: space-between; align-items: center; margin-top: 10px; }
.bet-btn { background: linear-gradient(135deg, #00d4ff, #00b8e6); color: #0f1419; border: none; padding: 8px 18px; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 13px; }
.bet-btn:hover { background: linear-gradient(135deg, #00b8e6, #0099cc); }
.modal-overlay { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); z-index: 200; align-items: center; justify-content: center; padding: 20px; }
.modal-overlay.open { display: flex; }
.auth-overlay { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.85); z-index: 300; align-items: center; justify-content: center; padding: 20px; }
.auth-overlay.open { display: flex; }
.auth-modal { max-width: 400px; }
.auth-field { margin-bottom: 14px; }
.auth-field label { display: block; font-size: 12px; color: #8a96a8; margin-bottom: 4px; }
.auth-field input { width: 100%; background: #0f1419; color: #e8eef5; border: 1px solid #2a3445; padding: 10px 12px; border-radius: 4px; font-size: 14px; }
.auth-field input:focus { outline: none; border-color: #00d4ff; }
.auth-error { background: rgba(255,71,87,0.15); color: #ff4757; padding: 10px 12px; border-radius: 4px; font-size: 13px; margin-bottom: 14px; border: 1px solid rgba(255,71,87,0.3); }
.header-user { display: flex; align-items: center; gap: 10px; font-size: 13px; }
.header-user .name { color: #00d4ff; font-weight: 600; }
.modal { background: #1a2332; border-radius: 8px; padding: 24px; max-width: 520px; width: 100%; max-height: 90vh; overflow-y: auto; border: 1px solid #00d4ff; box-shadow: 0 8px 32px rgba(0,212,255,0.2); }
.modal h2 { color: #00d4ff; margin-bottom: 16px; font-size: 18px; }
.modal .game-info { background: #0f1419; padding: 12px; border-radius: 4px; margin-bottom: 16px; font-size: 13px; }
.modal .close-btn { float: right; background: none; border: none; color: #8a96a8; font-size: 24px; cursor: pointer; }
.modal .close-btn:hover { color: #fff; }
.play-type { margin-bottom: 16px; }
.play-type h3 { font-size: 14px; color: #00d4ff; margin-bottom: 8px; }
.options { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.options.goals { grid-template-columns: repeat(4, 1fr); }
.option { background: #0f1419; border: 1px solid #2a3445; padding: 10px 8px; border-radius: 4px; cursor: pointer; text-align: center; font-size: 13px; transition: all 0.2s; }
.option:hover { border-color: #00d4ff; }
.option.selected { background: #00d4ff; color: #0f1419; border-color: #00d4ff; font-weight: bold; }
.option .label { font-weight: 600; margin-bottom: 2px; }
.option .odds { font-size: 11px; color: #ffd700; }
.option.selected .odds { color: #0f1419; }
.amount-input { display: flex; align-items: center; gap: 8px; margin: 16px 0; }
.amount-input label { color: #8a96a8; font-size: 13px; }
.amount-input input { background: #0f1419; color: #e8eef5; border: 1px solid #2a3445; padding: 8px 12px; border-radius: 4px; flex: 1; font-size: 14px; }
.modal .actions { display: flex; gap: 10px; margin-top: 16px; }
.modal .actions .btn { flex: 1; padding: 10px; }
.betslip { background: #1a2332; border-radius: 8px; padding: 16px; }
.betslip-empty { text-align: center; padding: 40px; color: #8a96a8; }
.bet-item { background: #0f1419; padding: 12px; border-radius: 4px; margin-bottom: 10px; border-left: 3px solid #00d4ff; display: flex; justify-content: space-between; align-items: center; }
.bet-item .info { flex: 1; }
.bet-item .info .teams { font-size: 14px; font-weight: 500; margin-bottom: 4px; }
.bet-item .info .meta { font-size: 12px; color: #8a96a8; }
.bet-item .info .pick { color: #00d4ff; font-weight: 600; }
.parlay-control { background: #1a2332; padding: 16px; border-radius: 8px; margin-bottom: 16px; border: 1px solid #2a3445; }
.parlay-control label { display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 14px; }
.parlay-control input[type=checkbox] { width: 18px; height: 18px; cursor: pointer; }
.parlay-options { display: none; margin-top: 12px; gap: 8px; flex-wrap: wrap; }
.parlay-options.show { display: flex; }
.parlay-options .parlay-btn { background: #0f1419; border: 1px solid #2a3445; color: #e8eef5; padding: 6px 14px; border-radius: 4px; cursor: pointer; font-size: 13px; }
.parlay-options .parlay-btn.active { background: #00d4ff; color: #0f1419; border-color: #00d4ff; font-weight: bold; }
.summary { background: linear-gradient(135deg, #1a2332, #243447); padding: 16px; border-radius: 8px; margin-top: 16px; display: flex; justify-content: space-between; flex-wrap: wrap; gap: 12px; }
.summary .stat { flex: 1; min-width: 120px; }
.summary .stat .label { color: #8a96a8; font-size: 11px; text-transform: uppercase; margin-bottom: 4px; }
.summary .stat .value { font-size: 20px; font-weight: bold; color: #00d4ff; }
.summary .stat.win .value { color: #ffd700; }
.history-list { display: flex; flex-direction: column; gap: 10px; }
.history-item { background: #1a2332; padding: 14px; border-radius: 8px; border: 1px solid #2a3445; }
.history-item.won { border-color: #ffd700; }
.history-item.lost { border-color: #2a3445; opacity: 0.7; }
.history-item .head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.history-item .order-id { font-family: monospace; color: #00d4ff; font-size: 13px; }
.history-item .status { padding: 2px 8px; border-radius: 3px; font-size: 11px; font-weight: 600; }
.history-item .status.pending { background: #2a3445; color: #ffd700; }
.history-item .status.won { background: #ffd700; color: #0f1419; }
.history-item .status.lost { background: #2a3445; color: #8a96a8; }
.history-item .details { font-size: 12px; color: #8a96a8; margin-top: 8px; }
.history-item .picks { margin-top: 8px; }
.history-item .pick-row { display: flex; justify-content: space-between; padding: 4px 0; font-size: 12px; }
.history-item .pick-row.hit { color: #00d4ff; }
.history-item .pick-row.miss { color: #ff4757; }
.history-item .pick-row.pending { color: #8a96a8; }
.stats-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 20px; }
.stat-card { background: linear-gradient(135deg, #1a2332, #243447); padding: 16px; border-radius: 8px; border: 1px solid #2a3445; }
.stat-card .label { color: #8a96a8; font-size: 11px; text-transform: uppercase; margin-bottom: 6px; }
.stat-card .value { font-size: 24px; font-weight: bold; }
.stat-card .value.positive { color: #00d4ff; }
.stat-card .value.negative { color: #ff4757; }
.stat-card .value.neutral { color: #ffd700; }
.empty-state { text-align: center; padding: 60px 20px; color: #8a96a8; }
.empty-state .icon { font-size: 48px; margin-bottom: 12px; }
@media (max-width: 600px) {
  .groups-grid { grid-template-columns: 1fr; }
  .games-grid { grid-template-columns: 1fr; }
  header h1 { font-size: 16px; }
  .tab { padding: 12px 12px; font-size: 13px; }
  .options { grid-template-columns: repeat(2, 1fr); }
  .options.goals { grid-template-columns: repeat(4, 1fr); }
  .container { padding: 12px; }
}
</style>
</head>
<body>
<header>
  <h1>🏆 2026 世界杯模拟盘</h1>
  <div class="balance" id="headerAuthArea">
    <!-- 未登录/已登录时由 JS 动态填充 -->
  </div>
</header>

<div class="tabs">
  <div class="tab active" data-tab="groups" onclick="switchTab('groups')">小组赛</div>
  <div class="tab" data-tab="games" onclick="switchTab('games')">赛程</div>
  <div class="tab" data-tab="slip" onclick="switchTab('slip')">投注单 <span id="slipCount"></span></div>
  <div class="tab" data-tab="history" onclick="switchTab('history')">我的投注</div>
  <div class="tab" data-tab="settled" onclick="switchTab('settled')">中奖查询</div>
</div>

<div class="container">
  <!-- TAB 1: 小组赛 -->
  <div id="tab-groups" class="tab-pane"></div>
  <!-- TAB 2: 赛程 -->
  <div id="tab-games" class="tab-pane" style="display:none">
    <div class="filter-bar">
      <label>小组: <select id="filterGroup" onchange="renderGames()"><option value="all">全部</option></select></label>
      <label>状态: <select id="filterStatus" onchange="renderGames()">
        <option value="all">全部</option>
        <option value="live">🔴 进行中</option>
        <option value="upcoming">未开始</option>
        <option value="finished">已结束</option>
      </select></label>
      <label>赛事: <select id="filterType" onchange="renderGames()">
        <option value="all">全部</option>
        <option value="group">小组赛</option>
        <option value="knockout">淘汰赛</option>
      </select></label>
      <span id="liveIndicator" class="live-indicator" style="display:none"><span class="live-dot"></span><span id="liveCount">0</span> 场进行中</span>
      <button id="refreshBtn" class="refresh-btn" onclick="fetchLiveData(true)" title="刷新实时比分">🔄 实时</button>
    </div>
    <div id="gamesContainer" class="games-grid"></div>
  </div>
  <!-- TAB 3: 投注单 -->
  <div id="tab-slip" class="tab-pane" style="display:none">
    <div id="slipContainer"></div>
  </div>
  <!-- TAB 4: 我的投注 -->
  <div id="tab-history" class="tab-pane" style="display:none">
    <div id="historyContainer"></div>
  </div>
  <!-- TAB 5: 中奖查询 -->
  <div id="tab-settled" class="tab-pane" style="display:none">
    <div id="settledContainer"></div>
  </div>
</div>

<!-- 登录/注册 modal（全屏遮罩） -->
<div class="modal-overlay auth-overlay" id="authModal">
  <div class="modal auth-modal">
    <h2 id="authTitle">🔐 登录 / 注册</h2>
    <p style="color:#8a96a8;font-size:12px;margin-bottom:16px">新用户注册即送 <strong style="color:#ffd700">¥2000</strong> 体验金</p>
    <div class="auth-field">
      <label>用户名</label>
      <input type="text" id="authUsername" maxlength="16" placeholder="3-16 位字母/数字" autocomplete="username">
    </div>
    <div class="auth-field">
      <label>密码</label>
      <input type="password" id="authPassword" placeholder="至少 6 位" autocomplete="current-password">
    </div>
    <div class="auth-field" id="confirmField" style="display:none">
      <label>确认密码</label>
      <input type="password" id="authPassword2" placeholder="再输入一次" autocomplete="new-password">
    </div>
    <div id="authError" class="auth-error" style="display:none"></div>
    <div class="actions">
      <button class="btn" id="authSubmitBtn" onclick="handleAuthSubmit()">登录</button>
      <button class="btn btn-ghost" id="authSwitchBtn" onclick="switchAuthMode()">去注册</button>
    </div>
    <div style="margin-top:12px;font-size:11px;color:#8a96a8;text-align:center">
      <span id="authModeHint">没有账号？<a style="color:#00d4ff;cursor:pointer" onclick="switchAuthMode()">立即注册</a></span>
    </div>
  </div>
</div>
<div class="modal-overlay" id="betModal">
  <div class="modal">
    <button class="close-btn" onclick="closeModal()">×</button>
    <h2>🎯 投注</h2>
    <div class="game-info" id="modalGameInfo"></div>
    <div class="play-type">
      <h3>胜平负</h3>
      <div class="options" id="wdlOptions"></div>
    </div>
    <div class="play-type">
      <h3>总进球数</h3>
      <div class="options goals" id="goalsOptions"></div>
    </div>
    <div class="amount-input">
      <label>投注金额:</label>
      <input type="number" id="betAmount" min="2" step="1" value="10">
      <span style="color:#8a96a8;font-size:12px">元</span>
    </div>
    <div class="actions">
      <button class="btn btn-ghost" onclick="closeModal()">取消</button>
      <button class="btn" onclick="addToSlip()">加入投注单</button>
    </div>
  </div>
</div>

<!-- 确认弹窗 -->
<div class="modal-overlay" id="confirmModal">
  <div class="modal" style="text-align:center">
    <h2 id="confirmTitle">✅ 投注成功</h2>
    <div id="confirmContent" style="margin: 16px 0; line-height: 1.8"></div>
    <div class="actions">
      <button class="btn" onclick="closeConfirm()">好的</button>
    </div>
  </div>
</div>

<script type="application/json" id="data-games">__GAMES__</script>
<script type="application/json" id="data-groups">__GROUPS__</script>
<script type="application/json" id="data-teams">__TEAMS__</script>
<script>
// ==== 用户系统 ====
const USERS_KEY = 'wc_users';       // [{username, salt, hash, balance, createdAt}]
const SESSION_KEY = 'wc_session';   // 当前登录用户名
let currentUser = null;
let authMode = 'login';             // 'login' | 'register'

function loadUsers() {
  try { return JSON.parse(localStorage.getItem(USERS_KEY) || '[]'); }
  catch(e) { return []; }
}
function saveUsers(users) {
  localStorage.setItem(USERS_KEY, JSON.stringify(users));
}
function userDataKey(k) {
  // 每个用户的投注/余额/历史隔离
  return currentUser ? `wc_u_${currentUser}_${k}` : null;
}
// 纯 JS SHA-256（兼容非 secure context，避免依赖 window.crypto.subtle）
// 实现来自 js-sha256/StackOverflow 经典版，逐字节处理
function sha256Core(ascii) {
  function rightRotate(value, amount) {
    return (value>>>amount) | (value<<(32-amount));
  }
  var mathPow = Math.pow, maxWord = mathPow(2, 32), len = 'length';
  var i, j, result = '', words = [], asciiBitLength = ascii[len]*8;
  var hash = sha256Core.h = sha256Core.h || [];
  var k = sha256Core.k = sha256Core.k || [];
  var primeCounter = k[len];
  var isComposite = {};
  for (var candidate = 2; primeCounter < 64; candidate++) {
    if (!isComposite[candidate]) {
      for (i = 0; i < 313; i += candidate) isComposite[i] = candidate;
      hash[primeCounter] = (mathPow(candidate, .5)*maxWord)|0;
      k[primeCounter++] = (mathPow(candidate, 1/3)*maxWord)|0;
    }
  }
  ascii += '\x80';
  while (ascii[len]%64 - 56) ascii += '\x00';
  for (i = 0; i < ascii[len]; i++) {
    j = ascii.charCodeAt(i);
    if (j>>8) return '';  // 仅处理单字节字符，调用方负责 UTF-8 预编码
    words[i>>2] |= j << ((3 - i)%4)*8;
  }
  words[words[len]] = ((asciiBitLength/maxWord)|0);
  words[words[len]] = (asciiBitLength);
  for (j = 0; j < words[len];) {
    var w = words.slice(j, j += 16), oldHash = hash;
    hash = hash.slice(0, 8);
    for (i = 0; i < 64; i++) {
      var w15 = w[i - 15], w2 = w[i - 2], a = hash[0], e = hash[4];
      var temp1 = hash[7]
        + (rightRotate(e, 6) ^ rightRotate(e, 11) ^ rightRotate(e, 25))
        + ((e&hash[5])^((~e)&hash[6]))
        + k[i]
        + (w[i] = (i < 16) ? w[i] : (
            w[i - 16]
            + (rightRotate(w15, 7) ^ rightRotate(w15, 18) ^ (w15>>>3))
            + w[i - 7]
            + (rightRotate(w2, 17) ^ rightRotate(w2, 19) ^ (w2>>>10))
          )|0
        );
      var temp2 = (rightRotate(a, 2) ^ rightRotate(a, 13) ^ rightRotate(a, 22))
        + ((a&hash[1])^(a&hash[2])^(hash[1]&hash[2]));
      hash = [(temp1 + temp2)|0].concat(hash);
      hash[4] = (hash[4] + temp1)|0;
    }
    for (i = 0; i < 8; i++) hash[i] = (hash[i] + oldHash[i])|0;
  }
  for (i = 0; i < 8; i++) {
    for (j = 3; j + 1; j--) {
      var b = (hash[i]>>(j*8))&255;
      result += ((b < 16) ? 0 : '') + b.toString(16);
    }
  }
  return result;
}
function sha256(text) {
  // 优先用 SubtleCrypto（secure context 时性能更好）
  if (typeof crypto !== 'undefined' && crypto.subtle && typeof TextEncoder !== 'undefined') {
    try {
      var buf = new TextEncoder().encode(text);
      var h = sha256Core(String.fromCharCode.apply(null, buf));
      if (h) return h;
    } catch (e) {}
  }
  // 降级：手动 UTF-8 编码到二进制字符串
  var utf8 = unescape(encodeURIComponent(text));
  return sha256Core(utf8);
}
function genSalt() {
  return Array.from(crypto.getRandomValues(new Uint8Array(16))).map(b => b.toString(16).padStart(2, '0')).join('');
}
function showAuthError(msg) {
  const el = document.getElementById('authError');
  el.textContent = msg;
  el.style.display = 'block';
}
function clearAuthError() {
  document.getElementById('authError').style.display = 'none';
}
function switchAuthMode() {
  authMode = authMode === 'login' ? 'register' : 'login';
  document.getElementById('authTitle').textContent = authMode === 'login' ? '🔐 登录' : '📝 注册';
  document.getElementById('authSubmitBtn').textContent = authMode === 'login' ? '登录' : '注册并领取 ¥2000';
  document.getElementById('confirmField').style.display = authMode === 'register' ? 'block' : 'none';
  document.getElementById('authSwitchBtn').textContent = authMode === 'login' ? '去注册' : '去登录';
  document.getElementById('authModeHint').innerHTML = authMode === 'login'
    ? '没有账号？<a style="color:#00d4ff;cursor:pointer" onclick="switchAuthMode()">立即注册</a>'
    : '已有账号？<a style="color:#00d4ff;cursor:pointer" onclick="switchAuthMode()">去登录</a>';
  clearAuthError();
}
async function handleAuthSubmit() {
  clearAuthError();
  const u = document.getElementById('authUsername').value.trim();
  const p = document.getElementById('authPassword').value;
  const p2 = document.getElementById('authPassword2').value;
  if (!/^[a-zA-Z0-9_]{3,16}$/.test(u)) {
    showAuthError('用户名必须是 3-16 位字母/数字/下划线');
    return;
  }
  if (p.length < 6) {
    showAuthError('密码至少 6 位');
    return;
  }
  const users = loadUsers();
  if (authMode === 'register') {
    if (p !== p2) {
      showAuthError('两次密码不一致');
      return;
    }
    if (users.some(x => x.username === u)) {
      showAuthError('用户名已存在');
      return;
    }
    const salt = genSalt();
    const hash = await sha256(salt + p);
    users.push({
      username: u, salt, hash,
      balance: 2000,
      createdAt: new Date().toISOString()
    });
    saveUsers(users);
    doLogin(u);
    alert('🎉 注册成功！已赠送 ¥2000 体验金');
  } else {
    const user = users.find(x => x.username === u);
    if (!user) {
      showAuthError('用户名不存在');
      return;
    }
    const hash = await sha256(user.salt + p);
    if (hash !== user.hash) {
      showAuthError('密码错误');
      return;
    }
    doLogin(u);
  }
}
function doLogin(username) {
  currentUser = username;
  localStorage.setItem(SESSION_KEY, username);
  // 加载用户数据
  balance = getUserBalance();
  betSlip = JSON.parse(localStorage.getItem(userDataKey('slip')) || '[]');
  betHistory = JSON.parse(localStorage.getItem(userDataKey('bets')) || '[]');
  window._parlayOn = JSON.parse(localStorage.getItem(userDataKey('parlayOn')) || 'false');
  window._parlayN = parseInt(localStorage.getItem(userDataKey('parlayN')) || '2');
  // 关闭 modal
  document.getElementById('authModal').classList.remove('open');
  document.getElementById('authModal').style.display = 'none';
  document.getElementById('authUsername').value = '';
  document.getElementById('authPassword').value = '';
  document.getElementById('authPassword2').value = '';
  renderHeader();
  updateBalance();
  updateSlipCount();
  switchTab('groups');
}
function doLogout() {
  if (!confirm('确定登出？投注数据会保留，下次登录可恢复。')) return;
  currentUser = null;
  localStorage.removeItem(SESSION_KEY);
  betSlip = [];
  betHistory = [];
  balance = 0;
  // 重置表单 + 显示
  authMode = 'login';
  document.getElementById('authTitle').textContent = '🔐 登录';
  document.getElementById('authSubmitBtn').textContent = '登录';
  document.getElementById('confirmField').style.display = 'none';
  document.getElementById('authSwitchBtn').textContent = '去注册';
  document.getElementById('authModal').classList.add('open');
  document.getElementById('authModal').style.display = 'flex';
  renderHeader();
}
function getUserBalance() {
  if (!currentUser) return 0;
  const users = loadUsers();
  const u = users.find(x => x.username === currentUser);
  return u ? parseInt(u.balance) : 0;
}
function setUserBalance(v) {
  if (!currentUser) return;
  const users = loadUsers();
  const u = users.find(x => x.username === currentUser);
  if (u) { u.balance = v; saveUsers(users); }
}
function renderHeader() {
  const el = document.getElementById('headerAuthArea');
  if (currentUser) {
    el.innerHTML = `
      <span class="header-user">👤 <span class="name">${currentUser}</span></span>
      <span>余额: <span class="amount" id="balanceDisplay">¥${balance}</span></span>
      <button class="btn btn-sm" onclick="addBalance()">+充值</button>
      <button class="btn btn-sm btn-danger" onclick="doLogout()">登出</button>
    `;
  } else {
    el.innerHTML = `
      <span style="color:#8a96a8">未登录</span>
      <button class="btn btn-sm" onclick="showAuthModal()">登录</button>
    `;
  }
}
function showAuthModal() {
  document.getElementById('authModal').classList.add('open');
  document.getElementById('authModal').style.display = 'flex';
}
function checkSession() {
  const session = localStorage.getItem(SESSION_KEY);
  if (session) {
    const users = loadUsers();
    if (users.some(x => x.username === session)) {
      doLogin(session);  // 自动恢复登录
      return true;
    }
  }
  return false;
}

// ==== 数据加载（必须在用户系统之后，依赖 teamMap） ====
const GAMES = JSON.parse(document.getElementById('data-games').textContent);
const GROUPS = JSON.parse(document.getElementById('data-groups').textContent);
const TEAMS = JSON.parse(document.getElementById('data-teams').textContent);

// teamId -> team map
const teamMap = {};
TEAMS.forEach(t => { teamMap[t.id] = t; });

// 默认赔率（中国体彩）
const ODDS_WDL = { home: 1.80, draw: 3.20, away: 4.00 };
const ODDS_GOALS = { '0': 8.0, '1': 4.5, '2': 3.2, '3': 3.5, '4': 4.5, '5': 7.0, '6': 12.0, '7+': 25.0 };

// 运行时状态（每个用户独立，由 doLogin 重置）
let balance = 0;
let betSlip = [];
let betHistory = [];
let currentModalGame = null;
let currentModalSelection = null;

function saveState() {
  if (!currentUser) return;
  setUserBalance(balance);
  localStorage.setItem(userDataKey('slip'), JSON.stringify(betSlip));
  localStorage.setItem(userDataKey('bets'), JSON.stringify(betHistory));
  localStorage.setItem(userDataKey('parlayOn'), JSON.stringify(window._parlayOn));
  localStorage.setItem(userDataKey('parlayN'), String(window._parlayN));
}
function updateBalance() {
  const el = document.getElementById('balanceDisplay');
  if (el) el.textContent = '¥' + balance;
}
function addBalance() {
  if (!currentUser) return;
  const v = parseInt(prompt('充值金额?', '500') || '0');
  if (v > 0) { balance += v; saveState(); updateBalance(); }
}
function resetBalance() {
  if (!currentUser) return;
  if (confirm('重置余额到 1000 元？历史投注保留。')) {
    balance = 1000; saveState(); updateBalance();
  }
}

// ==== Tab 切换 ====
function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === name));
  document.querySelectorAll('.tab-pane').forEach(p => p.style.display = 'none');
  document.getElementById('tab-' + name).style.display = 'block';
  if (name === 'groups') renderGroups();
  if (name === 'games') renderGames();
  if (name === 'slip') renderSlip();
  if (name === 'history') renderHistory();
  if (name === 'settled') renderSettled();
}

// ==== 小组赛渲染 ====
function renderGroups() {
  // 注入组下拉
  const sel = document.getElementById('filterGroup');
  if (!sel.children.length || sel.children.length < 13) {
    GROUPS.forEach(g => {
      const opt = document.createElement('option');
      opt.value = g.name; opt.textContent = '组 ' + g.name;
      sel.appendChild(opt);
    });
  }
  const container = document.getElementById('tab-groups');
  let html = '<div class="groups-grid">';
  GROUPS.forEach(g => {
    // 排序: pts desc, gd desc, gf desc
    const sorted = [...g.teams].sort((a, b) => {
      if (parseInt(b.pts) !== parseInt(a.pts)) return parseInt(b.pts) - parseInt(a.pts);
      if (parseInt(b.gd) !== parseInt(a.gd)) return parseInt(b.gd) - parseInt(a.gd);
      return parseInt(b.gf) - parseInt(a.gf);
    });
    html += `<div class="group-card">
      <h3>组 ${g.name} <span class="badge">${sorted.length} 队</span></h3>
      <table>
        <thead><tr><th>#</th><th>球队</th><th class="num">赛</th><th class="num">胜</th><th class="num">平</th><th class="num">负</th><th class="num">进</th><th class="num">失</th><th class="num">净</th><th class="num">积分</th></tr></thead>
        <tbody>`;
    sorted.forEach((t, idx) => {
      const team = teamMap[t.team_id] || { name_en: 'T' + t.team_id, name_cn: 'T' + t.team_id, flag: '' };
      html += `<tr>
        <td class="num">${idx + 1}</td>
        <td><div class="team-cell">
          ${team.flag ? `<img src="${team.flag}" onerror="this.style.display='none'">` : ''}
          <span>${team.name_cn || team.name_en}</span>
        </div></td>
        <td class="num">${t.mp}</td><td class="num">${t.w}</td><td class="num">${t.d}</td>
        <td class="num">${t.l}</td><td class="num">${t.gf}</td><td class="num">${t.ga}</td>
        <td class="num">${parseInt(t.gd) > 0 ? '+' + t.gd : t.gd}</td>
        <td class="num pts-cell">${t.pts}</td>
      </tr>`;
    });
    html += '</tbody></table></div>';
  });
  html += '</div>';
  container.innerHTML = html;
}

// ==== 实时数据拉取 ====
const LIVE_API = 'https://worldcup26.ir/get/games';
let _liveTimer = null;

// local_date = 美东 EDT (UTC-4) → 北京时间 (UTC+8) = +12h
function toBeijing(s) {
  if (!s) return s;
  const m = s.match(/^(\d{2})\/(\d{2})\/(\d{4})\s+(\d{2}):(\d{2})$/);
  if (!m) return s;
  const mo = parseInt(m[1]) - 1, d = parseInt(m[2]), y = parseInt(m[3]);
  const h = parseInt(m[4]), mi = parseInt(m[5]);
  // 1) 美东 → UTC: 美东 EDT = UTC-4, 所以 +4h 得 UTC
  //    Date.UTC 自动规范化越界小时/日期
  const utc = new Date(Date.UTC(y, mo, d, h + 4, mi));
  // 2) UTC → 北京: +8h
  utc.setUTCHours(utc.getUTCHours() + 8);
  const yy = utc.getUTCFullYear();
  const mm = String(utc.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(utc.getUTCDate()).padStart(2, '0');
  const hh = String(utc.getUTCHours()).padStart(2, '0');
  const mii = String(utc.getUTCMinutes()).padStart(2, '0');
  return `${yy}-${mm}-${dd} ${hh}:${mii}`;
}
const _BJ = '(北京时间)';

async function fetchLiveData(manual) {
  const btn = document.getElementById('refreshBtn');
  if (btn) { btn.classList.add('loading'); btn.textContent = '⏳ 拉取中…'; }
  try {
    const resp = await fetch(LIVE_API, { cache: 'no-store' });
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const data = await resp.json();
    const apiGames = data.games || [];
    // 按 id merge 进 GAMES（保留原 id 字段类型）
    let updated = 0;
    apiGames.forEach(ag => {
      const agId = String(ag.id);
      const local = GAMES.find(g => String(g.id) === agId);
      if (local) {
        if (local.home_score !== ag.home_score) { local.home_score = ag.home_score; updated++; }
        if (local.away_score !== ag.away_score) { local.away_score = ag.away_score; updated++; }
        local.finished = ag.finished;
        local.time_elapsed = ag.time_elapsed;
      }
    });
    // 更新 liveIndicator
    const liveCount = GAMES.filter(g => gameStatus(g) === 1).length;
    const ind = document.getElementById('liveIndicator');
    if (ind) {
      if (liveCount > 0) {
        ind.style.display = 'inline-flex';
        document.getElementById('liveCount').textContent = liveCount;
      } else {
        ind.style.display = 'none';
      }
    }
    // 重渲染当前可见 Tab 的赛程
    if (document.getElementById('tab-games').style.display !== 'none') renderGames();
    if (manual) {
      const ts = new Date().toLocaleTimeString('zh-CN', { hour12: false });
      btn.textContent = `✓ 已更新 ${ts}`;
      setTimeout(() => btn.textContent = '🔄 实时', 2500);
    } else {
      btn.textContent = '🔄 实时';
    }
  } catch (e) {
    console.warn('fetchLiveData failed:', e);
    if (btn) btn.textContent = '✗ 刷新失败';
    setTimeout(() => btn.textContent = '🔄 实时', 2500);
  } finally {
    if (btn) btn.classList.remove('loading');
  }
}

function startLivePolling() {
  if (_liveTimer) return;
  // 启动时拉一次
  fetchLiveData(false);
  // 每 30s 拉一次
  _liveTimer = setInterval(() => fetchLiveData(false), 30000);
}

// ==== 赛程渲染 ====
// 状态判定: 0=未开始 1=进行中 2=已结束
function gameStatus(g) {
  if (g.finished === 'TRUE' || g.finished === 'true' || g.time_elapsed === 'Finished' || g.time_elapsed === 'finished') return 2;
  if (g.time_elapsed === 'live') return 1;
  return 0;
}
function statusLabel(st) {
  return st === 2 ? '已结束' : st === 1 ? '进行中' : '未开始';
}

function renderGames() {
  // 注入组下拉
  const sel = document.getElementById('filterGroup');
  if (!sel.children.length || sel.children.length < 13) {
    GROUPS.forEach(g => {
      const opt = document.createElement('option');
      opt.value = g.name; opt.textContent = '组 ' + g.name;
      sel.appendChild(opt);
    });
  }
  const fg = document.getElementById('filterGroup').value;
  const fs = document.getElementById('filterStatus').value;
  const ft = document.getElementById('filterType').value;
  let list = GAMES.filter(g => {
    if (fg !== 'all' && g.group !== fg) return false;
    const st = gameStatus(g);
    if (fs === 'finished' && st !== 2) return false;
    if (fs === 'upcoming' && st !== 0) return false;
    if (fs === 'live' && st !== 1) return false;
    if (ft !== 'all' && g.type !== ft) return false;
    return true;
  });
  // 排序: 进行中 → 未开始 (按日期) → 已结束 (按 matchday desc 最新结束在前)
  list.sort((a, b) => {
    const sa = gameStatus(a), sb = gameStatus(b);
    if (sa !== sb) return sa === 1 ? -1 : sb === 1 ? 1 : (sa === 0 ? -1 : 1);
    if (sa === 2) return parseInt(b.matchday) - parseInt(a.matchday);
    return parseInt(a.matchday) - parseInt(b.matchday);
  });
  const container = document.getElementById('gamesContainer');
  if (!list.length) {
    container.innerHTML = '<div class="empty-state"><div class="icon">⚽</div>没有符合条件的比赛</div>';
    return;
  }
  container.innerHTML = list.map(g => {
    const st = gameStatus(g);
    const isFinished = st === 2, isLive = st === 1;
    const home = teamMap[g.home_team_id] || { name_en: g.home_team_name_en, name_cn: g.home_team_name_cn || g.home_team_name_en, flag: '' };
    const away = teamMap[g.away_team_id] || { name_en: g.away_team_name_en, name_cn: g.away_team_name_cn || g.away_team_name_en, flag: '' };
    let scorersHtml = '';
    if (isFinished) {
      const hs = parseScorers(g.home_scorers);
      const as = parseScorers(g.away_scorers);
      if (hs.length) scorersHtml += `<div>⚽ ${home.name_cn || home.name_en}: ${hs.join(', ')}</div>`;
      if (as.length) scorersHtml += `<div>⚽ ${away.name_cn || away.name_en}: ${as.join(', ')}</div>`;
    }
    // 状态徽标
    let statusBadge = '';
    if (isLive) {
      const liveMin = g.live_minute || (typeof g.time_elapsed === 'string' && g.time_elapsed.endsWith("'") ? g.time_elapsed : "进行中");
      statusBadge = `<span class="status-live"><span class="live-dot"></span>LIVE ${liveMin}</span>`;
    } else if (isFinished) {
      statusBadge = `<span class="status-finished">已结束</span>`;
    } else {
      statusBadge = `<span class="status-upcoming">${toBeijing(g.local_date)}</span>`;
    }
    // 比分或 VS
    const scoreHtml = (isFinished || isLive)
      ? `<div class="score ${isLive ? 'live' : ''}">${g.home_score} - ${g.away_score}</div>`
      : '<div class="vs">VS</div>';
    return `<div class="game-card ${isFinished ? 'finished' : ''} ${isLive ? 'live' : ''}">
      <div class="meta">
        <span><span class="type-tag">组 ${g.group}</span> · MD${g.matchday} · ${g.type === 'knockout' ? '淘汰赛' : '小组赛'}</span>
        ${statusBadge}
      </div>
      <div class="matchup">
        <div class="team home">
          ${home.flag ? `<img src="${home.flag}" onerror="this.style.display='none'">` : ''}
          <span class="team-name">${home.name_cn || home.name_en}</span>
        </div>
        ${scoreHtml}
        <div class="team away">
          ${away.flag ? `<img src="${away.flag}" onerror="this.style.display='none'">` : ''}
          <span class="team-name">${away.name_cn || away.name_en}</span>
        </div>
      </div>
      ${scorersHtml ? `<div class="scorers">${scorersHtml}</div>` : ''}
      <div class="footer">
        <span style="font-size:11px;color:#8a96a8">${toBeijing(g.local_date)} · ${_BJ}</span>
        ${!isFinished && !isLive ? `<button class="bet-btn" onclick="openBetModal('${g.id}')">投注</button>` : ''}
      </div>
    </div>`;
  }).join('');
}

function parseScorers(s) {
  if (!s || s === 'null' || s === '[]' || s === '{}') return [];
  try {
    // 可能是 '["a","b"]' 或 '{"a"}' 格式
    let arr;
    if (s.startsWith('[')) arr = JSON.parse(s);
    else if (s.startsWith('{')) {
      // 单元素 set 形式 '{"x"}'
      const inner = s.slice(1, -1);
      if (!inner) return [];
      arr = inner.split(/","/).map(x => x.replace(/^"|"$/g, ''));
    } else return [];
    return arr.map(x => x.replace(/\\'/g, "'"));
  } catch(e) { return []; }
}

// ==== 投注弹窗 ====
function openBetModal(gameId) {
  const g = GAMES.find(x => x.id === gameId);
  if (!g) return;
  const st = gameStatus(g);
  if (st === 2) { alert('该比赛已结束，无法投注'); return; }
  if (st === 1) { alert('该比赛正在进行中，无法投注'); return; }
  currentModalGame = g;
  currentModalSelection = null;
  const home = teamMap[g.home_team_id] || { name_en: g.home_team_name_en, name_cn: g.home_team_name_cn };
  const away = teamMap[g.away_team_id] || { name_en: g.away_team_name_en, name_cn: g.away_team_name_cn };
  document.getElementById('modalGameInfo').innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center">
      <strong>${home.name_cn || home.name_en}</strong>
      <span style="color:#8a96a8">VS</span>
      <strong>${away.name_cn || away.name_en}</strong>
    </div>
    <div style="color:#8a96a8;margin-top:6px">组 ${g.group} · MD${g.matchday} · ${toBeijing(g.local_date)} · ${_BJ}</div>
  `;
  // 胜平负
  const wdl = document.getElementById('wdlOptions');
  const homeShort = (home.name_cn || home.name_en).substring(0, 4);
  const awayShort = (away.name_cn || away.name_en).substring(0, 4);
  wdl.innerHTML = [
    { v: 'home', l: '主胜 ' + homeShort },
    { v: 'draw', l: '平局' },
    { v: 'away', l: '客胜 ' + awayShort }
  ].map(o => `<div class="option" data-type="wdl" data-value="${o.v}" onclick="selectOption(this)">
    <div class="label">${o.l}</div><div class="odds">@ ${ODDS_WDL[o.v].toFixed(2)}</div>
  </div>`).join('');
  // 总进球
  const goals = document.getElementById('goalsOptions');
  goals.innerHTML = Object.entries(ODDS_GOALS).map(([k, v]) => `<div class="option" data-type="goals" data-value="${k}" onclick="selectOption(this)">
    <div class="label">${k}球</div><div class="odds">@ ${v.toFixed(2)}</div>
  </div>`).join('');
  document.getElementById('betModal').classList.add('open');
}

function selectOption(el) {
  el.parentNode.querySelectorAll('.option').forEach(x => x.classList.remove('selected'));
  el.classList.add('selected');
  currentModalSelection = { type: el.dataset.type, value: el.dataset.value };
}

function closeModal() {
  document.getElementById('betModal').classList.remove('open');
  currentModalGame = null;
  currentModalSelection = null;
}

function addToSlip() {
  if (!currentModalGame || !currentModalSelection) {
    alert('请先选择一个投注选项');
    return;
  }
  const amt = parseInt(document.getElementById('betAmount').value);
  if (!amt || amt < 2) {
    alert('投注金额最低 2 元');
    return;
  }
  if (balance < amt) {
    alert('余额不足，当前余额 ¥' + balance);
    return;
  }
  const odds = currentModalSelection.type === 'wdl' ? ODDS_WDL[currentModalSelection.value] : ODDS_GOALS[currentModalSelection.value];
  const g = currentModalGame;
  const home = teamMap[g.home_team_id] || { name_en: g.home_team_name_en, name_cn: g.home_team_name_cn };
  const away = teamMap[g.away_team_id] || { name_en: g.away_team_name_en, name_cn: g.away_team_name_cn };
  betSlip.push({
    gameId: g.id,
    gameLabel: `${home.name_cn || home.name_en} vs ${away.name_cn || away.name_en}`,
    gameDate: toBeijing(g.local_date),
    type: currentModalSelection.type,
    pick: currentModalSelection.value,
    pickLabel: getPickLabel(currentModalSelection),
    odds: odds,
    amount: amt
  });
  saveState();
  closeModal();
  updateSlipCount();
  alert('已加入投注单 ✓');
}

function getPickLabel(sel) {
  if (sel.type === 'wdl') return sel.value === 'home' ? '主胜' : sel.value === 'away' ? '客胜' : '平局';
  return sel.value + ' 球';
}

function updateSlipCount() {
  document.getElementById('slipCount').textContent = betSlip.length ? `(${betSlip.length})` : '';
}

// ==== 投注单 ====
function renderSlip() {
  updateSlipCount();
  const c = document.getElementById('slipContainer');
  if (!betSlip.length) {
    c.innerHTML = '<div class="betslip"><div class="betslip-empty">📋 投注单为空<br><span style="font-size:12px">在"赛程"Tab 选择未开始的比赛投注</span></div></div>';
    return;
  }
  const totalAmount = betSlip.reduce((s, b) => s + b.amount, 0);
  const parlay = betSlip.length >= 2;
  let html = '<div class="betslip">';
  html += `<h3 style="margin-bottom:12px">投注单 (${betSlip.length} 场)</h3>`;
  betSlip.forEach((b, i) => {
    html += `<div class="bet-item">
      <div class="info">
        <div class="teams">${b.gameLabel}</div>
        <div class="meta">${b.gameDate} · <span class="pick">${b.pickLabel}</span> · @${b.odds.toFixed(2)} · ¥${b.amount}</div>
      </div>
      <button class="btn btn-danger btn-sm" onclick="removeFromSlip(${i})">删除</button>
    </div>`;
  });
  html += '</div>';
  if (parlay) {
    html += `<div class="parlay-control">
      <label><input type="checkbox" id="parlayToggle" onchange="toggleParlay()"> <strong>串联买 (串关)</strong> — 全中才算赢</label>
      <div class="parlay-options" id="parlayOptions">
        ${[2, 3, 4, 5, 6].filter(n => n <= betSlip.length).map(n => `<button class="parlay-btn" data-n="${n}" onclick="setParlayN(${n})">${n} 串 1</button>`).join('')}
      </div>
    </div>`;
  }
  const isParlayOn = document.getElementById('parlayToggle')?.checked;
  const n = isParlayOn ? (window._parlayN || 2) : 1;
  let maxWin;
  if (isParlayOn && betSlip.length >= n) {
    // 取最低 n 场（按赔率）or 前 n 场？最简方案：全部乘
    maxWin = betSlip.reduce((s, b) => s * b.odds, 0) * 10; // 演示用
    // 实际 maxWin = 各项赔率乘积 × 投入 (单关金额按均摊) — 简化：只算连乘
  } else {
    maxWin = betSlip.reduce((s, b) => s + b.odds * b.amount, 0);
  }
  html += `<div class="summary">
    <div class="stat"><div class="label">投注数</div><div class="value">${betSlip.length}</div></div>
    <div class="stat"><div class="label">投入合计</div><div class="value">¥${totalAmount}</div></div>
    <div class="stat win"><div class="label">理论最高奖金</div><div class="value">¥${isParlayOn ? (Math.pow(betSlip.slice(0, n).reduce((s, b) => s * b.odds, 1), 1) * totalAmount).toFixed(2) : maxWin.toFixed(2)}</div></div>
  </div>`;
  html += `<div style="margin-top:16px;text-align:right">
    <button class="btn" onclick="confirmBet()" style="padding:12px 32px;font-size:15px">确认投注</button>
  </div>`;
  c.innerHTML = html;
}

function removeFromSlip(idx) {
  betSlip.splice(idx, 1);
  saveState();
  renderSlip();
}

function toggleParlay() {
  const checked = document.getElementById('parlayToggle').checked;
  document.getElementById('parlayOptions').classList.toggle('show', checked);
  if (checked && !window._parlayN) {
    const buttons = document.querySelectorAll('#parlayOptions .parlay-btn');
    if (buttons.length) { buttons[0].classList.add('active'); window._parlayN = parseInt(buttons[0].dataset.n); }
  }
  renderSlip();
}

function setParlayN(n) {
  window._parlayN = n;
  document.querySelectorAll('#parlayOptions .parlay-btn').forEach(b => b.classList.toggle('active', parseInt(b.dataset.n) === n));
  renderSlip();
}

function confirmBet() {
  if (!betSlip.length) return;
  const total = betSlip.reduce((s, b) => s + b.amount, 0);
  if (balance < total) {
    alert('余额不足');
    return;
  }
  const isParlay = document.getElementById('parlayToggle')?.checked;
  const n = isParlay ? (window._parlayN || betSlip.length) : 1;
  const orderId = 'WC' + Date.now().toString().slice(-8) + Math.floor(Math.random() * 100);
  balance -= total;
  const bet = {
    orderId,
    time: new Date().toISOString(),
    type: isParlay ? `${n}串1` : '单关',
    items: betSlip.map(b => ({ ...b })),
    totalAmount: total,
    status: 'pending',
    payout: 0
  };
  betHistory.unshift(bet);
  betSlip = [];
  saveState();
  updateBalance();
  document.getElementById('confirmTitle').textContent = '✅ 投注成功';
  document.getElementById('confirmContent').innerHTML = `
    <div style="font-size:18px;color:#00d4ff;margin-bottom:12px">订单号: ${orderId}</div>
    <div>类型: <strong>${bet.type}</strong></div>
    <div>场次: ${bet.items.length} 场</div>
    <div>投入: <strong style="color:#ffd700">¥${total}</strong></div>
    <div style="margin-top:8px;color:#8a96a8;font-size:12px">等待比赛结束后自动结算</div>
  `;
  document.getElementById('confirmModal').classList.add('open');
}

function closeConfirm() {
  document.getElementById('confirmModal').classList.remove('open');
  switchTab('history');
}

// ==== 我的投注 ====
function renderHistory() {
  const c = document.getElementById('historyContainer');
  // 自动结算
  settleBets();
  if (!betHistory.length) {
    c.innerHTML = '<div class="empty-state"><div class="icon">📜</div>暂无投注记录</div>';
    return;
  }
  c.innerHTML = '<div class="history-list">' + betHistory.map(b => {
    const won = b.status === 'won';
    const lost = b.status === 'lost';
    return `<div class="history-item ${won ? 'won' : lost ? 'lost' : ''}">
      <div class="head">
        <div>
          <span class="order-id">${b.orderId}</span>
          <span style="color:#8a96a8;font-size:12px;margin-left:8px">${new Date(b.time).toLocaleString('zh-CN')}</span>
        </div>
        <span class="status ${won ? 'won' : lost ? 'lost' : 'pending'}">${won ? '中奖' : lost ? '未中' : '待开奖'}</span>
      </div>
      <div style="font-size:13px">
        <strong>${b.type}</strong> · ${b.items.length} 场 · 投入 ¥${b.totalAmount}
        ${b.status !== 'pending' ? `· <span style="color:${won ? '#ffd700' : '#8a96a8'}">${won ? '赢得 +¥' + b.payout.toFixed(2) : '亏损'}</span>` : ''}
      </div>
      <div class="picks">
        ${b.items.map(it => {
          const result = getPickResult(it);
          return `<div class="pick-row ${result.cls}">
            <span>${it.gameLabel} · <strong>${it.pickLabel}</strong> @${it.odds.toFixed(2)} ¥${it.amount}</span>
            <span>${result.icon} ${result.text}</span>
          </div>`;
        }).join('')}
      </div>
    </div>`;
  }).join('') + '</div>';
}

function getPickResult(item) {
  const g = GAMES.find(x => x.id === item.gameId);
  if (!g || g.finished !== 'TRUE') return { cls: 'pending', icon: '⏳', text: '待开奖' };
  const hs = parseInt(g.home_score), as_ = parseInt(g.away_score);
  if (item.type === 'wdl') {
    let actual = hs === as_ ? 'draw' : hs > as_ ? 'home' : 'away';
    if (actual === item.pick) return { cls: 'hit', icon: '✓', text: '中' };
    return { cls: 'miss', icon: '✗', text: `实际: ${hs}-${as_}` };
  } else { // goals
    const total = hs + as_;
    const totalStr = total >= 7 ? '7+' : String(total);
    if (totalStr === item.pick) return { cls: 'hit', icon: '✓', text: `中 (${total}球)` };
    return { cls: 'miss', icon: '✗', text: `实际: ${total}球` };
  }
}

// ==== 结算 ====
function settleBets() {
  let changed = false;
  betHistory.forEach(b => {
    if (b.status !== 'pending') return;
    // 检查每场是否都已结束
    const allDone = b.items.every(it => {
      const g = GAMES.find(x => x.id === it.gameId);
      return g && g.finished === 'TRUE';
    });
    if (!allDone) return;
    // 检查每场是否命中
    const allHit = b.items.every(it => {
      const r = getPickResult(it);
      return r.cls === 'hit';
    });
    if (b.type === '单关' || b.type.startsWith('串')) {
      // 串关：全部命中才赢
      if (allHit) {
        b.status = 'won';
        b.payout = b.items.reduce((s, it) => s * it.odds, 1) * (b.totalAmount / b.items.length);
        balance += b.payout;
      } else {
        b.status = 'lost';
        b.payout = 0;
      }
      changed = true;
    }
  });
  if (changed) saveState();
}

// ==== 中奖查询 ====
function renderSettled() {
  settleBets();
  const settled = betHistory.filter(b => b.status === 'won' || b.status === 'lost');
  const c = document.getElementById('settledContainer');
  if (!settled.length) {
    c.innerHTML = '<div class="empty-state"><div class="icon">🏆</div>暂无已结算订单</div>';
    return;
  }
  const totalIn = settled.reduce((s, b) => s + b.totalAmount, 0);
  const totalWin = settled.filter(b => b.status === 'won').reduce((s, b) => s + b.payout, 0);
  const profit = totalWin - totalIn;
  let html = `<div class="stats-cards">
    <div class="stat-card"><div class="label">已结算订单</div><div class="value neutral">${settled.length}</div></div>
    <div class="stat-card"><div class="label">总投入</div><div class="value neutral">¥${totalIn.toFixed(2)}</div></div>
    <div class="stat-card"><div class="label">总回报</div><div class="value positive">¥${totalWin.toFixed(2)}</div></div>
    <div class="stat-card"><div class="label">盈亏</div><div class="value ${profit >= 0 ? 'positive' : 'negative'}">${profit >= 0 ? '+' : ''}¥${profit.toFixed(2)}</div></div>
  </div>`;
  html += '<div class="history-list">' + settled.map(b => {
    const won = b.status === 'won';
    return `<div class="history-item ${won ? 'won' : 'lost'}">
      <div class="head">
        <div>
          <span class="order-id">${b.orderId}</span>
          <span style="color:#8a96a8;font-size:12px;margin-left:8px">${new Date(b.time).toLocaleString('zh-CN')}</span>
        </div>
        <span class="status ${won ? 'won' : 'lost'}">${won ? '中奖 +¥' + b.payout.toFixed(2) : '未中'}</span>
      </div>
      <div style="font-size:13px"><strong>${b.type}</strong> · ${b.items.length} 场 · 投入 ¥${b.totalAmount}</div>
      <div class="picks">
        ${b.items.map(it => {
          const r = getPickResult(it);
          return `<div class="pick-row ${r.cls}">
            <span>${it.gameLabel} · ${it.pickLabel} @${it.odds.toFixed(2)}</span>
            <span>${r.icon} ${r.text}</span>
          </div>`;
        }).join('')}
      </div>
    </div>`;
  }).join('') + '</div>';
  c.innerHTML = html;
}

// ==== 初始化 ====
updateBalance();
renderGroups();
updateSlipCount();
startLivePolling();
if (!checkSession()) showAuthModal();
</script>
</body>
</html>'''

html = html.replace('__GAMES__', games_json).replace('__GROUPS__', groups_json).replace('__TEAMS__', teams_json)
out = proj / 'index.html'
out.write_text(html, encoding='utf-8')
print(f"[OK] {out}  size={out.stat().st_size} bytes")
