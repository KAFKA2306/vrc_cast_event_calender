# Featured Tonight — スポンサー掲載PoC

`Featured Tonight` は、`events.json` に既に存在する公開イベントについて、主催者または掲載権限を確認できる依頼者が開催直前の追加露出を検証するための独立スポンサー枠です。

## 掲載条件

本番manifest `sponsorships.json` は `featured-tonight.v1` を使用します。1 campaign は1 event、掲載期間は最大7日です。`event_id` が公開snapshotに存在し、`destination_url` がそのeventの既存official/participation URLと完全一致し、`authorization_status=VERIFIED` とHTTPSの権限確認証跡がある場合だけ `APPROVED` にできます。

期限切れの `APPROVED` record、存在しないevent、URL不一致、7日超過、掲載権限未確認はCIがfail closedします。`PAUSED` / `EXPIRED` は監査履歴として保持できますがUIには表示されません。

## organic面との分離

スポンサーcardは `/tonight/` の通常イベント一覧とは別のDOM sectionとして生成します。既存 `tonight.js` の検索、期間filter、category/source filter、日時sort、端末内閲覧履歴にはsponsorship dataを渡しません。購入によってorganic順位、分類confidence、推薦scoreを変更しません。

全スポンサーcardには色だけではなく文字列 `スポンサー掲載` を常時表示します。本番manifestが空、または現在有効なcampaignが0件ならスポンサーsection自体を表示しません。

## 計測境界

スポンサーUIはcampaign別に `impression` と `outbound_click` を区別します。値は `featured-tonight.metric.v1` として、campaign ID、metric名、発生時刻だけをsessionStorageへ集計し、`featured-tonight-metric` CustomEventを発火します。iframe内で使われる場合のみ同じprivacy-minimal messageを親windowへ `postMessage` します。

通常イベントの端末内閲覧履歴 `vrc-tonight-history` はスポンサー計測payloadへ含めません。個人識別子、検索語、閲覧履歴、嗜好profileをserverへ送るbackendはこのPoCでは追加しません。cross-document messagingはtracking vectorになり得るため、payloadを上記最小項目へ限定します。

一次仕様: https://html.spec.whatwg.org/multipage/web-messaging.html

## 販売単位

- 無料demo: synthetic fixture 1 eventで表示・validatorを確認
- 有償PoC候補: 1 event / 最大7日 / 1 campaign
- 本番掲載: 主催者本人または掲載権限を確認できる証跡が必須

販売価格、click効果、導入実績は実契約・実計測前に記載しません。非公開イベント、公式/参加URLへ辿れないイベント、掲載権限を確認できない案件は対象外です。

## 導入手順

1. 対象eventが現在の `events.json` に存在することを確認する。
2. official/participation URLのいずれかを `destination_url` に使用する。
3. 掲載権限を確認し、公開可能なHTTPS evidence URLを記録する。
4. 最大7日の期間でcampaign recordをPRとして追加する。
5. `python scripts/verify_sponsorships.py` とFeatured Tonight CIがgreenであることを確認する。
6. merge後、`/tonight/` の独立railと `スポンサー掲載` 表示を確認する。
7. 実測KPIだけを `metrics/featured-tonight-kpi.json` に記録する。

問い合わせ・掲載相談はGitHub Issueで受け付けます: https://github.com/KAFKA2306/vrc_cast_event_calender/issues
