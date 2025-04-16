import pandas as pd
from datetime import datetime
import re # 正規表現モジュールをインポート

# ファイル読み込み
# ファイルパスは環境に合わせて調整してください
try:
    df1 = pd.read_csv('twitter_profiles/profiles_organized_20250415_195525.csv', encoding='utf-8-sig')
    print(f"df1 shape: {df1.shape}")
except FileNotFoundError:
    print("Warning: profiles_organized_20250415_195525.csv not found.")
    df1 = pd.DataFrame()

try:
    df2 = pd.read_csv('twitter_profiles/profiles_organized_20250416_175429.csv', encoding='utf-8-sig')
    print(f"df2 shape: {df2.shape}")
except FileNotFoundError:
    print("Warning: profiles_organized_20250416_175429.csv not found.")
    df2 = pd.DataFrame()

try:
    # ユーザー指定のファイルパスを使用
    df3_path = r'M:\DB\event\twitter_data\events_organized_20250416_195806.csv'
    df3 = pd.read_csv(df3_path, encoding='utf-8-sig')
    print(f"df3 shape: {df3.shape}")
except FileNotFoundError:
    print(f"Warning: {df3_path} not found.")
    df3 = pd.DataFrame()

# 存在するデータフレームのみを結合
existing_dfs = [df for df in [df1, df2, df3] if not df.empty]
if not existing_dfs:
    print("Error: No dataframes to concatenate. Exiting.")
    exit()

df = pd.concat(existing_dfs, ignore_index=True)
print(f"Combined df shape: {df.shape}")

# 結合結果を一時保存（デバッグ用）
try:
    df.to_csv(r'M:\DB\event\twitter_data\concat_all.csv', index=False, encoding='utf-8-sig')
    print("Saved combined data to concat_all.csv")
except Exception as e:
    print(f"Error saving combined CSV: {e}")


# 前処理: 重複行の削除（account_id と イベント名 の組み合わせで判定）
# 'account_id' が存在しない場合があるため、存在する列のみで判定
subset_cols_duplicates = ['イベント名']
if 'account_id' in df.columns:
    subset_cols_duplicates.append('account_id')
# '定期開催時刻 (開始)' もキーに加える
if '定期開催時刻 (開始)' in df.columns:
     subset_cols_duplicates.append('定期開催時刻 (開始)')

# NaNを空文字列に変換してから重複削除
for col in subset_cols_duplicates:
     if col in df.columns:
         df[col] = df[col].fillna('')

if all(col in df.columns for col in subset_cols_duplicates):
    original_len = len(df)
    df = df.drop_duplicates(subset=subset_cols_duplicates, keep='first')
    print(f"重複削除後 (キー: {', '.join(subset_cols_duplicates)}): {original_len}行 -> {df.shape[0]}行")
else:
    print("Warning: Not all columns for duplicate check exist. Skipping duplicate removal based on subset.")


# 開催頻度・開催曜日が両方空欄の行を除外
# NaNを考慮
df = df[
    ~( (df['開催頻度'].isna()) | (df['開催頻度'] == '') ) |
    ~( (df['開催曜日'].isna()) | (df['開催曜日'] == '') )
]
print(f"空欄行除外後: {df.shape}")


# 曜日展開
def expand_weekdays(row):
    if pd.isna(row.get('開催曜日')) or not str(row['開催曜日']).strip():
        return []
    val = str(row['開催曜日'])
    # 短縮形と完全形の両方に対応
    if '週末' in val:
        return ['土', '日']
    if '平日' in val:
        return ['月', '火', '水', '木', '金']
    # 区切り文字として「・」「,」「 」に対応し、曜日文字のみを抽出
    days = re.findall(r'[月火水木金土日]', val)
    return list(set(days)) # 重複を除去

df['曜日リスト'] = df.apply(expand_weekdays, axis=1)


# 定期/不定期分類
# NaNを空文字列として扱って判定
is_regular = df['開催頻度'].fillna('').str.contains('毎週|隔週|毎月|月\d回|週末|平日')
regular_df = df[is_regular].copy() # SettingWithCopyWarning 対策
irregular_df = df[~is_regular].copy() # SettingWithCopyWarning 対策
print(f"定期イベント: {len(regular_df)}件, 不定期イベント: {len(irregular_df)}件")


# カレンダー用データ整形
calendar = {d: [] for d in ['月', '火', '水', '木', '金', '土', '日']}

# 各曜日ごとにアカウントとイベントの組み合わせを記録（重複表示防止）
day_event_accounts = {day: set() for day in calendar.keys()}

# 定期イベントの曜日別リストを作成（重複なし）
for _, row in regular_df.iterrows():
    account_id = str(row.get('account_id', '')) if pd.notnull(row.get('account_id')) else ''
    event_name = str(row.get('イベント名', '')) if pd.notnull(row.get('イベント名')) else ''
    start_time = str(row.get('定期開催時刻 (開始)', '')) if pd.notnull(row.get('定期開催時刻 (開始)')) else ''
    organizer_text = str(row.get('主催者', '')) if pd.notnull(row.get('主催者')) else ''
    how_to_join = str(row.get('参加方法', '')) if pd.notnull(row.get('参加方法')) else ''

    # イベントキー（アカウントID, イベント名, 開始時刻でユニーク性を判定）
    event_key = f"{account_id}_{event_name}_{start_time}"

    for day in row['曜日リスト']:
        if day in calendar:
            # すでに同じイベントがその曜日に追加されている場合はスキップ
            if account_id and event_key in day_event_accounts[day]:
                continue

            # この組み合わせを記録
            if account_id:
                day_event_accounts[day].add(event_key)

            info = ''
            # 開始時刻
            if start_time:
                info += f'<span class="time">{start_time}</span> '
            # アカウントID（あればリンク付き）
            if account_id:
                info += f'<a href="https://twitter.com/{account_id}" target="_blank" class="account">@{account_id}</a> '
            # イベント名（アカウントIDがない場合）
            elif event_name:
                 info += f'<strong>{event_name}</strong> '
            # ハッシュタグ
            if pd.notnull(row.get('公式ハッシュタグ')) and str(row['公式ハッシュタグ']).strip():
                info += f'<span class="hashtag">{row["公式ハッシュタグ"]}</span> '
            # ハッシュタグ
            if pd.notnull(row.get('参加方法')) and str(row['参加方法']).strip():
                info += f'<span class="hashtag">{row["参加方法"]}</span> '

            if organizer_text and "@GN001EXIA" not in organizer_text: # "@GN001EXIA" を含む場合は表示しない
                info += f'<span class="organizer">主催: {organizer_text}</span>'

            # infoが空でなければ追加
            if info.strip():
                # ソート用に開始時刻（数値比較可能な形式）を保持
                sort_key = start_time if start_time else '99:99'
                calendar[day].append((sort_key, info))

# 開始時刻順に並べる
for day in calendar:
    # 時刻文字列を 'HH:MM' 形式に正規化してソート
    def normalize_time_for_sort(time_str):
        if not time_str or not isinstance(time_str, str) or time_str == '99:99':
            return '99:99'
        match = re.match(r'(\d{1,2})[:：]?(\d{2})?', time_str)
        if match:
            h, m = match.groups()
            return f"{int(h):02d}:{m if m else '00'}"
        return '99:99' # 不正な形式の場合

    calendar[day].sort(key=lambda x: normalize_time_for_sort(x[0]))
    calendar[day] = [ev[1] for ev in calendar[day]] # info部分のみをリストにする


# HTML生成
html = '''<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VRCイベントカレンダー</title>
    <style>
        body {
            font-family: 'Arial', 'Hiragino Kaku Gothic ProN', sans-serif;
            background-color: #f8f9fa;
            color: #333;
            line-height: 1.6;
            padding: 20px;
            max-width: 1400px; /* 最大幅を設定 */
            margin: 0 auto; /* 中央寄せ */
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
            border-bottom: 2px solid #a29bfe;
            padding-bottom: 5px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            table-layout: fixed; /* テーブルレイアウトを固定 */
        }
        th {
            background-color: #a29bfe;
            color: white;
            padding: 12px 8px; /* パディング調整 */
            text-align: center;
            font-weight: bold;
            border: 1px solid #ddd;
        }
        td {
            background-color: #fff;
            padding: 10px 8px; /* パディング調整 */
            border: 1px solid #ddd;
            vertical-align: top;
            height: 200px; /* セルの高さを固定 */
            overflow-y: auto; /* 内容が多い場合にスクロール */
            word-wrap: break-word; /* 長い単語の折り返し */
        }
        td:nth-child(6) { /* 土曜日 */
            background-color: #e4f0fb;
        }
        td:nth-child(7) { /* 日曜日 */
            background-color: #ffe8f0;
        }
        .event-item {
            padding: 8px 0;
            border-bottom: 1px dashed #ddd;
            margin-bottom: 8px;
        }
        .event-item:last-child {
             border-bottom: none; /* 最後の要素の下線を消す */
        }
        .time {
            font-weight: bold;
            color: #e84393;
            margin-right: 5px;
            white-space: nowrap; /* 時刻が折り返さないように */
        }
        .account, strong { /* イベント名も太字 */
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
            font-size: 0.9em;
            display: inline-block; /* 改行を防ぐ */
            margin-right: 3px; /* ハッシュタグ間の隙間 */
        }
        .organizer {
            color: #6c5ce7;
            font-size: 0.85em; /* 少し小さく */
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
        /* レスポンシブ対応 */
        @media (max-width: 768px) {
            body {
                padding: 10px;
            }
            h1 {
                font-size: 1.5em;
            }
            h2 {
                 font-size: 1.2em;
            }
            table, th, td {
                font-size: 0.9em; /* スマホでは文字を少し小さく */
            }
            th, td {
                padding: 8px 5px;
            }
            td {
                height: 150px; /* スマホでは高さを少し低く */
            }
        }
        @media (max-width: 480px) {
             table, th, td {
                font-size: 0.8em;
             }
             td {
                 height: 120px;
             }
             .hashtag {
                 display: block; /* スマホではハッシュタグを改行させる */
                 margin: 2px 0;
             }
             .organizer {
                 font-size: 0.8em;
             }
        }
    </style>
</head>
<body>
    <h1>VRCイベントカレンダー</h1>
'''

# 定期イベントカレンダーテーブル生成
html += '<h2>定期イベント</h2>'
html += '<table><thead><tr><th>月</th><th>火</th><th>水</th><th>木</th><th>金</th><th>土</th><th>日</th></tr></thead><tbody><tr>'
for day in ['月', '火', '水', '木', '金', '土', '日']:
    html += '<td>'
    if calendar[day]:
        for ev in calendar[day]:
            html += f'<div class="event-item">{ev}</div>'
    else:
        html += '&nbsp;' # イベントがない日は空白を表示
    html += '</td>'
html += '</tr></tbody></table>'


# 不定期イベントリスト生成
# 不定期イベントの重複をチェックするための集合 (キーをより厳密に)
seen_irregular_events = set()

html += '<h2>不定期イベント</h2><ul>'
# account_id と イベント名でソートしてから表示（見やすさのため）
irregular_df_sorted = irregular_df.sort_values(by=['account_id', 'イベント名'], na_position='last')

for _, row in irregular_df_sorted.iterrows():
    # 必要な情報を取得
    account_id = str(row.get('account_id', '')) if pd.notnull(row.get('account_id')) else ''
    event_name = str(row.get('イベント名', '')) if pd.notnull(row.get('イベント名')) else ''
    hashtag = str(row.get('公式ハッシュタグ', '')) if pd.notnull(row.get('公式ハッシュタグ')) else ''
    organizer_text = str(row.get('主催者', '')) if pd.notnull(row.get('主催者')) else ''
    start_time = str(row.get('主催者', '')) if pd.notnull(row.get('定期開催時刻 (開始)')) else ''

    # アカウントIDもイベント名もない場合は表示しない
    if not account_id and not event_name:
        continue
    if not hashtag:
        continue
    if not organizer_text:
        continue

    # 重複チェックキー (アカウントID, イベント名, ハッシュタグで判定)
    event_key = f"{account_id}_{event_name}_{hashtag}"
    if event_key in seen_irregular_events:
        continue

    seen_irregular_events.add(event_key)

    info = '<div>'
    # アカウントID
    if account_id:
        info += f'<a href="https://twitter.com/{account_id}" target="_blank" class="account">@{account_id}</a> '
    # イベント名
    if event_name:
        info += f'<strong>{event_name}</strong> '
    # ハッシュタグ
    if hashtag:
        info += f'<span class="hashtag">{hashtag}</span> '
    # 主催者（特定のアカウントを除く）
    if organizer_text and "@GN001EXIA" not in organizer_text: # "@GN001EXIA" を含む場合は表示しない
        info += f'<span class="organizer">主催: {organizer_text}</span>'
    info += '</div>'
    html += f'<li>{info}</li>'

    if start_time:
        info += f'<span class="hashtag">{start_time}</span> '

html += '</ul>'

# フッター
html += f'''
    <div class="footer">
        <p>最終更新: {datetime.now().strftime("%Y年%m月%d日 %H:%M")}</p>
    </div>
</body>
</html>
'''

# HTMLファイルに書き出し
try:
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("HTMLファイルを生成しました: index.html")
except Exception as e:
    print(f"HTMLファイル書き出しエラー: {e}")

