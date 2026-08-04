# VRChat Event Calendar — 参加方法と根拠を確認できる公開イベント案内

`KAFKA2306/vrc_cast_event_calender`は、VRChatの公開イベント情報を複数の情報源から集約し、日時、参加方法、公式リンク、カテゴリ、開催形式、分類根拠と一緒に閲覧できる静的イベント案内です。

利用者向けの一覧と、データ品質を確認する監査情報を分けています。イベントを探す人は「今夜」の参加優先画面から入り、データを確認する人はrootの監査寄り一覧、JSON、ontology、healthを参照します。

> **GitHub Pages:** https://kafka2306.github.io/vrc_cast_event_calender/  
> **Cloudflare Pages:** https://vrc-cast-event-calender.pages.dev/  
> **今夜のイベント:** `/tonight/`  
> **タイムゾーン:** JST  
> **実装:** 静的HTML / CSS / JavaScript / JSON / GitHub Actions

---

## 現在の重要な状態

2026年8月4日のdefault branch監査では、次の不整合を確認しています。

- `health.json`は`status: ok`、イベント601件、情報源5系統、ontology 15 entries、紐付け276件、曖昧一致0件を記録しています。
- `event-ontology.json`もsource event 601件を記録しています。
- 一方、default branchの`events.json`は0 byteです。
- `index.html`は`events.json`を取得してJSONとして読み込む実装です。

このため、GitHubに保存されたイベント本体とhealth・ontologyの間に整合性問題があります。Incident #22で復旧と再発防止を追跡しています。

**READMEの記述やhealthだけを根拠に、現在の公開一覧が正常とは判断しません。** GitHub PagesとCloudflare Pagesは個別に確認します。

---

## 主な画面とデータ

| 入口 | 役割 |
|---|---|
| `/` | 検索、期間、カテゴリ、情報源、分類根拠を確認する監査寄り一覧 |
| `/tonight/` | 開催時刻と参加方法を先に見るmobile-firstの参加画面 |
| `events.json` | イベント本体の公開JSON契約 |
| `calendar.ics` | カレンダー購読用データ |
| `health.json` | 取得元、件数、ontology、分類のhealth snapshot |
| `event-ontology.json` | 観測イベントと人手管理seriesの紐付け結果 |
| `category-ontology.json` | カテゴリ、subcategory、開催形式の定義 |
| `ontology-match-audit.json` | 公式リンクとontology照合の監査結果 |

各JSONは生成時点のsnapshotです。ファイルが存在するだけで、相互に同じ生成runから作られたとは限りません。件数、生成時刻、hashの整合を確認します。

---

## 利用者向けの考え方

## 今夜のイベントを探す

`/tonight/`は、次を先に表示します。

- 開始時刻
- 開催中、今夜、後日、日時不明などの状態
- 参加方法
- VRChat Group、公式告知、申込ページなどの主要action
- 主催者と開催形式

分類根拠、情報源、監査情報は詳細へ分離します。

一覧は30件単位で段階描画し、末尾付近で次のイベントを自動表示します。無限scrollを利用できない環境では手動buttonをfallbackとして残します。

## rootの一覧で調べる

rootの画面では、次の条件で絞り込みます。

- 文字列検索
- 今日、7日、30日、120日
- カテゴリ
- 情報源
- 募集・締切を通常一覧へ含めるか

カテゴリと開催形式を別の軸として表示します。例えば、技術イベントとin-world開催、募集締切とdeadlineは別の情報です。

## 端末内の閲覧履歴による推薦

rootの推薦は、公式リンクを開いた履歴をブラウザ内へ保存し、時間減衰、特徴量の類似度、開催の近さ、多様性を使って再順位付けします。

- serverへ個人の閲覧履歴を送信しません。
- browser storageが使えない場合は、そのpageを開いている間だけ保持します。
- 履歴がない場合は、開催の近さとカテゴリの多様性を使います。
- 推薦理由は画面に表示します。

これは利用者の嗜好を断定するモデルではなく、端末内の軽量な候補整理です。

---

## 情報源

`health.json`の2026年8月4日snapshotでは、次の5系統が有効として記録されています。

| source | 役割 |
|---|---|
| `repository_manual_events` | repositoryで管理する既知イベント |
| `vrchat_calendar_discovery` | VRChat calendar由来の探索 |
| `x_curated_events` | 人手確認したX由来イベント |
| `yahoo_realtime_events` | Yahooリアルタイム検索からの候補 |
| `external_calendar_events` | 外部カレンダー由来イベント |

情報源ごとの件数は重複除去前後で一致しない場合があります。source countを単純加算して総イベント数にしません。

収集結果は候補です。公式イベント説明、参加条件、開催日時は、イベントカードの公式リンクで再確認してください。

---

## event series ontology

定期・不定期に繰り返されるイベントは、人間が確認したseries ontologyへ紐付けます。

方針:

- ontology entryの自動作成を禁止
- 紹介文や公式URLの自動書換えを禁止
- fuzzy matchingを禁止
- patternだけの一致を禁止
- 曖昧一致を採用しない
- alias一致、または主催者完全一致と必須patternを要求
- 観測イベントは既存entryへのlinkだけを行う

ontologyには、公式site、VRChat Group、公式X、参加案内、開催周期、紹介、初参加者向け情報、公式画像などを保持できます。

2026年8月4日のsnapshotでは、15 entries、14 matched series、276 matched events、325 unmatched events、ambiguous 0が記録されています。これらの数値は固定仕様ではなく、その生成時点の監査結果です。

---

## カテゴリ分類

主なカテゴリ:

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

分類sourceを保持します。

- curated ontology
- keyword rules
- legacy category
- fallback

低confidenceのイベントは監査対象として区別します。分類confidenceはイベント内容の正しさや安全性を示す値ではありません。

---

## 公式リンクと画像

イベントごとに、可能な範囲で次を区別します。

- 公式告知
- 参加・申込ページ
- VRChat Group
- VRChat World
- 公式X
- 公式Web
- 配信
- 関連Web

同じ告知を`x.com`と`twitter.com`の別URLとして二重表示しないようcanonical keyを作ります。

画像は、公式投稿、VRChat Group、公式profileなど出典を区別し、可能な場合は参加・募集ページへlinkします。外部画像を無条件にrepositoryへ再配布しません。

---

## ローカルで確認する

rootにpackage manifestはなく、現在の公開物は静的fileを中心に構成されています。

簡易preview:

```bash
python -m http.server 8000
```

その後、次を開きます。

```text
http://localhost:8000/
http://localhost:8000/tonight/
```

`file://`で直接開くと、browserのfetch制限によりJSONを読み込めない場合があります。

ただし、現在のdefault branchでは`events.json`が空であるため、復旧前は一覧の正常表示を期待できません。

---

## 主な検証

### JavaScript syntax

```bash
node --check tonight/tonight.js
node --check tonight/kafka-signal.js
```

### UI contract

`.github/workflows/uiux-tonight.yml`では、次のような契約を検査します。

- 参加方法への導線
- 分類根拠と証跡の詳細表示
- URL queryとbrowser history
- infinite scrollと手動fallback
- focusとscroll位置の保持
- mobile幅
- 44px以上の操作target
- 日時不明状態

### データ整合

今後、少なくとも次を同じ検証で確認する必要があります。

- `events.json`が0 byteではない
- 有効なJSONである
- event件数が`health.json`と一致する
- 生成時刻が同じrunに属する
- ontology auditのsource countと一致する
- GitHub PagesとCloudflare Pagesの両方で同じrevisionを確認する

この不足はIncident #22で追跡しています。

---

## 公開と運用

公開面は2系統あります。

1. GitHub Pages
2. Cloudflare Pages

同じrepositoryを参照していても、deploy時刻、cache、runtime処理、response headerが異なる場合があります。片方の成功をもう片方の証拠にしません。

過去のproduction verifierは、`health.json`と`ontology-match-audit.json`の件数、ambiguous 0、Cloudflareのquality-view headerを確認していました。今後は`events.json`本体の非空・parse・件数も必須gateにします。

---

## 主要ファイル

```text
index.html                    rootの検索・監査・推薦UI
tonight/
  index.html                  今夜の参加優先UI
  tonight.js                  filter、状態、段階描画
  kafka-signal.js             説明追加、無限scroll、共通identity
events.json                   イベント本体
calendar.ics                  購読用calendar
health.json                   pipeline health
category-ontology.json        category定義
event-ontology.json           series紐付け結果
ontology-match-audit.json     ontology・公式link監査
.github/workflows/            UI、生成、公開、production verification
```

生成元、手動正準、生成物の完全な境界は、Incident #22の復旧時にREADMEと設計文書へ追加します。

---

## セキュリティとプライバシー

- 閲覧履歴は端末内に保存します。
- API key、cookie、認証sessionを公開repositoryへ保存しません。
- 非公開イベントや参加者個人情報を公開dataへ追加しません。
- X、VRChat、外部calendarの利用条件とrate limitを守ります。
- 短縮URLやredirectは、解決結果と根拠を保持します。
- イベント情報は主催者の公式説明を優先し、収集側の説明と混同しません。

---

## 既知の制約

- 現在、default branchの`events.json`が空であり、復旧中です。
- すべてのVRChatイベントを網羅しません。
- 情報源の取得停止や仕様変更で欠損が発生します。
- 自動分類には誤りがあり得ます。
- ontologyへ未登録のseriesは詳細情報が少なくなります。
- 日時不明や終了済み投稿を完全には解決できません。
- 公式告知の削除、時刻変更、参加条件変更は後から起こり得ます。
- local history推薦はbrowser単位で、account同期しません。

---

## README.mdの役割

READMEは、人間がプロジェクトの目的、公開面、data、分類、ontology、検証、運用、既知の障害を理解する正準入口です。

数値は固定仕様としてではなく、確認日時を伴うsnapshotとして記載します。pipeline、公開構造、正準data、主要commandが変わるPRでは、README更新の要否を確認します。

**README実体監査:** 2026年8月4日
