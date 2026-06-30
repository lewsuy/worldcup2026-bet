"""生成 index.html — 2026 世界杯模拟盘单文件应用。"""
import json
import math
import os
import time
import urllib.request
from pathlib import Path

# 项目根目录：用脚本自身所在目录（兼容 Windows / Linux，避免硬编码绝对路径）
proj = Path(__file__).resolve().parent

# ==== 赔率模型：Dixon-Coles 双泊松 + ELO + 庄家 margin ====
# 数据源: eloratings.net（公开 World Football Elo Ratings）
# 缓存路径: ~/.hermes/cache/world_elo.tsv（7 天自动刷新）
ELO_CACHE = Path(os.path.expanduser('~/.hermes/cache/world_elo.tsv'))
ELO_TTL = 7 * 86400  # 7 天

FIFA_TO_IOC = {
    'MEX':'ME','RSA':'ZA','KOR':'KO','CZE':'CZ','CAN':'CA','BIH':'BA',
    'QAT':'QA','SUI':'CH','BRA':'BR','MAR':'MA','HAI':'HT','SCO':'SC',
    'USA':'US','PAR':'PY','AUS':'AU','TUR':'TR','GER':'DE','CUW':'CW',
    'CIV':'CI','ECU':'EC','NED':'NL','JPN':'JP','SWE':'SE','TUN':'TN',
    'BEL':'BE','EGY':'EG','IRN':'IR','NZL':'NZ','ESP':'ES','CPV':'CV',
    'KSA':'SA','URU':'UY','FRA':'FR','SEN':'SN','IRQ':'IQ','NOR':'NO',
    'ARG':'AR','ALG':'DZ','AUT':'AT','JOR':'JO','POR':'PT','COD':'CD',
    'UZB':'UZ','COL':'CO','ENG':'EN','CRO':'HR','GHA':'GH','PAN':'PA',
}

HOME_BOOST = 100   # 主场加成（ELO 分）
LEAGUE_AVG = 1.35  # 每队平均预期进球（参考世界杯历史场均 2.7 球）
AWAY_DISCOUNT = 0.93  # 客场进球折扣
MARGIN = 0.08      # 庄家利润（overround = 1 + margin）
ELO_FLOOR = 1400   # ELO 下限（进入世界杯的最低门槛，避免 EloRatings 给 Scotland=853 这种极端低分）


def fetch_elo_data():
    """抓取并缓存 EloRatings.net World.tsv"""
    ELO_CACHE.parent.mkdir(parents=True, exist_ok=True)
    if ELO_CACHE.exists() and (time.time() - ELO_CACHE.stat().st_mtime) < ELO_TTL:
        return ELO_CACHE.read_text()
    req = urllib.request.Request('https://www.eloratings.net/World.tsv',
                                 headers={'User-Agent': 'Mozilla/5.0'})
    data = urllib.request.urlopen(req, timeout=15).read().decode('utf-8')
    ELO_CACHE.write_text(data)
    return data


def parse_elo(raw):
    """解析 TSV → {ioc_code: elo_int}"""
    result = {}
    for line in raw.strip().split('\n'):
        p = line.split('\t')
        if len(p) > 3:
            try: result[p[2]] = int(p[3])
            except: pass
    return result


def build_elo_map(teams):
    """FIFA_code → ELO (应用 floor 1400)"""
    elo_by_ioc = parse_elo(fetch_elo_data())
    out = {}
    for t in teams:
        ioc = FIFA_TO_IOC.get(t['fifa_code'])
        raw = elo_by_ioc.get(ioc, 1500) if ioc else 1500
        out[t['fifa_code']] = max(ELO_FLOOR, raw)
    return out


def expected_goals(home_elo, away_elo):
    """ELO 差 → 双方预期进球数"""
    diff = (home_elo + HOME_BOOST) - away_elo
    lh = LEAGUE_AVG * (10 ** (diff / 600))
    la = LEAGUE_AVG * (10 ** (-diff / 600)) * AWAY_DISCOUNT
    return lh, la


def _poisson(lam, k):
    if lam <= 0: return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def match_probs(lh, la, max_goals=8):
    """双独立泊松 → (P_home, P_draw, P_away, total_goals_dist, P_over25, P_under25)"""
    pm = [[_poisson(lh, i) * _poisson(la, j) for j in range(max_goals+1)] for i in range(max_goals+1)]
    p_w = sum(pm[i][j] for i in range(max_goals+1) for j in range(i))
    p_d = sum(pm[i][i] for i in range(max_goals+1))
    p_l = 1 - p_w - p_d
    pt = {}
    for total in range(0, 2*max_goals+1):
        s = 0
        for i in range(max_goals+1):
            j = total - i
            if 0 <= j <= max_goals: s += pm[i][j]
        pt[total] = s
    p7 = sum(p for k, p in pt.items() if isinstance(k, int) and k >= 7)
    pt = {k: p for k, p in pt.items() if not (isinstance(k, int) and k >= 7)}
    pt['7+'] = p7
    p_over = sum(p for k, p in pt.items() if k == '7+' or (isinstance(k, int) and k >= 3))
    p_under = 1 - p_over
    return p_w, p_d, p_l, pt, p_over, p_under


def fair_to_market(p, margin=MARGIN, lo=1.10, hi=80.0):
    """fair odds (1/p) 加庄家 margin → 市场赔率
    博彩公司让 sum(1/market_odds_i) = 1 + margin（典型 1.07-1.08）"""
    if p <= 0: return hi
    market = (1.0 / p) / (1 + margin)
    return max(lo, min(hi, round(market, 2)))


def compute_game_odds(game, elo_map, id2code):
    """为单场比赛计算赔率，写入 game 字典"""
    h_elo = elo_map.get(id2code.get(str(game['home_team_id']), ''), 1500)
    a_elo = elo_map.get(id2code.get(str(game['away_team_id']), ''), 1500)
    lh, la = expected_goals(h_elo, a_elo)
    p_w, p_d, p_l, p_t, p_over, p_under = match_probs(lh, la)
    game['odds_wdl'] = {
        'home': fair_to_market(p_w),
        'draw': fair_to_market(p_d),
        'away': fair_to_market(p_l),
    }
    game['odds_ou25'] = {
        'over':  fair_to_market(p_over),
        'under': fair_to_market(p_under),
    }
    game['odds_goals'] = {k: fair_to_market(v) for k, v in p_t.items()}
    return game


# ==== 数据加载 ====
with open(proj / 'wc_games_slim.json', encoding='utf-8') as f:
    games = json.load(f)['games']
with open(proj / 'wc_groups.json', encoding='utf-8') as f:
    groups = json.load(f)['groups']
with open(proj / 'wc_teams.json', encoding='utf-8') as f:
    teams = json.load(f)['teams']
# 淘汰赛对阵表（来自 wc-2026.org，共 32 场：R32×16 + R16×8 + QF×4 + SF×2 + 3rd + F）
knockout_path = proj / 'wc_knockouts.json'
if knockout_path.exists():
    with open(knockout_path, encoding='utf-8') as f:
        knockout_matches = json.load(f)
else:
    knockout_matches = []

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

# 计算所有比赛赔率（Dixon-Coles 双泊松 + ELO + 庄家 margin）
_elo_map = build_elo_map(teams)
_id2code = {t['id']: t['fifa_code'] for t in teams}
for g in games:
    compute_game_odds(g, _elo_map, _id2code)

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
knockouts_json = json.dumps(knockout_matches, ensure_ascii=False)

html = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>🏆 2026 世界杯模拟盘</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Ctext y='52' font-size='52'%3E%F0%9F%8F%86%3C/text%3E%3C/svg%3E">
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
/* 小组赛前 2 名直接出线 */
tr.top2 td { color: #2ecc71; font-weight: 600; }
tr.top2 .pts-cell { color: #2ecc71; }
/* 8 个最佳第 3 名（晋级 32 强淘汰赛） */
tr.top3best td { color: #2ecc71; font-weight: 600; }
tr.top3best .pts-cell { color: #2ecc71; }
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
  <div class="tab" data-tab="knockout" onclick="switchTab('knockout')">淘汰赛</div>
  <div class="tab" data-tab="games" onclick="switchTab('games')">赛程</div>
  <div class="tab" data-tab="slip" onclick="switchTab('slip')">投注单 <span id="slipCount"></span></div>
  <div class="tab" data-tab="history" onclick="switchTab('history')">我的投注</div>
  <div class="tab" data-tab="settled" onclick="switchTab('settled')">中奖查询</div>
</div>

<div class="container">
  <!-- TAB 1: 小组赛 -->
  <div id="tab-groups" class="tab-pane"></div>
  <!-- TAB 2: 淘汰赛（思维导图样式） -->
  <div id="tab-knockout" class="tab-pane" style="display:none">
    <div class="knockout-legend" style="margin-bottom:14px;display:flex;gap:18px;flex-wrap:wrap;font-size:12px;color:#8a96a8;">
      <span><span style="display:inline-block;width:14px;height:14px;background:rgba(59,130,246,0.10);border:1px solid rgba(59,130,246,0.55);border-radius:3px;vertical-align:middle"></span> 1/16 蓝</span>
      <span><span style="display:inline-block;width:14px;height:14px;background:rgba(139,92,246,0.10);border:1px solid rgba(139,92,246,0.55);border-radius:3px;vertical-align:middle"></span> 1/8 紫</span>
      <span><span style="display:inline-block;width:14px;height:14px;background:rgba(236,72,153,0.10);border:1px solid rgba(236,72,153,0.55);border-radius:3px;vertical-align:middle"></span> 1/4 粉</span>
      <span><span style="display:inline-block;width:14px;height:14px;background:rgba(245,158,11,0.10);border:1px solid rgba(245,158,11,0.55);border-radius:3px;vertical-align:middle"></span> 半决赛 橙</span>
      <span><span style="display:inline-block;width:14px;height:14px;background:rgba(251,191,36,0.10);border:1px solid rgba(251,191,36,0.55);border-radius:3px;vertical-align:middle"></span> 决赛 金</span>
      <span><span style="display:inline-block;width:14px;height:14px;background:rgba(148,163,184,0.10);border:1px solid rgba(148,163,184,0.55);border-radius:3px;vertical-align:middle"></span> 季军赛 灰</span>
      <span><span style="display:inline-block;width:14px;height:14px;background:#1a2332;border:1px dashed #8a96a8;border-radius:3px;vertical-align:middle"></span> 占位符</span>
      <span><span style="display:inline-block;width:14px;height:14px;background:rgba(255,71,87,0.12);border:2px solid #ff4757;border-radius:3px;vertical-align:middle"></span> 已结束</span>
    </div>
    <div id="knockoutContainer" class="ko-container" style="overflow-x:hidden;overflow-y:auto;padding:18px 22px;max-height:calc(100vh - 200px);"><span id="koUpdated" style="display:none">__KO_UPDATED__</span></div>
  </div>
  <!-- TAB 3: 赛程 -->
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
<script type="application/json" id="data-knockouts">__KNOCKOUTS__</script>
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
const KNOCKOUTS = JSON.parse(document.getElementById('data-knockouts').textContent);

// teamId -> team map
const teamMap = {};
TEAMS.forEach(t => { teamMap[t.id] = t; });

// 默认赔率（中国体彩）
// 默认赔率（中国体彩风格基础值）。单场比赛动态赔率由 build.py 通过 Dixon-Coles 模型计算后
// 注入到每场 game.odds_wdl / odds_ou25 / odds_goals，本地仅作 fallback。
const ODDS_WDL_DEFAULT = { home: 1.80, draw: 3.20, away: 4.00 };
const ODDS_GOALS_DEFAULT = { '0': 8.0, '1': 4.5, '2': 3.2, '3': 3.5, '4': 4.5, '5': 7.0, '6': 12.0, '7+': 25.0 };
function oddsWdl(g) { return g && g.odds_wdl ? g.odds_wdl : ODDS_WDL_DEFAULT; }
function oddsGoals(g) { return g && g.odds_goals ? g.odds_goals : ODDS_GOALS_DEFAULT; }

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
  if (name === 'groups') { recalcGroupsFromGames(); renderGroups(); }
  if (name === 'games') renderGames();
  if (name === 'knockout') renderKnockout();
  if (name === 'slip') renderSlip();
  if (name === 'history') renderHistory();
  if (name === 'settled') renderSettled();
}

// ==== 根据已结束的小组赛重算 GROUPS 积分 ====
// 修复：build 时注入的 GROUPS.teams 硬编码积分是 build 时刻的快照。
// fetchLiveData() 只更新了 GAMES 的比分，没更新 GROUPS，所以切到 groups tab 还是旧数据。
// 此函数：清零 GROUPS 每个 team 的统计字段，按 GAMES 中 type='group' 且 finished 的比分重新累加。
function recalcGroupsFromGames() {
  // 1) 清零所有 team 的统计字段
  GROUPS.forEach(g => {
    g.teams.forEach(t => {
      t.mp = 0; t.w = 0; t.d = 0; t.l = 0;
      t.gf = 0; t.ga = 0; t.gd = 0; t.pts = 0;
    });
  });
  // 2) 遍历已结束的 group 比赛，累加双方统计
  GAMES.forEach(g => {
    if (g.type !== 'group') return;
    const fin = g.finished === 'TRUE' || g.finished === 'true' || g.finished === true;
    if (!fin) return;
    const hs = parseInt(g.home_score);
    const as = parseInt(g.away_score);
    if (isNaN(hs) || isNaN(as)) return;
    const grp = GROUPS.find(x => x.name === g.group);
    if (!grp) return;
    const home = grp.teams.find(t => String(t.team_id) === String(g.home_team_id));
    const away = grp.teams.find(t => String(t.team_id) === String(g.away_team_id));
    if (!home || !away) return;
    // mp +1（双方）
    home.mp++; away.mp++;
    // 进球
    home.gf += hs; home.ga += as;
    away.gf += as; away.ga += hs;
    // 胜负平 + 积分
    if (hs > as) {
      home.w++; home.pts += 3; away.l++;
    } else if (hs < as) {
      away.w++; away.pts += 3; home.l++;
    } else {
      home.d++; home.pts += 1; away.d++; away.pts += 1;
    }
    // 净胜球
    home.gd = home.gf - home.ga;
    away.gd = away.gf - away.ga;
  });
  // 3) 转回字符串（保持原 GROUPS 数据格式，renderGroups 用 parseInt 比较）
  GROUPS.forEach(g => {
    g.teams.forEach(t => {
      t.mp = String(t.mp); t.w = String(t.w); t.d = String(t.d); t.l = String(t.l);
      t.gf = String(t.gf); t.ga = String(t.ga); t.gd = String(t.gd); t.pts = String(t.pts);
    });
  });
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

  // 2026 世界杯：48队→12组×4队
  // 出线 32 强规则：12 组前 2 名（24 队）+ 8 个最佳第 3 名（共 32 队晋级 Round of 32）
  // 8 个最佳第 3 名排序规则（FIFA 官方）：pts → gd → gf → w → 纪律分 → 抽签
  // 注：所有小组赛打完前为"实时预测"，可能随后续比赛结果变化
  const allGroupGames = GAMES.filter(m => m.type === 'group' || !m.type);
  const totalGroupMatches = allGroupGames.length;  // 应该是 72 (12组×6场)
  const finishedGroupMatches = allGroupGames.filter(m => m.finished === 'TRUE' || m.finished === 'true').length;
  const allGroupStageFinished = (totalGroupMatches === 72 && finishedGroupMatches === 72);

  // 收集每组当前排序后的第 3 名
  const thirdPlaceTeams = [];
  GROUPS.forEach(g => {
    const sorted = [...g.teams].sort((a, b) => {
      if (parseInt(b.pts) !== parseInt(a.pts)) return parseInt(b.pts) - parseInt(a.pts);
      if (parseInt(b.gd) !== parseInt(a.gd)) return parseInt(b.gd) - parseInt(a.gd);
      return parseInt(b.gf) - parseInt(a.gf);
    });
    if (sorted[2]) {
      thirdPlaceTeams.push({
        team_id: sorted[2].team_id,
        pts: parseInt(sorted[2].pts) || 0,
        gd: parseInt(sorted[2].gd) || 0,
        gf: parseInt(sorted[2].gf) || 0,
        w: parseInt(sorted[2].w) || 0,
        group: g.name,
      });
    }
  });
  // 按 FIFA 规则排序 12 个第 3 名：pts desc, gd desc, gf desc, w desc
  thirdPlaceTeams.sort((a, b) =>
    b.pts - a.pts || b.gd - a.gd || b.gf - a.gf || b.w - a.w);
  // 前 8 名晋级 32 强
  const top8ThirdIds = new Set(thirdPlaceTeams.slice(0, 8).map(t => t.team_id));

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
      // idx 0-1 = 前 2 名直接晋级；idx 2 + 在 8 个最佳第 3 名内 = 晋级 32 强
      let rowCls = '';
      if (idx <= 1) rowCls = 'top2';                                // 直接晋级
      else if (idx === 2 && top8ThirdIds.has(t.team_id)) rowCls = 'top3best';  // 8 个最佳第 3 名
      html += `<tr class="${rowCls}">
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

  // 在页面底部加说明：哪些是 8 个最佳第 3 名晋级 32 强的队
  if (!allGroupStageFinished) {
    const qualifiers = thirdPlaceTeams.slice(0, 8).map((t, i) => {
      const tm = teamMap[t.team_id] || {};
      return `${i+1}. ${tm.name_cn || tm.name_en || 'T'+t.team_id} (组 ${t.group}, ${t.pts}分)`;
    }).join('  ·  ');
    html += `<div class="footnote" style="margin-top:24px;padding:12px 16px;background:#1a2332;border-left:4px solid #f0b400;border-radius:6px;color:#f0b400;font-size:13px;">
      ⚠️ 小组赛未全部打完（${finishedGroupMatches}/${totalGroupMatches} 场），8 个最佳第 3 名为实时预测，可能随比赛结果变化。<br>
      <span style="color:#8a96a8;font-size:12px;">当前预测晋级 32 强（第 3 名）：${qualifiers}</span>
    </div>`;
  }

// 5) 渲染树状对阵图（白线白字风格）
  const TREE_rowH = 64;     // 行高
  const TREE_colW = 180;    // 卡片宽
  const TREE_colGap = 50;   // 列间距（连线空间）
  const TREE_padX = 16;
  const TREE_padY = 40;
  const TREE_nodeH = 50;    // 卡片高

  // y 坐标计算
  function TREE_y(round, idx) {
    const map = {R32: idx, R16: 2*idx+0.5, QF: 4*idx+1.5, SF: 8*idx+3.5, F: 6.0};
    return TREE_padY + (map[round] || idx) * TREE_rowH;
  }
  function TREE_y3rd() { return TREE_padY + 9.5 * TREE_rowH; }
  // x 坐标
  const TREE_xMap = {R32:0, R16:1, QF:2, SF:3, F:4};
  function TREE_x(round) { return TREE_padX + TREE_xMap[round] * (TREE_colW + TREE_colGap); }
  function TREE_x3rd() { return TREE_padX + 4 * (TREE_colW + TREE_colGap); }

  const TREE_fullW = TREE_padX + 5 * TREE_colW + 4 * TREE_colGap + TREE_colGap + TREE_colW + TREE_padX;
  const TREE_fullH = TREE_padY + 10 * TREE_rowH + TREE_padY;

function renderKnockout() {
  const container = document.getElementById('knockoutContainer');
  if (!container) return;
  if (!KNOCKOUTS || !KNOCKOUTS.length) {
    container.innerHTML = '<div style="padding:40px;text-align:center;color:#8a96a8;">暂无淘汰赛对阵数据（wc_knockouts.json 未生成）</div>';
    return;
  }

  // 1) 整理每轮数据（5 列布局：3rd 单独渲染在 F 下方）
  const rounds = [
    {key:'R32', name:'1/16决赛', count:16},
    {key:'R16', name:'1/8决赛',  count:8},
    {key:'QF',  name:'1/4决赛',  count:4},
    {key:'SF',  name:'半决赛',   count:2},
    {key:'F',   name:'决赛',     count:1},
  ];
  // 轮次主题色（按层级递进：蓝→紫→粉→橙→金）
  const colorMap = {
    R32: '#3b82f6',  // 蓝 1/16
    R16: '#8b5cf6',  // 紫 1/8
    QF:  '#ec4899',  // 粉 1/4
    SF:  '#f59e0b',  // 橙 半决赛
    F:   '#fbbf24',  // 金 决赛
    '3rd':'#94a3b8', // 灰 季军赛
  };
  // 各轮次 hex → rgba(..., 0.08) 用于淡背景填充
  function tint(hex, alpha) {
    const r = parseInt(hex.slice(1,3), 16);
    const g = parseInt(hex.slice(3,5), 16);
    const b = parseInt(hex.slice(5,7), 16);
    return `rgba(${r},${g},${b},${alpha})`;
  }
  const bgTint   = r => tint(r, 0.10);
  const borderT  = r => tint(r, 0.55);

  // 辅助函数：是否已结束 / 是否占位符（HTML div 版 cardHtml 需要）
  function isFinished(m) {
    const g = koGames[m.no];
    return g && (g.finished === 'TRUE' || g.finished === 'true' || g.finished === true);
  }
  function isPlaceholder(s) {
    if (!s) return true;
    if (/^W\d+|^L\d+/.test(s)) return true;
    if (/^[A-L]组(首名|次名|第三名)|^第三名[A-Z/]+$/.test(s)) return true;
    return false;
  }
  function esc(s) { return (s || '').replace(/[<&"']/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'})[c]); }

  const byRound = {};
  for (const r of rounds) byRound[r.key] = [];
  byRound['3rd'] = []; // 季军赛单独渲染在 F 列下方，但需要收集数据
  for (const m of KNOCKOUTS) {
    if (byRound[m.round]) byRound[m.round].push(m);
  }
  for (const k of Object.keys(byRound)) byRound[k].sort((a,b) => a.no - b.no);

  // 2) 几何参数
  const rowH = 80;            // 每场 R32 占行高（增大以容纳 76px 卡片）
  const colW = 280;           // 比赛节点宽
  const colGap = 60;          // 列间距
  const padX = 30, padY = 90; // 边距（顶部留出轮次标题 + 阴影空间）
  const nodeH = 76;           // 节点高：容纳时间行 + 间距 + 队名行
  const headerH = 50;         // 轮次标题高

  // 3) 计算每轮 y 坐标（垂直居中树状）
  // R32 16 场 → 行 0..15
  // R16 8 场  → 行中心 = (2*idx+0.5)
  // QF  4 场  → 行中心 = (4*idx+1.5)
  // SF  2 场  → 行中心 = (8*idx+3.5)
  // F   → 行 6.0
  // 3rd → 行 8.5（紧贴 F 列下方）
  function yFor(round, idx) {
    const map = {R32: idx, R16: 2*idx+0.5, QF: 4*idx+1.5, SF: 8*idx+3.5, F: 6.0};
    return padY + (map[round] || idx) * rowH + nodeH/2;
  }
  function yForF()   { return padY + 6.0 * rowH + nodeH/2; }
  function yFor3rd() { return padY + 8.5 * rowH + nodeH/2; }

  // 4) 找已结束的淘汰赛比分（从 GAMES 中 type='knockout'）
  const koGames = {};
  for (const g of GAMES) {
    if (g.type === 'knockout' || g.match_id === 'knockout') {
      koGames[g.no] = g;
    }
  }
  for (const g of GAMES) {
    if (g.type && g.type.toLowerCase().includes('knock')) {
      koGames[g.no] = koGames[g.no] || g;
    }
  }

// 渲染单张卡片（左右分区样式）
  function cardHtml(roundKey, m) {
    const c = colorMap[roundKey];
    const finished = isFinished(m);
    const placeholderA = isPlaceholder(m.a);
    const placeholderB = isPlaceholder(m.b);

    // 边框颜色：已结束用红色，占位符用灰色，正常用轮次色
    let borderColor, bgColor;
    if (finished) {
      borderColor = '#ff4757';
      bgColor = 'rgba(255,71,87,0.08)';
    } else if (placeholderA && placeholderB) {
      borderColor = '#3a4556';
      bgColor = '#151c28';
    } else {
      borderColor = tint(c, 0.45);
      bgColor = tint(c, 0.06);
    }

    const colorA = placeholderA ? '#4a5568' : '#e8eef5';
    const colorB = placeholderB ? '#4a5568' : '#e8eef5';
    const fsA = placeholderA ? 'italic' : 'normal';
    const fsB = placeholderB ? 'italic' : 'normal';
    const wA = placeholderA ? 400 : 600;
    const wB = placeholderB ? 400 : 600;

    // 右侧比分区域
    let scoreHtml = '';
    if (finished && koGames[m.no]) {
      const g = koGames[m.no];
      const ha = g.home_score != null ? g.home_score : '';
      const aa = g.away_score != null ? g.away_score : '';
      let penHtml = '';
      if (g.home_penalty) {
        penHtml = `<div style="font-size:9px;color:#8a96a8;">P ${g.home_penalty}-${g.away_penalty}</div>`;
      }
      scoreHtml = `<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1px;">
        <div style="color:#ffd700;font-size:15px;font-weight:700;">${ha}</div>
        <div style="color:#ffd700;font-size:15px;font-weight:700;">${aa}</div>
        ${penHtml}
      </div>`;
    } else {
      scoreHtml = '<div style="color:#3a4568;font-size:18px;font-weight:300;">-</div>';
    }

    // 编号+时间行
    const metaHtml = `<div style="display:flex;align-items:center;gap:4px;margin-bottom:3px;">
      <span style="color:${c};font-size:9px;font-weight:700;">#${m.no}</span>
      <span style="color:#4a5568;font-size:9px;">${esc(m.time || '')}</span>
    </div>`;

    // 左侧队伍名（上下排列）
    const teamsHtml = `<div style="flex:1;min-width:0;display:flex;flex-direction:column;justify-content:center;gap:2px;padding-right:8px;overflow:hidden;">
      <div style="display:flex;align-items:center;gap:4px;white-space:nowrap;overflow:hidden;">
        <span style="color:${colorA};font-size:12px;font-weight:${wA};font-style:${fsA};overflow:hidden;text-overflow:ellipsis;">${esc(m.a || '?')}</span>
      </div>
      <div style="display:flex;align-items:center;gap:4px;white-space:nowrap;overflow:hidden;">
        <span style="color:${colorB};font-size:12px;font-weight:${wB};font-style:${fsB};overflow:hidden;text-overflow:ellipsis;">${esc(m.b || '?')}</span>
      </div>
    </div>`;

    // 右侧比分区（固定宽度）
    const scoreArea = `<div style="width:44px;display:flex;align-items:center;justify-content:center;border-left:1px solid ${borderColor};padding-left:6px;flex-shrink:0;">${scoreHtml}</div>`;

    return `<div class="ko-card" data-no="${m.no}" style="
      background:${bgColor};
      border:1px solid ${borderColor};
      border-radius:4px;
      overflow:hidden;
      transition:filter .15s;
      cursor:pointer;
    " onmouseover="this.style.filter='brightness(1.3)'" onmouseout="this.style.filter=''">
      ${metaHtml}
      <div style="display:flex;align-items:stretch;height:38px;padding:0 6px 4px 6px;">
        ${teamsHtml}
        ${scoreArea}
      </div>
    </div>`;
  }

  // 渲染一个轮次段（section）：标题 + 卡片网格
  function sectionHtml(roundKey, name, sub, columns, list) {
    const c = colorMap[roundKey];
    const cardsHtml = list.map(m => cardHtml(roundKey, m)).join('');
    return `<section class="ko-section" style="margin-bottom:28px;">
      <div style="display:flex;align-items:baseline;gap:12px;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid ${tint(c, 0.30)};">
        <h3 style="margin:0;color:${c};font-size:18px;font-weight:700;">${name}</h3>
        <span style="color:#8a96a8;font-size:12px;">${sub}</span>
      </div>
      <div style="display:grid;grid-template-columns:repeat(${columns},minmax(0,1fr));gap:12px;">
        ${cardsHtml}
      </div>
    </section>`;
  }

  // 顶部 H2 标题 + 最后更新日期（取自 build.py 注入的 #koUpdated）
  const lastUpdateEl = document.getElementById('koUpdated');
  const lastUpdate = lastUpdateEl ? lastUpdateEl.textContent.trim() : '';
  let html = `<div style="margin-bottom:22px;padding-bottom:14px;border-bottom:2px solid #2a3445;">
    <h2 style="margin:0 0 6px 0;color:#e8eef5;font-size:22px;font-weight:700;">2026世界杯淘汰赛对阵表与赛程</h2>
    <div style="color:#8a96a8;font-size:13px;">最后更新：${lastUpdate}</div>
  </div>`;

  

    // 渲染卡片（白框风格）
  function treeCard(m, roundKey) {
    const finished = isFinished(m);
    const phA = isPlaceholder(m.a);
    const phB = isPlaceholder(m.b);
    let scoreText = '';
    if (finished && koGames[m.no]) {
      const g = koGames[m.no];
      const ha = g.home_score ?? ''; const aa = g.away_score ?? '';
      scoreText = `${ha}:${aa}`;
      if (g.home_penalty) scoreText += ` (${g.home_penalty}:${g.away_penalty})`;
    } else if (!phA && !phB) {
      scoreText = 'VS';
    }
    return `<div style="width:${TREE_colW}px;height:${TREE_nodeH}px;border:1px solid rgba(255,255,255,0.6);border-radius:2px;display:flex;flex-direction:column;justify-content:center;padding:0 8px;background:rgba(0,0,0,0.3);">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:6px;">
        <span style="color:${phA ? 'rgba(255,255,255,0.3)' : '#fff'};font-size:12px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;">${esc(m.a || '?')}</span>
        ${scoreText ? `<span style="color:#fff;font-size:12px;font-weight:700;flex-shrink:0;">${scoreText}</span>` : ''}
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;gap:6px;margin-top:2px;">
        <span style="color:${phB ? 'rgba(255,255,255,0.3)' : '#fff'};font-size:12px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;">${esc(m.b || '?')}</span>
      </div>
    </div>`;
  }

  // SVG 连线（白色 L 形）
  function svgBracketLines() {
    let svg = `<svg style="position:absolute;left:0;top:0;width:${TREE_fullW}px;height:${TREE_fullH}px;pointer-events:none;">`;
    const lineColor = 'rgba(255,255,255,0.5)';
    const sw = 1.5;

    // R32 → R16
    for (let i = 0; i < 8; i++) {
      const x1 = TREE_x('R32') + TREE_colW;
      const x2 = TREE_x('R16');
      const yA = TREE_y('R32', 2*i) + TREE_nodeH/2;
      const yB = TREE_y('R32', 2*i+1) + TREE_nodeH/2;
      const yC = TREE_y('R16', i) + TREE_nodeH/2;
      const mx = (x1 + x2) / 2;
      svg += `<path d="M${x1},${yA} H${mx} V${yC} H${x2}" stroke="${lineColor}" stroke-width="${sw}" fill="none"/>`;
      svg += `<path d="M${x1},${yB} H${mx} V${yC}" stroke="${lineColor}" stroke-width="${sw}" fill="none"/>`;
    }
    // R16 → QF
    for (let i = 0; i < 4; i++) {
      const x1 = TREE_x('R16') + TREE_colW;
      const x2 = TREE_x('QF');
      const yA = TREE_y('R16', 2*i) + TREE_nodeH/2;
      const yB = TREE_y('R16', 2*i+1) + TREE_nodeH/2;
      const yC = TREE_y('QF', i) + TREE_nodeH/2;
      const mx = (x1 + x2) / 2;
      svg += `<path d="M${x1},${yA} H${mx} V${yC} H${x2}" stroke="${lineColor}" stroke-width="${sw}" fill="none"/>`;
      svg += `<path d="M${x1},${yB} H${mx} V${yC}" stroke="${lineColor}" stroke-width="${sw}" fill="none"/>`;
    }
    // QF → SF
    for (let i = 0; i < 2; i++) {
      const x1 = TREE_x('QF') + TREE_colW;
      const x2 = TREE_x('SF');
      const yA = TREE_y('QF', 2*i) + TREE_nodeH/2;
      const yB = TREE_y('QF', 2*i+1) + TREE_nodeH/2;
      const yC = TREE_y('SF', i) + TREE_nodeH/2;
      const mx = (x1 + x2) / 2;
      svg += `<path d="M${x1},${yA} H${mx} V${yC} H${x2}" stroke="${lineColor}" stroke-width="${sw}" fill="none"/>`;
      svg += `<path d="M${x1},${yB} H${mx} V${yC}" stroke="${lineColor}" stroke-width="${sw}" fill="none"/>`;
    }
    // SF → F
    {
      const x1 = TREE_x('SF') + TREE_colW;
      const x2 = TREE_x('F');
      const yA = TREE_y('SF', 0) + TREE_nodeH/2;
      const yB = TREE_y('SF', 1) + TREE_nodeH/2;
      const yC = TREE_y('F', 0) + TREE_nodeH/2;
      const mx = (x1 + x2) / 2;
      svg += `<path d="M${x1},${yA} H${mx} V${yC} H${x2}" stroke="${lineColor}" stroke-width="${sw}" fill="none"/>`;
      svg += `<path d="M${x1},${yB} H${mx} V${yC}" stroke="${lineColor}" stroke-width="${sw}" fill="none"/>`;
    }
    // SF → 3rd（虚线）
    {
      const x1 = TREE_x('SF') + TREE_colW;
      const x2 = TREE_x3rd();
      const yA = TREE_y('SF', 0) + TREE_nodeH/2;
      const yB = TREE_y('SF', 1) + TREE_nodeH/2;
      const yC = TREE_y3rd() + TREE_nodeH/2;
      const mx = (x1 + x2) / 2;
      svg += `<path d="M${x1},${yA} H${mx} V${yC} H${x2}" stroke="rgba(255,255,255,0.25)" stroke-width="${sw}" fill="none" stroke-dasharray="4 3"/>`;
      svg += `<path d="M${x1},${yB} H${mx} V${yC}" stroke="rgba(255,255,255,0.25)" stroke-width="${sw}" fill="none" stroke-dasharray="4 3"/>`;
    }
    svg += `</svg>`;
    return svg;
  }

  // 轮次标题
  const roundHeaders = [
    {key:'R32', name:'1/16决赛'}, {key:'R16', name:'1/8决赛'},
    {key:'QF', name:'1/4决赛'}, {key:'SF', name:'半决赛'}, {key:'F', name:'决赛'}
  ];

  html += `<div style="overflow-x:auto;padding:10px 0;">`;
  html += `<div style="position:relative;width:${TREE_fullW}px;height:${TREE_fullH}px;">`;

  // SVG 连线
  html += svgBracketLines();

  // 轮次标题
  for (const rh of roundHeaders) {
    const x = TREE_x(rh.key);
    html += `<div style="position:absolute;left:${x}px;top:0;width:${TREE_colW}px;text-align:center;color:rgba(255,255,255,0.7);font-size:13px;font-weight:600;border-bottom:1px solid rgba(255,255,255,0.2);padding-bottom:6px;">${rh.name}</div>`;
  }
  // 季军赛标题
  html += `<div style="position:absolute;left:${TREE_x3rd()}px;top:0;width:${TREE_colW}px;text-align:center;color:rgba(255,255,255,0.5);font-size:13px;font-weight:600;border-bottom:1px dashed rgba(255,255,255,0.2);padding-bottom:6px;">季军赛</div>`;

  // 卡片
  function placeCards(round, matches) {
    const x = TREE_x(round);
    for (let i = 0; i < matches.length; i++) {
      const y = TREE_y(round, i);
      html += `<div style="position:absolute;left:${x}px;top:${y}px;">${treeCard(matches[i], round)}</div>`;
    }
  }
  placeCards('R32', byRound['R32'] || []);
  placeCards('R16', byRound['R16'] || []);
  placeCards('QF', byRound['QF'] || []);
  placeCards('SF', byRound['SF'] || []);
  if (byRound['F'] && byRound['F'][0]) {
    html += `<div style="position:absolute;left:${TREE_x('F')}px;top:${TREE_y('F', 0)}px;">${treeCard(byRound['F'][0], 'F')}</div>`;
  }
  if (byRound['3rd'] && byRound['3rd'][0]) {
    html += `<div style="position:absolute;left:${TREE_x3rd()}px;top:${TREE_y3rd()}px;">${treeCard(byRound['3rd'][0], '3rd')}</div>`;
  }

  html += `</div></div>`;

  
    container.innerHTML = html;
}

// ==== 淘汰赛对阵表（思维导图样式 SVG）====
// 32 场对阵来自 wc_knockouts.json：R32(16) → R16(8) → QF(4) → SF(2) → 3rd(1) + F(1)
// 布局：5 列 R32/R16/QF/SF/F，季军赛 3rd 单独放在 F 列下方
// 颜色：按轮次主题色（蓝→紫→粉→橙→金），淡色背景 + 半透明边框
// 已结束：保持红色 #ff4757 边框 + 显示比分（最高优先级覆盖主题色）
// 占位符：灰色虚线 #8a96a8 + dasharray
// 已确定国家队：实线主题色边框

  container.innerHTML = html;
}

// ==== 实时数据拉取 ====
const LIVE_API = 'https://worldcup26.ir/get/games';
let _liveTimer = null;

// local_date = 美西 PDT (UTC-7) → 北京时间 (UTC+8) = +15h
// 注：6月美国是夏令时，2026世界杯比赛当地多为西海岸时间(PDT)
//    反推验证：TUR vs USA 06/25 19:00 PDT = 06/26 10:00 北京 ✓
function toBeijing(s) {
  if (!s) return s;
  const m = s.match(/^(\d{2})\/(\d{2})\/(\d{4})\s+(\d{2}):(\d{2})$/);
  if (!m) return s;
  const mo = parseInt(m[1]) - 1, d = parseInt(m[2]), y = parseInt(m[3]);
  const h = parseInt(m[4]), mi = parseInt(m[5]);
  // 1) 美西 → UTC: 美西 PDT = UTC-7, 所以 +7h 得 UTC
  //    Date.UTC 自动规范化越界小时/日期
  const utc = new Date(Date.UTC(y, mo, d, h + 7, mi));
  // 2) UTC → 北京: +8h
  utc.setUTCHours(utc.getUTCHours() + 8);
  return utc;
}
function toBeijingStr(s) {
  const utc = toBeijing(s);
  if (!(utc instanceof Date) || isNaN(utc)) return s;
  const yy = utc.getUTCFullYear();
  const mm = String(utc.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(utc.getUTCDate()).padStart(2, '0');
  const hh = String(utc.getUTCHours()).padStart(2, '0');
  const mii = String(utc.getUTCMinutes()).padStart(2, '0');
  return `${yy}-${mm}-${dd} ${hh}:${mii}`;
}
const _BJ = '(北京时间)';
// 投注截止：开赛前 2 小时
const BETTING_CUTOFF_MS = 2 * 60 * 60 * 1000;
function kickoffDate(g) { return toBeijing(g.local_date); }
function bettingClosed(g) {
  if (g.finished === 'TRUE' || g.finished === 'true') return '已结束';
  const ko = kickoffDate(g);
  if (!(ko instanceof Date) || isNaN(ko)) return null;
  const diff = ko.getTime() - Date.now();
  if (diff <= 0) return '已开赛';
  if (diff <= BETTING_CUTOFF_MS) return '已截止（开赛前 2 小时内禁止投注）';
  return null;  // null = 仍可投注
}
function cutoffMinutesLeft(g) {
  const ko = kickoffDate(g);
  if (!(ko instanceof Date) || isNaN(ko)) return null;
  const diff = ko.getTime() - Date.now();
  return Math.max(0, Math.floor(diff / 60000));
}

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
    // 拉取完实时比分后，按已结束的小组赛重算积分，并刷新 groups tab
    recalcGroupsFromGames();
    if (document.getElementById('tab-groups').style.display !== 'none') renderGroups();
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
  // 排序：进行中 → 未开始（按时间升序，最早在前）→ 已结束（按时间降序，最新结束在前）
  const toTs = g => {
    // local_date 格式可能是 "YYYY/MM/DD HH" 或 "MM/DD/YYYY HH:MM"
    const d = g.local_date || '';
    let m = /(\d{4})\/(\d{2})\/(\d{2})\s+(\d{1,2})/.exec(d);  // YYYY/MM/DD HH
    if (m) return Date.UTC(+m[1], +m[2]-1, +m[3], +m[4]);
    m = /(\d{2})\/(\d{2})\/(\d{4})\s+(\d{2}):(\d{2})/.exec(d);  // MM/DD/YYYY HH:MM
    if (m) return Date.UTC(+m[3], +m[1]-1, +m[2], +m[4], +m[5]);
    return 0;
  };
  list.sort((a, b) => {
    const sa = gameStatus(a), sb = gameStatus(b);
    if (sa !== sb) return sa === 1 ? -1 : sb === 1 ? 1 : (sa === 0 ? -1 : 1);
    const ta = toTs(a), tb = toTs(b);
    return sa === 2 ? tb - ta : ta - tb;
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
      statusBadge = `<span class="status-upcoming">${toBeijingStr(g.local_date)}</span>`;
    }
    // 比分或 VS（含加时/点球）
    const scoreHtml = (isFinished || isLive)
      ? (() => {
          let main = `${g.home_score} - ${g.away_score}`;
          let extra = '';
          if (g.home_penalty) {
            extra = `<div style="font-size:12px;color:#ffd700;margin-top:2px">点球 ${g.home_penalty} - ${g.away_penalty}</div>`;
          } else if (g.home_bigscore && g.home_bigscore !== g.home_score) {
            extra = `<div style="font-size:12px;color:#ffd700;margin-top:2px">总比分 ${g.home_bigscore} - ${g.away_bigscore}</div>`;
          }
          return `<div class="score ${isLive ? 'live' : ''}">${main}${extra}</div>`;
        })()
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
        <span style="font-size:11px;color:#8a96a8">${toBeijingStr(g.local_date)} · ${_BJ}</span>
        ${!isFinished && !isLive ? (() => {
          const reason = bettingClosed(g);
          if (reason) return `<button class="bet-btn" disabled style="background:#555;cursor:not-allowed" title="${reason}">已截止</button>`;
          const left = cutoffMinutesLeft(g);
          const tip = left <= 24 * 60 ? `距截止 ${(left/60).toFixed(1)} 小时` : `投注截止：开赛前 2 小时`;
          return `<button class="bet-btn" onclick="openBetModal('${g.id}')" title="${tip}">投注</button>`;
        })() : ''}
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
    <div style="color:#8a96a8;margin-top:6px">组 ${g.group} · MD${g.matchday} · ${toBeijingStr(g.local_date)} · ${_BJ}</div>
  `;
  // 胜平负（用当前比赛动态赔率 g.odds_wdl）
  const wdl = document.getElementById('wdlOptions');
  const homeShort = (home.name_cn || home.name_en).substring(0, 4);
  const awayShort = (away.name_cn || away.name_en).substring(0, 4);
  const oWdl = oddsWdl(g);
  wdl.innerHTML = [
    { v: 'home', l: '主胜 ' + homeShort },
    { v: 'draw', l: '平局' },
    { v: 'away', l: '客胜 ' + awayShort }
  ].map(o => `<div class="option" data-type="wdl" data-value="${o.v}" onclick="selectOption(this)">
    <div class="label">${o.l}</div><div class="odds">@ ${oWdl[o.v].toFixed(2)}</div>
  </div>`).join('');
  // 总进球（用当前比赛动态赔率 g.odds_goals）
  const goals = document.getElementById('goalsOptions');
  const oGoals = oddsGoals(g);
  goals.innerHTML = Object.entries(oGoals).map(([k, v]) => `<div class="option" data-type="goals" data-value="${k}" onclick="selectOption(this)">
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
  // 检查投注截止（开赛前 2 小时）
  const closed = bettingClosed(currentModalGame);
  if (closed) {
    alert(closed);
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
  const oWdl = oddsWdl(currentModalGame);
  const oGoals = oddsGoals(currentModalGame);
  const odds = currentModalSelection.type === 'wdl' ? oWdl[currentModalSelection.value] : oGoals[currentModalSelection.value];
  const g = currentModalGame;
  const home = teamMap[g.home_team_id] || { name_en: g.home_team_name_en, name_cn: g.home_team_name_cn };
  const away = teamMap[g.away_team_id] || { name_en: g.away_team_name_en, name_cn: g.away_team_name_cn };
  betSlip.push({
    gameId: g.id,
    gameLabel: `${home.name_cn || home.name_en} vs ${away.name_cn || away.name_en}`,
    gameDate: toBeijingStr(g.local_date),
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

html = html.replace('__GAMES__', games_json).replace('__GROUPS__', groups_json).replace('__TEAMS__', teams_json).replace('__KNOCKOUTS__', knockouts_json)
# 注入淘汰赛数据最后更新时间（取 wc_knockouts.json 的 mtime）
ko_json_path = proj / 'wc_knockouts.json'
if ko_json_path.exists():
  ko_updated = time.strftime('%Y年%m月%d日', time.localtime(ko_json_path.stat().st_mtime))
else:
  ko_updated = time.strftime('%Y年%m月%d日', time.localtime())
html = html.replace('__KO_UPDATED__', ko_updated)
out = proj / 'index.html'
out.write_text(html, encoding='utf-8')
print(f"[OK] {out}  size={out.stat().st_size} bytes")
