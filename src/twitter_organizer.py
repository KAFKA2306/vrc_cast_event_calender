import re
import json
import unicodedata
from datetime import datetime, timedelta
import pandas as pd

EVENT_START_MARKER = re.compile(r'(?:さて)?(?:今夜|今日)[は、]?\s*\n?')
TIME_PATTERN = re.compile(r'(\d{1,2})\s*[:：時]\s*(\d{1,2})?(?:\s*分)?(?:\s*[-~～〜]\s*(\d{1,2})\s*[:：時]\s*(\d{1,2})?(?:\s*分)?)?')
EVENT_NAME_BRACKETS = re.compile(r'[「『【]([^」』】]+)[」』】]')
HASHTAG_PATTERN = re.compile(r'#([A-Za-z0-9_一-龥ぁ-んァ-ンー]+)')
PARTICIPATION_KEYWORDS = [
    r'リクイン', r'ReqIn', r'reqin', r'Join', r'join', r'JOIN', r'ジョイン', r'グループ', r'Group', r'Group\+', r'メンバー',
    r'抽選', r'応募', r'予約', r'事前', r'当日枠', r'初回', r'限定', r'フレ(?:ンド)?(?:申請|\+|リク)', r'発表', r'IL', r'インスタンス', r'ins'
]
PARTICIPATION_PATTERN = re.compile(r'(' + '|'.join(PARTICIPATION_KEYWORDS) + r')', re.IGNORECASE)
VRC_GROUP_ID_PATTERN = re.compile(r'vrc\.group/([A-Za-z0-9._-]+)', re.IGNORECASE)
VRC_USER_ID_PATTERN = re.compile(r'(?:[＠@]|ID:?\s*)?([a-zA-Z0-9_.-]{3,32})')
TARGET_PATTERNS = [
    re.compile(r'(?:リクイン|ReqIn|reqin|Join|join|ジョイン)\s*(?:先|方法|は|へ|に)[:：]?\s*\"?([a-zA-Z0-9_.-]+)\"?', re.IGNORECASE),
    re.compile(r'([a-zA-Z0-9_.-]+)\s*(?:さん|様)?\s*(?:に|へ)\s*(?:リクイン|ReqIn|reqin|Join|join|ジョイン)', re.IGNORECASE),
    re.compile(r'第\d\s*(?:ins|インスタンス)[:：]?\s*([a-zA-Z0-9_.-]+)', re.IGNORECASE),
    re.compile(r'(?:グループ|Group)\+?\s*(?:に|へ)?\s*(?:Join|join|JOIN)', re.IGNORECASE),
    re.compile(r'(?:IL|インスタンス|ins)(?:\s*[:：]\s*([a-zA-Z0-9_.-]+)|\s*(?:に|へ))', re.IGNORECASE),
    re.compile(r'(?:当日|後日|別途|改めて)発表(?:のIL)?', re.IGNORECASE),
    re.compile(r'(?:抽選|予約|応募)', re.IGNORECASE),
    re.compile(r'(フレ(?:ンド)?(?:申請|\+|リク))', re.IGNORECASE),
    re.compile(r'([a-zA-Z0-9_.-]{3,32})\s*(?:へ|に)$', re.IGNORECASE)
]
INVALID_TARGETS = {"il", "グループ", "メンバー", "当日発表のil", "発表のil", "各il", "代表", "リクイン", "join", "reqin",
                   "twitter", "com", "http", "https", "youtube", "booth", "fanbox", "vrc", "vrchat", "info", "official", "event", "news", "bot"}

def extract_participation_method_enhanced(text):
    methods = set()
    normalized_text = normalize_text(text)
    found_keywords = PARTICIPATION_PATTERN.findall(normalized_text)
    methods.update(kw.strip().lower() for kw in found_keywords)
    final_methods = set()
    if any(m in ['リクイン', 'reqin'] for m in methods): final_methods.add('リクイン')
    if any(m in ['join', 'ジョイン'] for m in methods): final_methods.add('Join')
    if any(m in ['グループ', 'group', 'group+'] for m in methods):
        if '+join' in normalized_text.lower() or 'グループ+にjoin' in normalized_text.lower():
            final_methods.add('Group+ Join')
        else: final_methods.add('Group Join')
    if any(m in ['抽選', '応募', '予約', '事前'] for m in methods): final_methods.add('抽選/予約等')
    if any(m in ['フレ申請', 'フレリク', 'フレンド申請', 'フレンド+', 'フレ+'] for m in methods): final_methods.add('フレンド申請')
    if '当日枠' in methods: final_methods.add('当日枠')
    if '初回' in methods: final_methods.add('初回限定')
    if '限定' in methods and '初回' not in methods: final_methods.add('限定')
    if '抽選/予約等' in final_methods and 'Join' in final_methods and 'discord' in normalized_text.lower():
        final_methods.discard('抽選/予約等')
        final_methods.discard('Join')
        final_methods.add('Discord抽選+Join')
    if 'Group+ Join' in final_methods: final_methods.discard('Group Join')
    if 'Discord抽選+Join' in final_methods:
        final_methods.discard('Join')
        final_methods.discard('抽選/予約等')
    return '・'.join(sorted(list(final_methods))) if final_methods else ""

def extract_participation_details_enhanced(text):
    details = set()
    normalized_text = normalize_text(text)
    for pattern in TARGET_PATTERNS:
        matches = pattern.finditer(normalized_text)
        for match in matches:
            groups = match.groups()
            target = ""
            if groups:
                valid_groups = [g for g in groups if g is not None]
                if valid_groups:
                    target = valid_groups[-1].strip().strip('"').strip("'").strip("｣")
            if not target and match.group(0).lower() in ['ilに', 'ilへ', 'インスタンスに', 'インスタンスへ']:
                target = "IL/インスタンス"
            elif not target and match.group(0).lower() in ['当日発表', '当日発表のil']:
                target = "当日発表"
            elif not target and match.group(0).lower() in ['抽選', '予約', '応募']:
                target = "抽選/予約等"
            elif not target and match.group(0).lower().startswith(('フレンド申請', 'フレリク', 'フレ+')):
                target = "フレンド申請"
            if target and target.lower() not in INVALID_TARGETS and len(target) > 1:
                vrc_id_match = VRC_USER_ID_PATTERN.search(target)
                clean_target = vrc_id_match.group(1) if vrc_id_match else target
                if clean_target and clean_target.lower() not in INVALID_TARGETS:
                    details.add(clean_target)
    return ' | '.join(sorted(list(details))) if details else ""

def extract_hashtags(text):
    if not isinstance(text, str): return []
    hashtags = HASHTAG_PATTERN.findall(text)
    valid_hashtags = [f"#{h}" for h in hashtags if len(h) > 1 and not re.match(r'^[.\d-]+$', h) and 'http' not in h.lower()]
    return list(set(valid_hashtags))

def normalize_text(text):
    if not text or not isinstance(text, str): return ""
    text = unicodedata.normalize('NFKC', text)
    return text

def clean_text(text):
    if isinstance(text, str):
        cleaned = ''.join(c for c in text if c.isprintable() or c in ('\n', '\t'))
        return cleaned.strip()
    return ""

def parse_datetime_flexible(date_str):
    if not date_str: return None
    date_str = str(date_str)
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S"
    ]
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt
    except (ValueError, TypeError):
        for fmt in formats:
            try: return datetime.strptime(date_str, fmt)
            except (ValueError, TypeError): continue
    try:
        from dateutil import parser
        return parser.parse(date_str)
    except Exception: return None

def extract_event_name_enhanced(text_lines, hashtags):
    potential_names = []
    for line in text_lines:
        matches = EVENT_NAME_BRACKETS.findall(line)
        for name in matches:
            name = name.strip()
            if name and len(name) > 1 and not name.startswith(('#', '@', 'http')) and len(name.split()) < 7:
                potential_names.append(name)
    for i, line in enumerate(text_lines):
        if TIME_PATTERN.search(line):
            if i > 0 and text_lines[i-1].strip():
                prev_line = text_lines[i-1].strip()
                if len(prev_line) > 2 and len(prev_line) < 40 and not prev_line.startswith(('#', '@', 'http', '第', '(', '[')):
                    potential_names.append(prev_line)
            right = TIME_PATTERN.split(line)
            if len(right) > 2:
                after = right[-1].strip()
                if after and len(after) > 2 and len(after) < 40 and not after.startswith(('#', '@', 'http', '第', '(', '[')):
                    potential_names.append(after)
    if hashtags:
        for tag in hashtags:
            tag_body = tag[1:]
            if len(tag_body) < 25 and (re.search(r'[ぁ-んァ-ン一-龥]', tag_body) or tag_body.upper() != tag_body):
                potential_names.append(tag)
    cleaned = []
    for p in potential_names:
        if p.lower() in ["イベント", "event"]:
            continue
        if re.fullmatch(r'[a-zA-Z0-9_.-]{3,32}', p):
            continue
        if any(x in p for x in ["リクイン", "Join", "抽選", "限定", "参加方法", "当日発表", "フレンド", "IL", "インスタンス", "グループ", "初回"]):
            continue
        cleaned.append(p)
    if cleaned:
        cleaned.sort(key=lambda x: -len(x))
        return cleaned[0]
    return "不明"

def extract_vrc_events_from_tweet_enhanced(tweet_id, tweet_text, tweet_date_str, username):
    tweet_datetime = parse_datetime_flexible(tweet_date_str)
    if not tweet_datetime or not tweet_text: return []
    tweet_date_part = tweet_datetime.strftime("%Y-%m-%d")
    cleaned_text = clean_text(tweet_text)
    events = []
    event_block_start_index = 0
    marker_match = EVENT_START_MARKER.search(cleaned_text)
    if marker_match:
        remaining_text = cleaned_text[marker_match.end():]
        first_line_match = re.search(r'\S', remaining_text)
        if first_line_match: event_block_start_index = marker_match.end() + first_line_match.start()
    else:
        first_time_match = TIME_PATTERN.search(cleaned_text)
        if first_time_match and first_time_match.start() > 50:
            prev_newline = cleaned_text.rfind('\n', 0, first_time_match.start())
            event_block_start_index = prev_newline + 1 if prev_newline != -1 else 0
        elif not first_time_match: return []
    event_section = cleaned_text[event_block_start_index:]
    time_matches = list(TIME_PATTERN.finditer(event_section))
    hashtags = extract_hashtags(cleaned_text)
    for i, match in enumerate(time_matches):
        start_hour, start_minute, end_hour, end_minute = match.groups()
        start_time_str = f"{int(start_hour):02d}:{int(start_minute):02d}" if start_minute else f"{int(start_hour):02d}:00"
        end_time_str = ""
        if end_hour:
            end_time_str = f"{int(end_hour):02d}:{int(end_minute):02d}" if end_minute else f"{int(end_hour):02d}:00"
        detail_start = match.end()
        detail_end = time_matches[i + 1].start() if i + 1 < len(time_matches) else len(event_section)
        detail_text_block = event_section[detail_start:detail_end].strip()
        if not detail_text_block: continue
        detail_lines = detail_text_block.split('\n')
        cleaned_detail_lines = [clean_text(line) for line in detail_lines if clean_text(line)]
        if not cleaned_detail_lines: continue
        event_name = extract_event_name_enhanced(cleaned_detail_lines, hashtags)
        participation_method = extract_participation_method_enhanced(detail_text_block)
        participation_details = extract_participation_details_enhanced(detail_text_block)
        start_datetime_full, end_datetime_full = "", ""
        try:
            start_dt_obj = datetime.strptime(f"{tweet_date_part} {start_time_str}", "%Y-%m-%d %H:%M")
            start_datetime_full = start_dt_obj.strftime("%Y-%m-%d %H:%M:%S")
            if end_time_str:
                end_dt_obj = datetime.strptime(f"{tweet_date_part} {end_time_str}", "%Y-%m-%d %H:%M")
                if end_dt_obj < start_dt_obj:
                    end_dt_obj += timedelta(days=1)
                end_datetime_full = end_dt_obj.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError: continue
        if event_name == "不明" and not participation_details: continue
        events.append({
            'イベント名': event_name,
            '公式ハッシュタグ': " ".join(hashtags),
            '参加詳細/リクイン先': participation_details,
            '参加方法': participation_method,
            '定期開催時刻 (開始)': start_time_str,
            '定期開催時刻 (終了)': end_time_str,
            '開催日時スタート': start_datetime_full,
            '開催日時エンド': end_datetime_full,
            '引用元ツイート全文': cleaned_text,
            'tweet_id_source': tweet_id,
        })
    return events

def process_json_to_csv(input_json_path, output_csv_path):
    with open(input_json_path, encoding='utf-8') as f:
        data = json.load(f)
    all_events = []
    for row in data:
        tweet_id = row.get('id') or row.get('tweet_id_source')
        tweet_text = row.get('text') or row.get('引用元ツイート全文')
        tweet_date = row.get('date') or row.get('開催日時スタート')
        username = row.get('username', '')
        if not tweet_id or not tweet_text or not tweet_date:
            continue
        events = extract_vrc_events_from_tweet_enhanced(tweet_id, tweet_text, tweet_date, username)
        if events:
            all_events.extend(events)
    if not all_events:
        print("イベント抽出結果なし")
        return
    df = pd.DataFrame(all_events)
    # CSV出力カラム順
    columns = [
        'イベント名', '公式ハッシュタグ', '参加詳細/リクイン先', '参加方法',
        '定期開催時刻 (開始)', '定期開催時刻 (終了)', '開催日時スタート', '開催日時エンド',
        '引用元ツイート全文', 'tweet_id_source'
    ]
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    df = df[columns]
    df.to_csv(output_csv_path, index=False, encoding='utf-8-sig')
    print(f"保存完了: {output_csv_path}")

if __name__ == "__main__":
    process_json_to_csv("twitter_data/combined_twitter_data_20250416_194247.json", "events_extracted.csv")
