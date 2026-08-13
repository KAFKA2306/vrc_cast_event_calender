# VRChat Event Calendar

**公開カレンダーが見えていても、「その情報をどこで作ったか」が曖昧なら更新事故は防げない。**

収集・分類する場所と配信する場所を同じ正本として扱うと、片方だけ更新されたり、配信成功を収集成功と誤認したりします。このリポジトリは、イベントを再収集・再分類せず、正本が作った検証済みsnapshotだけを受け取って公開する配信面です。

正本は [`KAFKA2306/cast_event_cal`](https://github.com/KAFKA2306/cast_event_cal) です。ここで初めて projection、snapshot、manifest、hash parity などの技術語を使い、正本commitと公開artifactの対応を検証します。

READMEの入口は [`KAFKA2306/articles#34`](https://github.com/KAFKA2306/articles/issues/34) の「広い問題 → 具体例 → 技術」の編集原則を維持し、配信成功を収集・分類成功へ読み替えません。

- GitHub Pages: https://kafka2306.github.io/vrc_cast_event_calender/
- Cloudflare Pages: https://vrc-cast-event-calender.pages.dev/
- JSON: https://kafka2306.github.io/vrc_cast_event_calender/events.json
- iCalendar: https://kafka2306.github.io/vrc_cast_event_calender/calendar.ics
- 標準タイムゾーン: JST

## 正本への入口

データの意味・生成方法・品質判定は配信repoで二重定義しません。次の正本資料を参照してください。

- **正本README / Data Quality:** https://github.com/KAFKA2306/cast_event_cal/blob/main/README.md#品質原則
- **Methodology / scraping:** https://github.com/KAFKA2306/cast_event_cal/blob/main/docs/SCRAPING_METHOD.md
- **MCP:** https://github.com/KAFKA2306/cast_event_cal/blob/main/docs/mcp.md
- **Architecture:** https://github.com/KAFKA2306/cast_event_cal/blob/main/docs/architecture.md
- **API:** https://github.com/KAFKA2306/cast_event_cal/blob/main/docs/api-v1.md

MCPをこの配信面へ追加する場合も、同一snapshot/read modelを読むproxy/adapterに限定します。このrepoで独立した収集・分類・正本データを生成しません。

## Data Contract

公開snapshotは `.github/workflows/deploy-canonical-pages-v2.yml` が `KAFKA2306/cast_event_cal` の `main` をcheckoutし、`canonical/public/` を一括受信して配信します。部分的なYahoo evidence同期やdeploy側での分類指標生成は正準経路にしません。

各deployで `projection-manifest.json` を生成します。manifest v2は少なくとも次を保持します。

- `schema_version`
- `role = projection_only`
- `source_repository`
- `source_commit_sha`
- `source_snapshot_sha256`
- `source_snapshot_generated_at`
- `generated_at`
- `received_at`
- `deployed_at`
- `collection_counts`
- `event_count`
- `ontology_version`
- `validation_status`
- canonical `public/` 配下の**全file**について `bytes` / `sha256`

`source_snapshot_sha256` は、manifestに列挙した全canonical artifactのpath・byte数・SHA-256から決定論的に導出します。これにより、公開snapshotから正本commitと受信artifact集合へ遡れます。

## Fail-closed gate

公開前に次を検証します。

1. 正本 `events.json` / `health.json` / ontology / auditのschemaと件数整合
2. `health.status == ok` かつ `failed_sources == 0`
3. event countとsource/ontology監査の整合
4. projection manifestのsource commit、snapshot digest、全artifact byte数・SHA-256
5. GitHub PagesのHTTP responseとmanifest/source commitの一致
6. 公開artifactのhash parity

mismatch時はdeploy workflowをfailureにし、「古い値や一部だけ更新した値を正常snapshotとして公開できた」とは扱いません。

## 公開data

主なartifact:

| path | 役割 |
|---|---|
| `events.json` | 統合イベントと生成metadata |
| `calendar.ics` | カレンダー購読 |
| `health.json` | 正本pipelineのhealth snapshot |
| `event-ontology.json` | event seriesとの紐付け結果 |
| `category-ontology.json` | category / 開催形式定義 |
| `ontology-match-audit.json` | ontology照合監査 |
| `projection-manifest.json` | 正本commit・snapshot・artifact hashの追跡契約 |
| `audit/production-v2-status.json` | production HTTP検証結果 |

件数・分類version・生成時刻はsnapshotごとに変わるため、このREADMEへ固定値として複製しません。現在値は各JSONとmanifestを参照してください。

## 利用者向け画面

- `/` — 検索、期間、カテゴリ、情報源、分類根拠を確認する一覧
- `/tonight/` — 開催時刻と参加方法を優先するmobile-first画面

イベントカードから公式告知、参加・申込ページ、VRChat Group、World、公式X等を確認できます。日時・参加条件は主催者の最新公式情報を最終確認してください。

## ローカルpreview

静的ファイルが中心です。

```bash
python -m http.server 8000
```

その後、`http://localhost:8000/` または `/tonight/` を開きます。`file://` ではbrowserのfetch制限によりJSONを読み込めない場合があります。

## 検証

repository内snapshot:

```bash
python scripts/verify_public_snapshot.py
python -m unittest tests.test_projection_manifest -v
```

projection manifest生成:

```bash
python scripts/write_projection_manifest.py \
  --canonical-root /path/to/cast_event_cal/public \
  --source-commit <40-char-commit-sha> \
  --output projection-manifest.json
```

PRとmainでは `.github/workflows/verify-public-snapshot.yml` が同じ契約を検査します。実deployは `.github/workflows/deploy-canonical-pages-v2.yml` が正本checkout → 検証 → 一括copy → manifest生成 → production HTTP検証まで行います。

## セキュリティとprivacy

- API key、cookie、認証sessionを公開repositoryへ保存しません。
- 非公開eventや参加者個人情報を公開dataへ追加しません。
- 閲覧履歴を使うUI機能はbrowser内に保持し、serverへ正本データとして送信しません。
- 正本の取得元利用条件・rate limit・分類方針は `cast_event_cal` 側で管理します。
- 配信repoは独自のEDINETDB consumer、独立MCP正本、独自収集器を持ちません。

## 既知の制約

- すべてのVRChat eventを網羅するサービスではありません。
- 正本の情報源停止や仕様変更により欠損が発生し得ます。
- 自動分類には誤りがあり得ます。
- repository snapshotの整合だけではCDN/cacheを含むproduction成功を証明しないため、production HTTP検証を別gateで行います。
- GitHub Contents API等は大容量JSON本文を省略する場合があるため、byte数やhashの判定はcheckoutした実ファイルで行います。

## Repository boundary

```text
KAFKA2306/cast_event_cal
  canonical ingestion / normalization / classification / ontology
  canonical public snapshot generation
        │
        ▼  commit SHA + snapshot hashes
KAFKA2306/vrc_cast_event_calender
  receive / parity validation / static projection
        │
        ├─ GitHub Pages
        └─ Cloudflare Pages
```

この境界を変更する場合は、正本と配信面を再び二重管理しないことを最優先にします。
