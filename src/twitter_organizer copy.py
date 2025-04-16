import pandas as pd
import re
from datetime import datetime
import json
import os
import locale

# --- ロケール設定 ---
try:
    # 日本語環境に適したロケールを設定 (曜日表示用)
    # Windows: 'ja_JP.UTF-8' or 'Japanese_Japan.932'
    # Linux/macOS: 'ja_JP.UTF-8' or 'ja_JP.utf8'
    locale.setlocale(locale.LC_TIME, 'ja_JP.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'ja_JP.utf8')
    except locale.Error:
        print("警告: 日本語ロケールが設定できませんでした。曜日はデフォルト表記になります。")

# --- 正規表現パターン ---
EVENT_START_MARKER = re.compile(r'(?:さて)?(?:今夜|今日)[は、,]?\s*\n?')
TIME_PATTERN = re.compile(r'(\d{1,2}[:：]\d{1,2})(?:\s*[-~～]\s*(\d{1,2}[:：]\d{1,2}))?')
VENUE_PATTERN = re.compile(r'(リクイン|ReqIn|reqin|Join|join|ジョイン)', re.IGNORECASE)
TARGET_PATTERNS = [
    re.compile(r'(.+?)\s*(?:に|へ)\s*(?:リクイン|ReqIn|reqin)', re.IGNORECASE),
    re.compile(r'(.+?)\s*(?:に|へ)\s*(?:Join|join|ジョイン)', re.IGNORECASE),
    re.compile(r'(.+?)\s*(?:リクイン|ReqIn|reqin)', re.IGNORECASE), # スペースなし対応
    re.compile(r'(.+?)\s*(?:Join|join|ジョイン)', re.IGNORECASE),   # スペースなし対応
]
INVALID_TARGETS = {"il", "グループ", "メンバー", "当日発表のil", "発表のil", "各il"}

def clean_text(text):
    """文字列から印刷不能文字やサロゲート文字を除去"""
    if isinstance(text, str):
        # サロゲートペアを考慮しつつ、印刷可能文字と空白のみを残す
        # (より高度なクリーニングが必要な場合はunicodedataなどを検討)
        return ''.join(c for c in text if c.isprintable() or c.isspace())
    return text

def parse_datetime_flexible(date_str):
    """複数の日付形式を試してdatetimeオブジェクトを返す"""
    if pd.isna(date_str): return None
    date_str = str(date_str)
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ", # ISO 8601 with milliseconds and Z
        "%Y-%m-%dT%H:%M:%SZ",    # ISO 8601 without milliseconds and Z
        "%Y-%m-%d %H:%M:%S%z",   # Includes timezone offset like +00:00
        "%Y-%m-%d %H:%M:%S",     # Naive datetime
    ]
    for fmt in formats:
        try:
            # タイムゾーン情報があればそれを尊重し、なければNaiveとしてパース
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt
        except (ValueError, TypeError):
            try:
                 dt_naive = datetime.strptime(date_str, fmt)
                 return dt_naive
            except (ValueError, TypeError):
                 continue
    try:
        # Fallback using dateutil if installed
        from dateutil import parser
        return parser.parse(date_str)
    except (ImportError, ValueError, TypeError):
        # print(f"警告: 解析できない日付形式: {date_str}")
        return None

def extract_event_details_refined(lines):
    """イベント詳細行からイベント名、リクイン先を抽出"""
    event_name = "不明"
    join_destination = "不明"
    event_name_candidates = []
    found_venue_line = False

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped: continue

        venue_found_in_line = False
        if VENUE_PATTERN.search(line_stripped):
            venue_found_in_line = True
            extracted_target = ""
            for pattern in TARGET_PATTERNS:
                match = pattern.search(line_stripped)
                if match:
                    target_candidate = clean_text(match.group(1).strip()) # クリーニング
                    if target_candidate and target_candidate.lower() not in INVALID_TARGETS:
                        extracted_target = target_candidate
                        break
            if extracted_target:
                join_destination = extracted_target
                found_venue_line = True
            elif join_destination == "不明": # Generic line check
                 if not re.match(r"^(IL|グループ|メンバー|当日発表のIL|発表のIL|各IL)\s*(?:に|へ)?\s*(?:リクイン|ReqIn|reqin|Join|join|ジョイン)", line_stripped, re.IGNORECASE):
                    join_destination = clean_text(line_stripped) # Fallback + クリーニング
                    found_venue_line = True

        if not venue_found_in_line:
            cleaned_candidate = clean_text(line_stripped) # クリーニング
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
    if not tweet_datetime: return []

    tweet_date_part = tweet_datetime.strftime("%Y-%m-%d")
    try:
        weekday_jp = tweet_datetime.strftime('%a') # ロケール依存の曜日
    except Exception:
        weekday_jp = "不明"

    events = []
    event_block_start = 0
    marker_match = EVENT_START_MARKER.search(tweet_text)
    if marker_match:
        event_block_start = marker_match.end()
    elif not TIME_PATTERN.search(tweet_text[:50]): # ツイート冒頭に時刻がない場合のみ
        first_time_match = TIME_PATTERN.search(tweet_text)
        if first_time_match:
            prev_newline = tweet_text.rfind('\n', 0, first_time_match.start())
            event_block_start = prev_newline + 1 if prev_newline != -1 else 0
        else:
            return [] # イベント情報なし

    event_section = tweet_text[event_block_start:]
    time_matches = list(TIME_PATTERN.finditer(event_section))

    for i, match in enumerate(time_matches):
        start_time_str = match.group(1).replace('：', ':')
        detail_start = match.end()
        detail_end = time_matches[i + 1].start() if i + 1 < len(time_matches) else len(event_section)
        detail_text = event_section[detail_start:detail_end].strip()

        if not detail_text: continue

        lines = detail_text.split('\n')
        event_name, join_destination = extract_event_details_refined(lines)

        # イベント名とリクイン先が両方不明の場合はスキップ
        if event_name == "不明" and join_destination == "不明":
            continue

        start_datetime_full = None
        try:
            # 時刻文字列の検証を追加 (例: HHが23以下、MMが59以下)
            hour, minute = map(int, start_time_str.split(':'))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                start_dt_obj = datetime.strptime(f"{tweet_date_part} {start_time_str}", "%Y-%m-%d %H:%M")
                start_datetime_full = start_dt_obj.strftime("%Y-%m-%d %H:%M:%S")
            else:
                # print(f"警告: 不正な時刻形式: {start_time_str}")
                continue # 不正な時刻はスキップ
        except ValueError:
            # print(f"警告: 時刻パースエラー: {start_time_str}")
            continue # パースエラーもスキップ

        events.append({
            'イベント名': event_name,
            '開催日時スタート': start_datetime_full,
            '曜日': weekday_jp,
            'リクイン先': join_destination,
            '引用元ツイート全文': tweet_text # 元のツイートはクリーニングしない
        })
    return events

def process_files(csv_path, json_path):
    """CSVとJSONを処理し、イベントDataFrameを返す"""
    df_csv, df_json = pd.DataFrame(), pd.DataFrame()
    try:
        # errors='replace' で読み込みエラーを回避
        df_csv = pd.read_csv(csv_path, dtype={'id': str}, encoding='utf-8', errors='replace')
        print(f"CSV読み込み完了: {len(df_csv)}行")
    except FileNotFoundError:
        print(f"警告: CSVファイルが見つかりません: {csv_path}")
    except Exception as e:
        print(f"CSV読み込み中の警告: {e}")

    try:
        # errors='replace' で読み込みエラーを回避
        with open(json_path, 'r', encoding='utf-8', errors='replace') as f:
            json_data = json.load(f)
        if isinstance(json_data, list): df_json = pd.DataFrame(json_data)
        elif isinstance(json_data, dict): df_json = pd.DataFrame([json_data])
        if not df_json.empty and 'id' in df_json.columns:
            df_json['id'] = df_json['id'].astype(str)
            print(f"JSON読み込み完了: {len(df_json)}行")
        else: df_json = pd.DataFrame()
    except FileNotFoundError:
         print(f"警告: JSONファイルが見つかりません: {json_path}")
    except Exception as e:
        print(f"JSON読み込み中の警告: {e}")

    # --- データのマージ ---
    if not df_csv.empty and not df_json.empty and 'id' in df_csv.columns and 'id' in df_json.columns:
        df = pd.merge(df_csv, df_json, on='id', how='outer', suffixes=('_csv', '_json'))
        # 列の統合
        for col_base in ['username', 'text', 'date']: # 必要に応じて他の列も追加
             col_csv, col_json = f'{col_base}_csv', f'{col_base}_json'
             if col_json in df.columns and col_csv in df.columns:
                  df[col_base] = df[col_json].fillna(df[col_csv])
                  df.drop(columns=[col_csv, col_json], inplace=True, errors='ignore')
             elif col_json in df.columns: df.rename(columns={col_json: col_base}, inplace=True)
             elif col_csv in df.columns: df.rename(columns={col_csv: col_base}, inplace=True)
        print(f"マージ後のデータ: {len(df)}行")
    elif not df_csv.empty:
        df = df_csv
    elif not df_json.empty:
        df = df_json
    else:
        print("エラー: 有効なデータソースがありません。")
        return pd.DataFrame() # 空のDataFrame

    # --- イベント抽出処理 ---
    all_events = []
    required_columns = ['id', 'text', 'date']
    if not all(col in df.columns for col in required_columns):
         print(f"エラー: 必要な列 {required_columns} がDataFrameにありません。")
         return pd.DataFrame()

    for row in df.itertuples(index=False):
        tweet_id, tweet_text, tweet_date_str = getattr(row, 'id', ''), getattr(row, 'text', ''), getattr(row, 'date', None)
        # text と date が有効な場合のみ処理
        if tweet_text and tweet_date_str:
            try:
                # 抽出前にテキストをクリーニングするか検討 (今回は抽出関数内で実施)
                extracted = extract_vrc_events_from_tweet(tweet_text, tweet_date_str)
                if extracted:
                    for event in extracted: event['tweet_id_source'] = tweet_id
                    all_events.extend(extracted)
            except Exception as e:
                # 個別ツイートのエラーは警告として処理を続ける
                print(f"警告: ツイートID {tweet_id} 処理中に予期せぬエラー: {e}")

    if not all_events:
        print("抽出されたイベントはありませんでした。")
        return pd.DataFrame()

    # --- DataFrame整形と最終クリーニング ---
    final_columns = ['イベント名', '開催日時スタート', '曜日', 'リクイン先', '引用元ツイート全文', 'tweet_id_source']
    result_df = pd.DataFrame(all_events)
    # 不足している列があればNaNで追加
    for col in final_columns:
         if col not in result_df.columns: result_df[col] = None
    # 抽出結果のテキスト列を再度クリーニング (念のため)
    for col in ['イベント名', 'リクイン先']: # 引用元ツイートは変更しない
         if col in result_df.columns:
             result_df[col] = result_df[col].apply(clean_text)

    return result_df[final_columns] # 列順序を整えて返す

# --- メイン実行ブロック ---
if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # ファイルパスを修正: スクリプトの場所基準で "../twitter_data/" を参照しない
    # 正しいファイルがスクリプトと同じディレクトリにあると仮定
    csv_filename = "results_20250414_212538.csv"
    json_filename = "results_20250414_212538.json"
    output_filename = 'vrc_events_extracted_fixed.csv'

    csv_path = os.path.join(script_dir, "../twitter_data/" + csv_filename)
    json_path = os.path.join(script_dir, "../twitter_data/" + json_filename)
    output_path = os.path.join(script_dir, output_filename)

    if os.path.exists(csv_path) and os.path.exists(json_path):
        events_df = process_files(csv_path, json_path)
        if not events_df.empty:
            try:
                # errors='replace' で書き込みエラーを回避
                events_df.to_csv(output_path, index=False, encoding='utf-8-sig', errors='replace')
                print(f"抽出結果が正常に保存されました: {output_path}")
            except Exception as e:
                print(f"ファイル保存エラー: {e}")
        # else のメッセージは process_files 内で出力されるので不要
    else:
        # エラーメッセージをより具体的に
        missing_files = []
        if not os.path.exists(csv_path): missing_files.append(csv_filename)
        if not os.path.exists(json_path): missing_files.append(json_filename)
        print(f"エラー: 入力ファイルが見つかりません: {', '.join(missing_files)}")
