import pandas as pd
from datetime import datetime

# ファイル読み込み
df1 = pd.read_csv('twitter_profiles/profiles_organized_20250415_195525.csv', encoding='utf-8-sig')
print(df1.shape)
df2 = pd.read_csv('twitter_profiles/profiles_organized_20250416_175429.csv', encoding='utf-8-sig')
print(df2.shape)
df3 = pd.read_csv('twitter_data/events_organized_20250416_181217.csv', encoding='utf-8-sig')
print(df3.shape)
df = pd.concat([df1, df2, df3])
print(df.shape)

# 前処理: 重複行の削除（account_idとイベント名の組み合わせで判定）
if 'account_id' in df.columns and 'イベント名' in df.columns:
    df = df.drop_duplicates(subset=['account_id', 'イベント名'], keep='first')
    print(f"重複削除後: {df.shape}")

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

# 各曜日ごとにアカウントとイベントの組み合わせを記録
day_event_accounts = {day: set() for day in calendar.keys()}

# 定期イベントの曜日別リストを作成（重複なし）
for _, row in regular_df.iterrows():
    for day in row['曜日リスト']:
        if day in calendar:
            # アカウントとイベント名のキーを作成
            account_id = str(row.get('account_id', '')) if pd.notnull(row.get('account_id')) else ''
            event_name = str(row.get('イベント名', '')) if pd.notnull(row.get('イベント名')) else ''
            event_key = f"{account_id}_{event_name}"
            
            # すでに同じアカウント+イベントの組み合わせがある場合はスキップ
            if account_id and event_key in day_event_accounts[day]:
                continue
            
            # この組み合わせを記録
            if account_id:
                day_event_accounts[day].add(event_key)
            
            info = ''
            if pd.notnull(row.get('定期開催時刻 (開始)')) and str(row['定期開催時刻 (開始)']).strip():
                info += f'<span class="time">{row["定期開催時刻 (開始)"]}</span> '
            if pd.notnull(row.get('account_id')) and str(row['account_id']).strip():
                info += f'<a href="https://twitter.com/{row["account_id"]}" target="_blank" class="account">@{row["account_id"]}</a> '
            if pd.notnull(row.get('公式ハッシュタグ')) and str(row['公式ハッシュタグ']).strip():
                info += f'<span class="hashtag">{row["公式ハッシュタグ"]}</span> '
            if pd.notnull(row.get('主催者')) and str(row['主催者']).strip():
                info += f'<span class="organizer">主催: {row["主催者"]}</span>'
            
            # 開始時刻を取得（NaNの場合は最後尾に配置するため99:99を使用）
            start_time = row.get('定期開催時刻 (開始)') if pd.notnull(row.get('定期開催時刻 (開始)')) else '99:99'
            calendar[day].append((start_time, info))

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

# 不定期イベントの重複をチェックするための集合
seen_irregular_events = set()

html += '<h2>不定期イベント</h2><ul>'
for _, row in irregular_df.iterrows():
    has_account = pd.notnull(row.get('account_id')) and str(row['account_id']).strip()
    has_event = pd.notnull(row.get('イベント名')) and str(row['イベント名']).strip()
    
    # アカウントとイベント名の両方がある場合のみ表示
    if not (has_account and has_event):
        continue
    
    # 重複チェック
    event_key = f"{row['account_id']}_{row['イベント名']}"
    if event_key in seen_irregular_events:
        continue
    
    seen_irregular_events.add(event_key)
    
    info = '<div>'
    if has_account:
        info += f'<a href="https://twitter.com/{row["account_id"]}" target="_blank" class="account">@{row["account_id"]}</a> '
    if has_event:
        info += f'<strong>{row["イベント名"]}</strong> '
    if pd.notnull(row.get('公式ハッシュタグ')) and str(row['公式ハッシュタグ']).strip():
        info += f'<span class="hashtag">{row["公式ハッシュタグ"]}</span> '
    if pd.notnull(row.get('主催者')) and str(row['主催者']).strip():
        info += f'<span class="organizer">主催: {row["主催者"]}</span>'
    info += '</div>'
    html += f'<li>{info}</li>'
html += '</ul>'

html += f'''
    <div class="footer">
        <p>最終更新: {datetime.now().strftime("%Y年%m月%d日")}</p>
    </div>
</body>
</html>
'''

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("HTMLファイルを生成しました: index.html")
