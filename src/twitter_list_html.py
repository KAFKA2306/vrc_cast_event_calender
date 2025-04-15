import pandas as pd

# CSVファイル読み込み
df = pd.read_csv('twitter_profiles/profiles_organized_20250415_195525.csv', encoding='utf-8-sig')

# 開催頻度・開催曜日が両方空欄の行を除外
df = df[~(df['開催頻度'].isna() | (df['開催頻度'] == '')) | ~(df['開催曜日'].isna() | (df['開催曜日'] == ''))]

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
            info = ''
            
            if pd.notnull(row['定期開催時刻 (開始)']) and str(row['定期開催時刻 (開始)']).strip():
                info += f'<span class="time">{row["定期開催時刻 (開始)"]}</span> '
            
            if pd.notnull(row['account_id']) and str(row['account_id']).strip():
                info += f'<a href="https://twitter.com/{row["account_id"]}" target="_blank" class="account">@{row["account_id"]}</a> '
            
            if pd.notnull(row['公式ハッシュタグ']) and str(row['公式ハッシュタグ']).strip():
                info += f'<span class="hashtag">{row["公式ハッシュタグ"]}</span> '

            if pd.notnull(row['主催者']) and str(row['主催者']).strip():
                info += f'<span class="organizer">主催: {row["主催者"]}</span>'

            calendar[day].append((row['定期開催時刻 (開始)'], info))

# 開始時刻順に並べる
for day in calendar:
    calendar[day].sort(key=lambda x: (x[0] if pd.notnull(x[0]) and x[0] else '99:99'))
    calendar[day] = [ev[1] for ev in calendar[day]]

# HTML生成
html = '''<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VRCキャストイベントカレンダー</title>
    <style>
        body {
            font-family: 'Arial', 'Hiragino Kaku Gothic ProN', sans-serif;
            background-color: #f8f9fa;
            color: #333;
            line-height: 1.6;
            padding: 20px;
        }
        h1 {
            color: #6c5ce7;
            text-align: center;
            margin-bottom: 30px;
        }
        h2 {
            color: #6c5ce7;
            margin-top: 40px;
            margin-bottom: 20px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        th {
            background-color: #a29bfe;
            color: white;
            padding: 12px;
            text-align: center;
            font-weight: bold;
        }
        td {
            background-color: #fff;
            padding: 10px;
            border: 1px solid #ddd;
            vertical-align: top;
        }
        td:nth-child(6), td:nth-child(7) {
            background-color: #e4f0fb;
        }
        .event-item {
            padding: 8px 0;
            border-bottom: 1px dashed #ddd;
            margin-bottom: 8px;
        }
        .time {
            font-weight: bold;
            color: #e84393;
            margin-right: 5px;
        }
        .account {
            color: #0984e3;
            text-decoration: none;
            font-weight: bold;
        }
        .account:hover {
            text-decoration: underline;
        }
        .hashtag {
            color: #00b894;
            margin: 0 5px;
        }
        .organizer {
            color: #6c5ce7;
            font-size: 0.9em;
            display: block;
            margin-top: 3px;
        }
        ul {
            list-style-type: none;
            padding: 0;
        }
        li {
            background-color: white;
            padding: 12px 15px;
            margin-bottom: 10px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        li:hover {
            background-color: #f5f5f5;
        }
        .footer {
            text-align: center;
            margin-top: 40px;
            color: #777;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <h1>VRCキャストイベントカレンダー</h1>
'''

html += '<table><tr><th>月</th><th>火</th><th>水</th><th>木</th><th>金</th><th>土</th><th>日</th></tr><tr>'

for day in ['月', '火', '水', '木', '金', '土', '日']:
    html += '<td>'
    for ev in calendar[day]:
        html += f'<div class="event-item">{ev}</div>'
    html += '</td>'
html += '</tr></table>'

html += '<h2>不定期イベント</h2><ul>'
for _, row in irregular_df.iterrows():
    info = '<div>'
    
    if pd.notnull(row['account_id']) and str(row['account_id']).strip():
        info += f'<a href="https://twitter.com/{row["account_id"]}" target="_blank" class="account">@{row["account_id"]}</a> '
    
    if pd.notnull(row['イベント名']) and str(row['イベント名']).strip():
        info += f'<strong>{row["イベント名"]}</strong> '
    
    if pd.notnull(row['公式ハッシュタグ']) and str(row['公式ハッシュタグ']).strip():
        info += f'<span class="hashtag">{row["公式ハッシュタグ"]}</span> '
    
    if pd.notnull(row['主催者']) and str(row['主催者']).strip():
        info += f'<span class="organizer">主催: {row["主催者"]}</span>'
    
    info += '</div>'
    html += f'<li>{info}</li>'
html += '</ul>'

html += '''
    <div class="footer">
        <p>最終更新: 2025年4月15日</p>
    </div>
</body>
</html>
'''

# HTMLファイルに書き出し
with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)
