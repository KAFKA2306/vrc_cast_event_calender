@echo off
setlocal

REM リモートリポジトリのURLを設定
set REPO_URL=https://github.com/KAFKA2306/vrc_cast_event_calender.git

REM gitリポジトリの初期化
git init

REM リモートリポジトリの登録
git remote add origin %REPO_URL%

REM ファイルのadd
git add .

REM コミット
git commit -m "Initial commit"

REM git push
git push origin main

endlocal