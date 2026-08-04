# VRChat Event Calendar — 参加方法と根拠を確認できる公開イベント案内

`KAFKA2306/vrc_cast_event_calender`は、VRChatの公開イベント情報を、日時、参加方法、公式リンク、カテゴリ、開催形式、分類根拠と一緒に配信する**公開用リポジトリ**です。

イベントの収集・生成・品質検査の正準実装は[`KAFKA2306/cast_event_cal`](https://github.com/KAFKA2306/cast_event_cal)にあります。このリポジトリは、生成済みの静的snapshotを受け取り、GitHub PagesとCloudflare Pagesへ配信します。source側の生成成功だけを公開成功の証拠にせず、deploy側でも受信snapshotを独立検証します。

> **GitHub Pages:** https://kafka2306.github.io/vrc_cast_event_calender/  
> **Cloudflare Pages:** https://vrc-cast-event-calender.pages.dev/  
> **今夜のイベント:** `/tonight/`  
> **標準タイムゾーン:** JST  
> **実装:** 静的HTML / CSS / JavaScript / JSON / GitHub Actions

---

## 2026年8月4日のsnapshot検証

GitHub Actions run `30904241278`でrepositoryをcheckoutし、公開dataを実ファイルから直接検証しました。

| 項目 | 実測値 |
|---|---:|
| `events.json`のbyte数 | 1,949,391 bytes |
| event件数 | 601 |
| payload形式 | object内の`events`配列 |
| SHA-256 | `bfa05322318ea350626e7e4a847dd62b034c6c25f751e26e9848ffae8183956f` |
| ontology entries | 15 |
| matched events | 276 |
| ambiguous events | 0 |
| `health.json`生成時刻 | `2026-08-04T09:43:06Z` |

次のevent件数がすべて601で一致しました。

- `events.json`
- `health.json`
- `event-ontology.json`
- `ontology-match-audit.json`

GitHub Contents APIや一部のconnectorは、大容量fileの本文を返せない場合があります。空の`content`表示だけを見て、実ファイルが0 byteだと判断してはいけません。以前のREADMEに記載した0 byte判定は誤りであり、Issue #22へ訂正履歴を残しています。

この検証はrepository内snapshotの整合を示します。GitHub PagesとCloudflare Pagesのproduction response、cache、画面表示は、別の公開確認が必要です。

---

## 主な画面とdata

| 入口 | 役割 |
|---|---|
| `/` | 検索、期間、カテゴリ、情報源、分類根拠を確認する一覧 |
| `/tonight/` | 開催時刻と参加方法を先に見るmobile-firstの参加画面 |
| `events.json` | イベント本体を含む公開JSON |
| `calendar.ics` | カレンダー購読用data |
| `health.json` | 取得元、件数、ontology、分類のhealth snapshot |
| `event-ontology.json` | 観測イベントと人手管理seriesの紐付け結果 |
| `category-ontology.json` | category、subcategory、開催形式の定義 |
| `ontology-match-audit.json` | ontologyと公式linkの監査結果 |

`events.json`のtop-levelは配列ではなくobjectです。event本体は`events`fieldに格納され、schema version、生成時刻、timezone、ontology version、asset enrichment時刻などのmetadataも保持します。

---

## 利用者向けの使い方

### 今夜参加できるイベントを探す

`/tonight/`では、次を優先して表示します。

- 開始時刻
- 開催中、今夜、後日、日時不明などの状態
- 参加方法
- VRChat Group、公式告知、申込ページなどの主要action
- 主催者と開催形式

一覧は30件単位で段階描画し、末尾付近で次のeventを自動表示します。自動読込を利用できない場合は手動buttonをfallbackとして残します。

### root一覧で調べる

rootでは、次の条件で絞り込みます。

- 文字列
- 今日、7日、30日、120日
- category
- 情報源
- 募集・締切を通常一覧へ含めるか

categoryと開催形式は別の軸です。技術イベントという内容分類と、in-world開催という実施形式を混同しません。

### 端末内履歴による推薦

公式linkを開いた履歴をbrowser内に保存し、時間減衰、特徴量の類似度、開催の近さ、多様性を使って再順位付けします。

- 履歴をserverへ送信しません。
- browser storageが使えない場合は、そのpageを開いている間だけ保持します。
- 履歴がない場合は、開催の近さとcategoryの多様性を使います。
- 推薦理由を画面へ表示します。

これは利用者の嗜好を確定するmodelではなく、端末内の軽量な候補整理です。

---

## 情報源

2026年8月4日の`health.json`では、次の5系統が有効として記録されています。

| source | 役割 |
|---|---|
| `repository_manual_events` | repositoryで管理する既知イベント |
| `vrchat_calendar_discovery` | VRChat calendar由来の探索 |
| `x_curated_events` | 人手確認したX由来イベント |
| `yahoo_realtime_events` | Yahooリアルタイム検索からの候補 |
| `external_calendar_events` | 外部calendar由来イベント |

情報源ごとの件数は、重複除去前後で一致しない場合があります。source countを単純加算して総イベント数にしません。

収集結果は候補です。日時、参加条件、申込方法は、event cardから主催者の公式情報を再確認してください。

---

## event series ontology

定期・不定期に繰り返されるeventは、人間が確認したseries ontologyへ紐付けます。

- ontology entryの自動作成を禁止
- 紹介文や公式URLの自動書換えを禁止
- fuzzy matchingを禁止
- patternだけの一致を禁止
- 曖昧一致を採用しない
- alias一致、または主催者完全一致と必須patternを要求
- 観測eventは既存entryへのlinkだけを行う

ontologyには、公式site、VRChat Group、公式X、参加案内、開催周期、紹介、初参加者向け情報、公式画像などを保持できます。

2026年8月4日のsnapshotは15 entries、14 matched series、276 matched events、325 unmatched events、ambiguous 0です。これらは固定仕様ではなく、その生成時点の監査結果です。

---

## category分類

主なcategory:

- 募集・締切
- 言語交流
- 技術・研究
- 学習・講義
- アート・展示・撮影
- 音楽・ダンス
- 公演・ショー
- ゲーム・参加型
- ワールド巡り・観光
- 運動・ウェルネス
- 交流・カフェ
- その他

分類sourceも保持します。

- curated ontology
- keyword rules
- legacy category
- fallback

低confidenceのeventは監査対象として区別します。分類confidenceは、event内容の正しさや安全性を示す値ではありません。

---

## 公式linkと画像

可能な範囲で、次を区別します。

- 公式告知
- 参加・申込ページ
- VRChat Group
- VRChat World
- 公式X
- 公式Web
- 配信
- 関連Web

`x.com`と`twitter.com`の同じ投稿、同一VRChat Groupなどを二重表示しないようcanonical keyを作ります。

画像は、公式投稿、VRChat Group、公式profileなど出典を区別します。外部画像を無条件にrepositoryへ再配布しません。

---

## ローカルpreview

rootにpackage manifestはなく、静的fileを中心に構成されています。

```bash
python -m http.server 8000
```

次を開きます。

```text
http://localhost:8000/
http://localhost:8000/tonight/
```

`file://`で直接開くと、browserのfetch制限によりJSONを読み込めない場合があります。

`events.json`は約1.95MBあるため、Contents APIや一部connectorでは本文を直接表示できません。local previewではrepositoryをcheckoutした実ファイルを使用してください。

---

## 検証

### JavaScript syntax

```bash
node --check tonight/tonight.js
node --check tonight/kafka-signal.js
```

### 公開snapshot

```bash
python scripts/verify_public_snapshot.py
```

このscriptは次を検証します。

- `events.json`が非空で有効なJSON
- object wrapper内にevent配列が存在
- event件数が`health.json`と一致
- event件数が`event-ontology.json`と一致
- event件数が`ontology-match-audit.json`と一致
- byte数、payload形式、SHA-256、ontology件数をlogへ出力

`.github/workflows/verify-public-snapshot.yml`がPRとmainで同じ検証を行います。

### UI contract

`.github/workflows/uiux-tonight.yml`などで、次を確認します。

- 参加方法への導線
- 分類根拠と証跡の詳細表示
- URL queryとbrowser history
- infinite scrollと手動fallback
- focusとscroll位置の保持
- mobile幅
- 44px以上の操作target
- 日時不明状態

repository内検証に加えて、公開後はGitHub PagesとCloudflare Pagesを個別に確認します。

---

## source repoから公開まで

```text
KAFKA2306/cast_event_cal
  収集・正規化・分類・ontology・生成・source側検証
        │
        ▼
public/の生成snapshot
        │
        ▼
KAFKA2306/vrc_cast_event_calender
  deploy側snapshot検証
        │
        ├─ GitHub Pages
        └─ Cloudflare Pages
```

source repoとdeploy repoは役割が異なります。同じREADMEや生成codeを二重に正準化しません。

---

## 主要file

```text
index.html                         rootの検索・監査・推薦UI
tonight/
  index.html                       今夜の参加優先UI
  tonight.js                       filter、状態、段階描画
  kafka-signal.js                  説明追加、無限scroll、共通identity
events.json                        event本体と生成metadata
calendar.ics                       購読用calendar
health.json                        pipeline health
category-ontology.json             category定義
event-ontology.json                series紐付け結果
ontology-match-audit.json          ontology・公式link監査
scripts/verify_public_snapshot.py  deploy snapshot検証
.github/workflows/                 UI、snapshot、公開検証
```

---

## セキュリティとprivacy

- 閲覧履歴は端末内に保存します。
- API key、cookie、認証sessionを公開repositoryへ保存しません。
- 非公開eventや参加者個人情報を公開dataへ追加しません。
- X、VRChat、外部calendarの利用条件とrate limitを守ります。
- 短縮URLやredirectは、解決結果と根拠を保持します。
- 主催者の公式説明と、収集側が生成した説明を混同しません。

---

## 既知の制約

- すべてのVRChat eventを網羅しません。
- 情報源の取得停止や仕様変更で欠損が発生します。
- 自動分類には誤りがあり得ます。
- ontologyへ未登録のseriesは詳細情報が少なくなります。
- 日時不明や終了済み投稿を完全には解決できません。
- 公式告知の削除、時刻変更、参加条件変更は後から起こり得ます。
- local history推薦はbrowser単位で、account同期しません。
- `events.json`は大容量のobject wrapperであり、一部APIでは本文が省略されます。
- repository snapshotの成功は、production cacheや表示内容の成功を自動的に証明しません。

---

## README.mdの役割

READMEは、人間がプロジェクトの目的、source/deploy境界、公開面、data、分類、ontology、検証、運用、制約を理解する正準入口です。

件数やhashは固定仕様ではなく、確認日時を伴うsnapshotとして記載します。生成schema、公開構造、正準repo、主要検証が変わるPRでは、READMEも更新します。

**README実体監査:** 2026年8月4日
