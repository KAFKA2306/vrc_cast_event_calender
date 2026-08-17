# VRChat Event Calendar

[![Deploy canonical Pages v2](https://github.com/KAFKA2306/vrc_cast_event_calender/actions/workflows/deploy-canonical-pages-v2.yml/badge.svg)](https://github.com/KAFKA2306/vrc_cast_event_calender/actions/workflows/deploy-canonical-pages-v2.yml)
[![Web quality](https://github.com/KAFKA2306/vrc_cast_event_calender/actions/workflows/web-quality.yml/badge.svg)](https://github.com/KAFKA2306/vrc_cast_event_calender/actions/workflows/web-quality.yml)
[![Verify public snapshot](https://github.com/KAFKA2306/vrc_cast_event_calender/actions/workflows/verify-public-snapshot.yml/badge.svg)](https://github.com/KAFKA2306/vrc_cast_event_calender/actions/workflows/verify-public-snapshot.yml)

**今夜行けるイベントを探したい。そのとき必要なのは、イベント数より「この日時・参加方法をどこまで信じてよいか」です。**

VRChat Event Calendar は、VRChatのイベントを検索・購読しやすい形で公開しながら、**表示している情報がどの正本snapshotから来たのかを追跡できる配信面**です。

- GitHub Pages: https://kafka2306.github.io/vrc_cast_event_calender/
- Cloudflare Pages: https://vrc-cast-event-calender.pages.dev/
- JSON: https://kafka2306.github.io/vrc_cast_event_calender/events.json
- iCalendar: https://kafka2306.github.io/vrc_cast_event_calender/calendar.ics
- 標準タイムゾーン: JST

正本は [`KAFKA2306/cast_event_cal`](https://github.com/KAFKA2306/cast_event_cal) です。このrepositoryはイベントを再収集・再分類せず、正本が生成した検証済みsnapshotを受け取って公開します。

## Vision

複数の告知先を手作業で巡回しなくても、**利用者が「今夜・今週どんなVRChatイベントがあるか」を素早く見つけ、公式告知へ戻って参加判断できる体験**を作ります。

同時に、配信側が古い・部分的・壊れたデータを「最新」と見せないことを重視します。

利用者ができること:

- 日時・カテゴリ・情報源からイベントを探す
- mobile-firstの`/tonight/`で開催直前の情報を見る
- calendarを購読する
- 主催者の公式告知・Group・World・申込先へ移動する
- 公開snapshotのsource commit / hash / healthを確認する

## Design philosophy

- **収集と配信を二重管理しない。** ingestion / normalization / classificationは`cast_event_cal`だけが担う。
- **配信成功をデータ成功と呼ばない。** Pagesが200を返しても、正本snapshotのhealthとparityが合わなければ成功扱いしない。
- **partial updateを正常snapshotにしない。** canonical `public/` を一括受信し、artifact集合全体をmanifestで固定する。
- **鮮度を推測しない。** source commit、snapshot generated time、received/deployed timeを分けて保持する。
- **hashで正本まで戻れるようにする。** path / bytes / SHA-256からsnapshot digestを決定論的に作る。
- **最終判断は主催者の最新公式情報へ戻す。** calendarは発見と整理を助けるが、主催者の告知を置き換えない。

## Why / 差別化

静的なイベント一覧やICSを作るだけなら、配信は簡単です。難しいのは、**配信された1件1件が「どの正本状態から来たか」を説明し、正本と公開物がずれたときに公開を止めること**です。

このrepositoryの差別化はイベント件数ではありません。

- canonical sourceとprojectionを分離する
- source commitとsnapshot digestを公開artifactへ結びつける
- fail-closed parity gateを持つ
- production HTTP verificationをbuild成功と分離する

ことで、利用者へ「見えているから正しい」ではなく「どの状態を根拠に表示しているか分かる」calendarを提供します。

## User journey

```text
イベントを探す
  → / または /tonight/
  → 日時・カテゴリ・情報源で絞る
  → event cardを確認
  → 主催者の公式告知へ移動
  → 最新日時・参加条件を最終確認
  → VRChatで参加
```

calendarの役割は、公式情報へ短く到達させることです。

## Canonical data boundary

```text
KAFKA2306/cast_event_cal
  collection
  normalization
  classification
  ontology
  canonical public snapshot
        │
        │ source commit + hashes
        ▼
KAFKA2306/vrc_cast_event_calender
  receive
  parity validation
  projection only
        │
        ├─ GitHub Pages
        └─ Cloudflare Pages
```

配信repoで独自collector、独自classifier、別正本DBを持ちません。

正本資料:

- [README / Data Quality](https://github.com/KAFKA2306/cast_event_cal/blob/main/README.md)
- [Scraping methodology](https://github.com/KAFKA2306/cast_event_cal/blob/main/docs/SCRAPING_METHOD.md)
- [Architecture](https://github.com/KAFKA2306/cast_event_cal/blob/main/docs/architecture.md)
- [API](https://github.com/KAFKA2306/cast_event_cal/blob/main/docs/api-v1.md)
- [MCP](https://github.com/KAFKA2306/cast_event_cal/blob/main/docs/mcp.md)

## Projection manifest

`.github/workflows/deploy-canonical-pages-v2.yml` が正本`main`の`canonical/public/`を受信し、`projection-manifest.json`を生成します。

主なfield:

- `role = projection_only`
- `source_repository`
- `source_commit_sha`
- `source_snapshot_sha256`
- `source_snapshot_generated_at`
- `received_at`
- `deployed_at`
- `collection_counts`
- `event_count`
- `ontology_version`
- `validation_status`
- 全canonical artifactの`bytes` / `sha256`

`source_snapshot_sha256` はmanifest内のartifact集合から決定論的に導出します。

## Fail-closed publish gate

公開前に検証するもの:

1. `events.json` / `health.json` / ontology / auditのschema・件数整合
2. `health.status == ok`
3. `failed_sources == 0`
4. source commit / snapshot digest / bytes / SHA-256 parity
5. GitHub Pages production HTTP response
6. production manifestとsource commitの一致

mismatch時はdeploy failureです。古いsnapshotや部分更新を「正常最新値」へ昇格しません。

## Public artifacts

| path | purpose |
|---|---|
| `events.json` | canonical event projection |
| `calendar.ics` | calendar subscription |
| `health.json` | source pipeline health |
| `event-ontology.json` | event-series relation |
| `category-ontology.json` | category / format definitions |
| `ontology-match-audit.json` | ontology matching evidence |
| `projection-manifest.json` | source commit / snapshot / artifact parity |
| `audit/production-v2-status.json` | production HTTP verification |

件数・分類version・生成時刻はsnapshotごとに変わるため、現在値はJSON / manifestを参照してください。

## Views

### `/`

検索・期間・カテゴリ・情報源を使う通常のevent discovery viewです。

### `/tonight/`

開催時刻と参加方法を優先するmobile-first viewです。直前の参加判断では必ず公式告知を再確認してください。

## Local preview

```bash
python -m http.server 8000
```

`http://localhost:8000/` または `/tonight/` を開きます。`file://`ではJSON fetchが制限される場合があります。

## Validation

```bash
python scripts/verify_public_snapshot.py
python -m unittest tests.test_projection_manifest -v
```

manifest生成:

```bash
python scripts/write_projection_manifest.py \
  --canonical-root /path/to/cast_event_cal/public \
  --source-commit <40-char-commit-sha> \
  --output projection-manifest.json
```

## Privacy / security

- API key、cookie、認証sessionをpublic repoへ保存しない
- 非公開event・参加者個人情報を公開dataへ入れない
- 閲覧履歴を正本へ送らない
- collection側の利用条件・rate limitは`cast_event_cal`で管理する
- 配信面へ独立した正本MCP / collectorを追加しない

## Known limits

- すべてのVRChat eventを網羅するサービスではない
- source停止・仕様変更で欠損は起こり得る
- 自動分類は誤る可能性がある
- build成功だけではproduction/CDN状態まで証明しない
- calendar情報は主催者の最終公式告知を置き換えない

## Done

このrepositoryの成功は「イベントを何件表示したか」では測りません。

**利用者が行きたいイベントへ短く到達でき、運営側はその表示がどの正本snapshotに基づくかを説明でき、ずれた公開物を正常扱いしないこと**をDoneとします。
