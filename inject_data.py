"""把 wc_games_slim.json / wc_groups.json / wc_teams.json 注入到 index.html 的占位符里。"""
import json, re, sys
from pathlib import Path

proj = Path(r'D:\VSCodeProject\worldcup2026-bet')
html_path = proj / 'index.html'

if not html_path.exists():
    print(f"[!] {html_path} 不存在，等 CC 写完")
    sys.exit(1)

with open(html_path, encoding='utf-8') as f:
    html = f.read()

# 读三个数据源
with open(proj / 'wc_games_slim.json', encoding='utf-8') as f:
    games = json.load(f)['games']
with open(proj / 'wc_groups.json', encoding='utf-8') as f:
    groups_data = json.load(f)
with open(proj / 'wc_teams.json', encoding='utf-8') as f:
    teams_data = json.load(f)

groups = groups_data.get('groups', groups_data)
teams = teams_data.get('teams', teams_data)

# 把 JSON 字符串转义为安全的 HTML <script> 内容
games_json = json.dumps(games, ensure_ascii=False)
groups_json = json.dumps(groups, ensure_ascii=False)
teams_json = json.dumps(teams, ensure_ascii=False)

# 替换三种占位符
patterns = [
    (r'<script type="application/json" id="data-games">\[?/?\*?\s*INJECT[^\]]*\]?\s*\*?/?</script>',
     f'<script type="application/json" id="data-games">{games_json}</script>'),
    (r'<script type="application/json" id="data-groups">\[?/?\*?\s*INJECT[^\]]*\]?\s*\*?/?</script>',
     f'<script type="application/json" id="data-groups">{groups_json}</script>'),
    (r'<script type="application/json" id="data-teams">\[?/?\*?\s*INJECT[^\]]*\]?\s\*?/?</script>',
     f'<script type="application/json" id="data-teams">{teams_json}</script>'),
]

for pat, repl in patterns:
    new_html, n = re.subn(pat, repl, html, flags=re.IGNORECASE | re.DOTALL)
    if n > 0:
        html = new_html
        print(f"  [OK] replaced {n} placeholders matching: {pat[:50]}...")
    else:
        print(f"  [!] no placeholder matched: {pat[:50]}...")

# 输出
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"[DONE] {html_path}, {html_path.stat().st_size} bytes")
print(f"  games: {len(games)} matches ({sum(1 for g in games if g.get('finished')=='TRUE')} finished, {sum(1 for g in games if g.get('finished')!='TRUE')} upcoming)")
print(f"  groups: {len(groups)}")
print(f"  teams: {len(teams)}")