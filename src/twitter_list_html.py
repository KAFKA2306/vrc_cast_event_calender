import pandas as pd

# CSVファイル読み込み
df = pd.read_csv('twitter_profiles/profiles_organized_20250415_195525.csv', encoding='utf-8-sig')

# 開催頻度・開催曜日が両方空欄の行を除外
df = df[~(df['開催頻度'].isna() | (df['開催頻度'] == '')) | ~(df['開催曜日'].isna() | (df['開催曜日'] == ''))]

# イベント名補完
def get_event_name(row):
    if pd.notnull(row['イベント名']) and str(row['イベント名']).strip():
        return str(row['イベント名'])
    if pd.notnull(row['公式ハッシュタグ']) and str(row['公式ハッシュタグ']).strip():
        return str(row['公式ハッシュタグ']).split()[0]
    return row['account_id']

df['イベント名_補完'] = df.apply(get_event_name, axis=1)

# 曜日展開
def expand_weekdays(row):
    if pd.isna(row['開催曜日']) or not str(row['開催曜日']).strip():
        return []
    val = str(row['開催曜日'])
    if '週末' in val:
        return ['土', '日']
    if '平日' in val:
        return ['月', '火', '水', '木', '金']
    return [d for d in val.replace('・', ',').replace(' ', ',').split(',') if d in ['月','火','水','木','金','土','日']]

df['曜日リスト'] = df.apply(expand_weekdays, axis=1)

# 定期/不定期分類
is_regular = df['開催頻度'].fillna('').str.contains('毎週|隔週|毎月|月\d回|週末|平日')
regular_df = df[is_regular]
irregular_df = df[~is_regular]

# カレンダー用データ整形
calendar = {d: [] for d in ['月', '火', '水', '木', '金', '土', '日']}
for _, row in regular_df.iterrows():
    for day in row['曜日リスト']:
        if day in calendar:
            info = f'<a href="{row["メンバーのtwitterのリンク"]}" target="_blank">{row["イベント名_補完"]}</a>'
            if pd.notnull(row['定期開催時刻 (開始)']) and str(row['定期開催時刻 (開始)']).strip():
                info += f' <span style="color:#888;">{row["定期開催時刻 (開始)"]}</span>'
            if pd.notnull(row['主催者']) and str(row['主催者']).strip():
                info += f' <span style="color:#006;">{row["主催者"]}</span>'
            if pd.notnull(row['公式ハッシュタグ']) and str(row['公式ハッシュタグ']).strip():
                info += f' <span style="color:#080;">{row["公式ハッシュタグ"]}</span>'
            if pd.notnull(row['グループID']) and str(row['グループID']).strip():
                info += f' <span style="color:#a60;">{row["グループID"]}</span>'
            calendar[day].append((row['定期開催時刻 (開始)'], info))

# 開始時刻順に並べる
for day in calendar:
    calendar[day].sort(key=lambda x: (x[0] if pd.notnull(x[0]) and x[0] else '99:99'))
    calendar[day] = [ev[1] for ev in calendar[day]]

# HTML生成
html = '''
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>VRCイベントカレンダー</title>
<style>
body { font-family: sans-serif; margin: 20px; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #ddd; padding: 8px; text-align: left; vertical-align: top; }
th { background-color: #f2f2f2; font-weight: bold; }
tr:nth-child(even) { background-color: #f9f9f9; }
.event { margin-bottom: 8px; }
.irregular { margin-top: 30px; }
</style>
</head>
<body>
<h2>VRCイベント ウィークリーカレンダー</h2>
<table>
<tr>
  <th>月</th><th>火</th><th>水</th><th>木</th><th>金</th><th>土</th><th>日</th>
</tr>
<tr>
'''

for day in ['月', '火', '水', '木', '金', '土', '日']:
    html += '<td>'
    for ev in calendar[day]:
        html += f'<div class="event">{ev}</div>'
    html += '</td>'
html += '</tr></table>'

# 不定期イベントリスト
html += '<div class="irregular"><h3>不定期イベント一覧</h3><ul>'
for _, row in irregular_df.iterrows():
    name = row['イベント名_補完']
    link = row['メンバーのtwitterのリンク']
    info = f'<a href="{link}" target="_blank">{name}</a>'
    if pd.notnull(row['主催者']) and str(row['主催者']).strip():
        info += f' <span style="color:#006;">{row["主催者"]}</span>'
    if pd.notnull(row['公式ハッシュタグ']) and str(row['公式ハッシュタグ']).strip():
        info += f' <span style="color:#080;">{row["公式ハッシュタグ"]}</span>'
    if pd.notnull(row['グループID']) and str(row['グループID']).strip():
        info += f' <span style="color:#a60;">{row["グループID"]}</span>'
    html += f'<li>{info}</li>'
html += '</ul></div>'

html += '</body></html>'

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)
