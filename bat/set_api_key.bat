@echo off
setlocal

REM Check if Twitter credentials are already set
if defined TWITTER_USERNAME (
  echo Twitter credentials are already set.
  goto :eof
)

REM Prompt for username and password
set /p TWITTER_USERNAME="Enter Twitter username: "
set /p TWITTER_PASSWORD="Enter Twitter password: "

REM Set Twitter credentials in environment variables (temporary)
set TWITTER_USERNAME=%TWITTER_USERNAME%
set TWITTER_PASSWORD=%TWITTER_PASSWORD%

REM Set Twitter credentials in environment variables (permanent)
setx TWITTER_USERNAME "%TWITTER_USERNAME%"
setx TWITTER_PASSWORD "%TWITTER_PASSWORD%"

echo Twitter credentials have been set.

endlocal