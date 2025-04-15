import pandas as pd
import re
import os
import unicodedata
from datetime import datetime

def normalize_text(text):
    if not text or not isinstance(text, str):
        return ""
    text = unicodedata.normalize('NFKC', text)
    text = text.replace('\n', ' ').replace('\r', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def get_candidate_texts(row):
    texts = []
    for col in ['profile', '固定ツイート', '最新ツイート']:
        if col in row and pd.notnull(row[col]):
            texts.append(str(row[col]))
    return texts

def extract_event_name(text, account_id, hashtags):
    keywords = ['Cafe', 'Bar', 'Club', 'イベント', '集会', '喫茶', 'サロン', 'Party', 'Lounge', 'Host', 'メイド', '執事', '酒場']
    EVENT_NAME_PATTERN = re.compile(r'[「『【]([^」』】]+)[」』】]')
    matches = EVENT_NAME_PATTERN.findall(text)
    for name in matches:
        name = name.strip()
        if name and len(name) > 1 and not name.startswith('#') and not name.startswith('@') and 'http' not in name and len(name.split()) < 6:
            return name
    if hashtags:
        return hashtags[0]
    if account_id and any(kw in account_id for kw in keywords):
        if not re.match(r'^(VRC|EVENT|INFO)', account_id, re.IGNORECASE) and (len(account_id.split('_')) > 1 or len(account_id) > 5):
            return account_id.strip()
    return ""

def extract_times(text):
    text = normalize_text(text)
    kanji_map = {'一': '1', '二': '2', '三': '3', '四': '4', '五': '5', '六': '6', '七': '7', '八': '8', '九': '9'}
    for k, v in kanji_map.items():
        text = text.replace(k, v)
    time_range = re.search(r'(\d{1,2})[:：時](\d{2})?\s*[~〜\-]\s*(\d{1,2})[:：時](\d{2})?', text)
    if time_range:
        sh, sm, eh, em = time_range.groups()
        start = f"{int(sh):02d}:{sm if sm else '00'}"
        end = f"{int(eh):02d}:{em if em else '00'}"
        return start, end
    time_single = re.search(r'(\d{1,2})[:：時](\d{2})?', text)
    if time_single:
        h, m = time_single.groups()
        return f"{int(h):02d}:{m if m else '00'}", ""
    return "", ""

def extract_weekdays(text):
    text = normalize_text(text)
    days = re.findall(r'(月|火|水|木|金|土|日)曜', text)
    if days:
        return '・'.join(days)
    if '週末' in text:
        return '週末'
    if '平日' in text:
        return '平日'
    return ""

def extract_frequency(text):
    text = normalize_text(text)
    freq = re.search(r'(毎週|隔週|毎月|月\d回|年\d回|不定期|第\d|週\d回|週末|平日)', text)
    if freq:
        return freq.group(1)
    return ""

def extract_participation_method(text):
    text = normalize_text(text)
    methods = re.findall(r'(リクイン|ReqInvite|RequestInvite|Join\+?|ジョイン|グループ|事前応募|抽選|当日枠|予約|受付開始)', text, re.IGNORECASE)
    return '・'.join(sorted(set(methods)))

def extract_participation_details(text):
    text = normalize_text(text)
    details = []
    reqin = re.search(r'(?:リクイン|ReqIn|reqin|Join|join|ジョイン|参加方法)(?:先|方法)?[：:は]?\s*([^。\n￤\|]+)', text, re.IGNORECASE)
    if reqin:
        details.append(reqin.group(1).strip())
    vrc_group = re.findall(r'(vrc\.group/[a-zA-Z0-9._-]+)', text)
    details.extend(vrc_group)
    urls = re.findall(r'(https?://[^\s<>"]+)', text)
    for url in urls:
        if not any(domain in url for domain in ['x.com', 'twitter.com', 'lit.link', 'booth.pm', 'mosh.jp', 'fanbox.cc', 'twitch.tv', 'profcard.info', 'potofu.me']):
            details.append(url)
    return ' | '.join(sorted(set(details)))

def extract_organizers(text):
    text = normalize_text(text)
    organizers = set()
    for m in re.findall(r'(?:主催|オーナー|店長)[:：]?\s*[@＠]([a-zA-Z0-9_]{1,15})|[@＠]([a-zA-Z0-9_]{1,15})', text):
        org = m[0] or m[1]
        if org and org.lower() not in ['twitter', 'vrc', 'vrchat', 'official', 'info']:
            organizers.add(f"@{org}")
    return ', '.join(sorted(organizers))

def extract_hashtags(text):
    text = normalize_text(text)
    hashtags = re.findall(r'#([A-Za-z0-9_一-龥ぁ-んァ-ンー]+)', text)
    hashtags = [f"#{h}" for h in hashtags if len(h) > 2]
    return hashtags

def extract_group_ids(text):
    text = normalize_text(text)
    group_ids = re.findall(r'vrc\.group/([A-Za-z0-9._-]+)', text)
    return group_ids

def fill_from_multiple_sources(row, extract_func, account_id="", hashtags=None):
    texts = get_candidate_texts(row)
    for text in texts:
        if extract_func == extract_event_name:
            result = extract_func(text, account_id, hashtags)
        else:
            result = extract_func(text)
        if result:
            return result
    return ""

def fill_hashtags(row):
    hashtags = set()
    for text in get_candidate_texts(row):
        hashtags.update(extract_hashtags(text))
    return list(hashtags)

def fill_group_ids(row):
    group_ids = set()
    for text in get_candidate_texts(row):
        group_ids.update(extract_group_ids(text))
    return list(group_ids)

def organize_profiles(input_csv, output_csv):
    df = pd.read_csv(input_csv, encoding="utf-8-sig")
    columns = [
        "イベント名", "定期開催時刻 (開始)", "定期開催時刻 (終了)", "開催曜日",
        "開催頻度", "参加方法", "参加詳細/リクイン先", "主催者", "公式ハッシュタグ", "グループID"
    ]
    for col in columns:
        df[col] = ""
    for idx, row in df.iterrows():
        account_id = str(row.get("account_id", ""))
        hashtags = fill_hashtags(row)
        group_ids = fill_group_ids(row)
        event_name = fill_from_multiple_sources(row, extract_event_name, account_id, hashtags)
        if not event_name:
            if hashtags:
                event_name = hashtags[0]
            else:
                event_name = account_id
        start, end = "", ""
        for text in get_candidate_texts(row):
            start, end = extract_times(text)
            if start or end:
                break
        df.at[idx, "イベント名"] = event_name
        df.at[idx, "定期開催時刻 (開始)"] = start
        df.at[idx, "定期開催時刻 (終了)"] = end
        df.at[idx, "開催曜日"] = fill_from_multiple_sources(row, extract_weekdays)
        df.at[idx, "開催頻度"] = fill_from_multiple_sources(row, extract_frequency)
        df.at[idx, "参加方法"] = fill_from_multiple_sources(row, extract_participation_method)
        df.at[idx, "参加詳細/リクイン先"] = fill_from_multiple_sources(row, extract_participation_details)
        df.at[idx, "主催者"] = fill_from_multiple_sources(row, extract_organizers)
        df.at[idx, "公式ハッシュタグ"] = " ".join(hashtags)
        df.at[idx, "グループID"] = " ".join(group_ids)
    df = df.rename(columns={
        "url": "メンバーのtwitterのリンク",
        "profile": "プロフィール",
        "固定ツイート": "固定ツイートURL",
        "最新ツイート": "最新ツイートURL",
    })
    final_columns = [
        'account_id','メンバーのtwitterのリンク','最新ツイートURL', 'プロフィール', 'イベント名', '公式ハッシュタグ', 'グループID',
        '主催者', '参加詳細/リクイン先','参加方法', 
        '開催頻度','開催曜日', '定期開催時刻 (開始)', '定期開催時刻 (終了)',
       ]
    output_columns = [col for col in final_columns if col in df.columns]
    result_df = df[output_columns]
    result_df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    return result_df

if __name__ == "__main__":
    input_dir = "twitter_profiles"
    if not os.path.exists(input_dir):
        print(f"入力ディレクトリが見つかりません: {input_dir}")
        exit(1)
    files = sorted([f for f in os.listdir(input_dir) if f.startswith("profiles_raw_") and f.endswith(".csv")])
    if not files:
        print(f"{input_dir} 内に入力ファイル (profiles_raw_*.csv) が見つかりません")
        exit(1)
    latest_file = files[-1]
    input_csv = os.path.join(input_dir, latest_file)
    print(f"入力ファイル: {input_csv}")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_csv = os.path.join(input_dir, f"profiles_organized_{timestamp}.csv")
    organize_profiles(input_csv, output_csv)
    print(f"分析結果を保存しました: {output_csv}")

