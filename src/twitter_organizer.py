import pandas as pd
import re
import os
import json
import locale
import unicodedata
from datetime import datetime

# ロケール設定
try:
    locale.setlocale(locale.LC_TIME, 'ja_JP.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'ja_JP.utf8')
    except locale.Error:
        print("警告: 日本語ロケールが設定できませんでした。曜日はデフォルト表記になります。")

# 正規表現パターン
EVENT_START_MARKER = re.compile(r'(?:さて)?(?:今夜|今日)[は、,]?\s*\n?')
TIME_PATTERN = re.compile(r'(\d{1,2}[:：]\d{1,2})(?:\s*[-~～]\s*(\d{1,2}[:：]\d{1,2}))?')
VENUE_PATTERN = re.compile(r'(リクイン|ReqIn|reqin|Join|join|ジョイン)', re.IGNORECASE)
TARGET_PATTERNS = [
    re.compile(r'(.+?)\s*(?:に|へ)\s*(?:リクイン|ReqIn|reqin)', re.IGNORECASE),
    re.compile(r'(.+?)\s*(?:に|へ)\s*(?:Join|join|ジョイン)', re.IGNORECASE),
    re.compile(r'(.+?)\s*(?:リクイン|ReqIn|reqin)', re.IGNORECASE),
    re.compile(r'(.+?)\s*(?:Join|join|ジョイン)', re.IGNORECASE),
]
INVALID_TARGETS = {"il", "グループ", "メンバー", "当日発表のil", "発表のil", "各il"}

def normalize_text(text):
    """文字列を正規化し、改行や余分な空白を削除"""
    if not text or not isinstance(text, str):
        return ""
    text = unicodedata.normalize('NFKC', text)
    text = text.replace('\n', ' ').replace('\r', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def clean_text(text):
    """文字列から印刷不能文字を除去"""
    if isinstance(text, str):
        return ''.join(c for c in text if c.isprintable() or c.isspace())
    return text

def parse_datetime_flexible(date_str):
    """複数の日付形式を試してdatetimeオブジェクトを返す"""
    if pd.isna(date_str):
        return None
    date_str = str(date_str)
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
    ]
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt
    except (ValueError, TypeError):
        for fmt in formats:
            try:
                dt_naive = datetime.strptime(date_str, fmt)
                return dt_naive
            except (ValueError, TypeError):
                continue
    try:
        from dateutil import parser
        return parser.parse(date_str)
    except (ImportError, ValueError, TypeError):
        return None

def extract_event_details_refined(lines):
    """イベント詳細行からイベント名、リクイン先を抽出"""
    event_name = "不明"
    join_destination = "不明"
    event_name_candidates = []
    found_venue_line = False
    
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
        
        venue_found_in_line = False
        if VENUE_PATTERN.search(line_stripped):
            venue_found_in_line = True
        
        extracted_target = ""
        for pattern in TARGET_PATTERNS:
            match = pattern.search(line_stripped)
            if match:
                target_candidate = clean_text(match.group(1).strip())
                if target_candidate and target_candidate.lower() not in INVALID_TARGETS:
                    extracted_target = target_candidate
                    break
        
        if extracted_target:
            join_destination = extracted_target
            found_venue_line = True
        elif join_destination == "不明":
            if not re.match(r"^(IL|グループ|メンバー|当日発表のIL|発表のIL|各IL)\s*(?:に|へ)?\s*(?:リクイン|ReqIn|reqin|Join|join|ジョイン)", line_stripped, re.IGNORECASE):
                join_destination = clean_text(line_stripped)
                found_venue_line = True
        
        if not venue_found_in_line:
            cleaned_candidate = clean_text(line_stripped)
            if cleaned_candidate:
                event_name_candidates.append(cleaned_candidate)
    
    if event_name_candidates:
        event_name = event_name_candidates[0]
    elif not event_name_candidates and join_destination != "不明" and not VENUE_PATTERN.search(join_destination):
        event_name = join_destination
    
    # 相互補完
    if event_name == "不明" and join_destination != "不明":
        event_name = join_destination
    elif join_destination == "不明" and event_name != "不明":
        join_destination = event_name
    
    return event_name, join_destination

def extract_vrc_events_from_tweet(tweet_text, tweet_date_str):
    """1つのツイートから複数のイベント情報を抽出"""
    tweet_datetime = parse_datetime_flexible(tweet_date_str)
    if not tweet_datetime:
        return []
    
    tweet_date_part = tweet_datetime.strftime("%Y-%m-%d")
    try:
        weekday_jp = tweet_datetime.strftime('%a')
    except Exception:
        weekday_jp = "不明"
    
    events = []
    event_block_start = 0
    
    marker_match = EVENT_START_MARKER.search(tweet_text)
    if marker_match:
        event_block_start = marker_match.end()
    elif not TIME_PATTERN.search(tweet_text[:50]):
        first_time_match = TIME_PATTERN.search(tweet_text)
        if first_time_match:
            prev_newline = tweet_text.rfind('\n', 0, first_time_match.start())
            event_block_start = prev_newline + 1 if prev_newline != -1 else 0
        else:
            return []
    
    event_section = tweet_text[event_block_start:]
    time_matches = list(TIME_PATTERN.finditer(event_section))
    
    for i, match in enumerate(time_matches):
        start_time_str = match.group(1).replace('：', ':')
        detail_start = match.end()
        detail_end = time_matches[i + 1].start() if i + 1 < len(time_matches) else len(event_section)
        detail_text = event_section[detail_start:detail_end].strip()
        
        if not detail_text:
            continue
        
        lines = detail_text.split('\n')
        event_name, join_destination = extract_event_details_refined(lines)
        
        if event_name == "不明" and join_destination == "不明":
            continue
        
        start_datetime_full = None
        try:
            hour, minute = map(int, start_time_str.split(':'))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                start_dt_obj = datetime.strptime(f"{tweet_date_part} {start_time_str}", "%Y-%m-%d %H:%M")
                start_datetime_full = start_dt_obj.strftime("%Y-%m-%d %H:%M:%S")
            else:
                continue
        except ValueError:
            continue
        
        events.append({
            'イベント名': event_name,
            '開催日時スタート': start_datetime_full,
            '曜日': weekday_jp,
            'リクイン先': join_destination,
            '引用元ツイート全文': tweet_text
        })
    
    return events

def extract_hashtags(text):
    """テキストからハッシュタグを抽出"""
    text = normalize_text(text)
    hashtags = re.findall(r'#([A-Za-z0-9_一-龥ぁ-んァ-ンー]+)', text)
    hashtags = [f"#{h}" for h in hashtags if len(h) > 2]
    return hashtags

def extract_group_ids(text):
    """テキストからVRCグループIDを抽出"""
    text = normalize_text(text)
    group_ids = re.findall(r'vrc\.group/([A-Za-z0-9._-]+)', text)
    return group_ids

def extract_weekdays_from_date(date_str):
    """日付から曜日を抽出"""
    dt = parse_datetime_flexible(date_str)
    if dt:
        try:
            return dt.strftime('%a')
        except:
            pass
    return ""

def extract_times_from_event(event_dict):
    """イベント情報から時間を抽出"""
    if '開催日時スタート' in event_dict and event_dict['開催日時スタート']:
        dt = parse_datetime_flexible(event_dict['開催日時スタート'])
        if dt:
            return dt.strftime('%H:%M'), ""
    return "", ""

def process_files(csv_path, json_path=None):
    """CSVとJSONを処理し、イベントDataFrameを返す"""
    df_csv = pd.DataFrame()
    df_json = pd.DataFrame()
    
    # CSVファイルの読み込み
    try:
        df_csv = pd.read_csv(csv_path, dtype={'id': str}, encoding='utf-8')
        print(f"CSV読み込み完了: {len(df_csv)}行")
    except Exception as e:
        print(f"CSV読み込み中のエラー: {e}")
        return pd.DataFrame()
    
    # JSONファイルの読み込み（存在する場合）
    if json_path and os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8', errors='replace') as f:
                json_data = json.load(f)
            if isinstance(json_data, list):
                df_json = pd.DataFrame(json_data)
            elif isinstance(json_data, dict):
                df_json = pd.DataFrame([json_data])
            
            if not df_json.empty and 'id' in df_json.columns:
                df_json['id'] = df_json['id'].astype(str)
            print(f"JSON読み込み完了: {len(df_json)}行")
        except Exception as e:
            print(f"JSON読み込み中のエラー: {e}")
    
    # データのマージ
    df = df_csv
    if not df_json.empty and 'id' in df_json.columns and 'id' in df_csv.columns:
        df = pd.merge(df_csv, df_json, on='id', how='outer', suffixes=('_csv', '_json'))
        
        for col_base in ['username', 'text', 'date']:
            col_csv, col_json = f'{col_base}_csv', f'{col_base}_json'
            if col_json in df.columns and col_csv in df.columns:
                df[col_base] = df[col_json].fillna(df[col_csv])
                df.drop(columns=[col_csv, col_json], inplace=True, errors='ignore')
            elif col_json in df.columns:
                df.rename(columns={col_json: col_base}, inplace=True)
            elif col_csv in df.columns:
                df.rename(columns={col_csv: col_base}, inplace=True)
        print(f"マージ後のデータ: {len(df)}行")
    
    # イベント抽出処理
    all_events = []
    required_columns = ['id', 'text', 'date']
    if not all(col in df.columns for col in required_columns):
        print(f"エラー: 必要な列 {required_columns} がDataFrameにありません。")
        return pd.DataFrame()
    
    for row in df.itertuples(index=False):
        tweet_id, tweet_text, tweet_date_str = getattr(row, 'id', ''), getattr(row, 'text', ''), getattr(row, 'date', None)
        
        if tweet_text and tweet_date_str:
            try:
                extracted = extract_vrc_events_from_tweet(tweet_text, tweet_date_str)
                if extracted:
                    for event in extracted:
                        event['tweet_id_source'] = tweet_id
                        # ハッシュタグとグループIDを抽出
                        event['公式ハッシュタグ'] = " ".join(extract_hashtags(tweet_text))
                        event['グループID'] = " ".join(extract_group_ids(tweet_text))
                    all_events.extend(extracted)
            except Exception as e:
                print(f"警告: ツイートID {tweet_id} 処理中にエラー: {e}")
    
    if not all_events:
        print("抽出されたイベントはありませんでした。")
        return pd.DataFrame()
    
    # twitter_list_organizer.pyの出力形式に合わせる
    result_df = pd.DataFrame(all_events)
    
    # 列名の変換
    result_df = result_df.rename(columns={
        '開催日時スタート': '定期開催時刻 (開始)',
        'リクイン先': '参加詳細/リクイン先',
        '曜日': '開催曜日'
    })
    
    # 必要な列を追加
    for col in ['定期開催時刻 (終了)', '開催頻度', '参加方法', '主催者']:
        if col not in result_df.columns:
            result_df[col] = ""
    
    # 最終的な列順序
    final_columns = [
        'イベント名', '公式ハッシュタグ', 'グループID', '主催者', '参加詳細/リクイン先', 
        '参加方法', '開催頻度', '開催曜日', '定期開催時刻 (開始)', '定期開催時刻 (終了)',
        '引用元ツイート全文', 'tweet_id_source'
    ]
    
    # 存在する列のみを選択
    output_columns = [col for col in final_columns if col in result_df.columns]
    result_df = result_df[output_columns]
    
    return result_df

def organize_tweets(input_csv, output_csv):
    """ツイートからイベント情報を抽出し、整形して保存"""
    # JSONファイルパスを推測（同じ名前で拡張子だけ違う）
    json_path = input_csv.replace('.csv', '.json')
    if not os.path.exists(json_path):
        json_path = None
    
    # ファイル処理
    events_df = process_files(input_csv, json_path)
    
    if not events_df.empty:
        try:
            events_df.to_csv(output_csv, index=False, encoding='utf-8-sig', errors='replace')
            print(f"抽出結果を保存しました: {output_csv}")
            return events_df
        except Exception as e:
            print(f"ファイル保存エラー: {e}")
    
    return pd.DataFrame()

if __name__ == "__main__":
    input_dir = "twitter_data"
    if not os.path.exists(input_dir):
        os.makedirs(input_dir, exist_ok=True)
        print(f"ディレクトリを作成しました: {input_dir}")
    
    # 最新のresultsファイルを探す
    files = sorted([f for f in os.listdir(input_dir) if f.startswith("results_") and f.endswith(".csv")])
    
    if not files:
        print(f"{input_dir} 内に入力ファイル (results_*.csv) が見つかりません")
        exit(1)
    
    latest_file = files[-1]
    input_csv = os.path.join(input_dir, latest_file)
    print(f"入力ファイル: {input_csv}")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_csv = os.path.join(input_dir, f"events_organized_{timestamp}.csv")
    
    organize_tweets(input_csv, output_csv)
