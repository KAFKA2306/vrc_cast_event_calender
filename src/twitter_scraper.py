from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import pandas as pd
import json
import os
from datetime import datetime, timedelta

def initialize_driver():
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    except:
        driver = webdriver.Chrome(options=options)
    return driver

def login(driver):
    TWITTER_USERNAME = os.environ.get("TWITTER_USERNAME")
    TWITTER_PASSWORD = os.environ.get("TWITTER_PASSWORD")
    driver.get("https://twitter.com/i/flow/login")
    time.sleep(5)
    username_field = WebDriverWait(driver, 15).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "input[autocomplete='username']"))
    )
    username_field.send_keys(TWITTER_USERNAME)
    time.sleep(1)
    next_button = driver.find_element(By.XPATH, "//span[contains(text(), '次へ')]")
    next_button.click()
    time.sleep(3)
    password_field = WebDriverWait(driver, 15).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='password']"))
    )
    password_field.send_keys(TWITTER_PASSWORD)
    time.sleep(1)
    login_button = driver.find_element(By.XPATH, "//span[contains(text(), 'ログイン')]")
    login_button.click()
    time.sleep(10)

def scrape_tweets(driver, search_url):
    driver.get(search_url)
    time.sleep(5)
    print("スクレイピング開始")
    tweets = []
    processed_ids = set()
    max_tweets = 10
    last_height = driver.execute_script("return document.body.scrollHeight")

    def scroll_and_wait():
        driver.execute_script("""
            window.scrollTo({
                top: document.body.scrollHeight,
                behavior: 'smooth'
            });
        """)
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        time.sleep(3)  # 追加読み込み待機

    previous_count = 0
    while len(tweets) < max_tweets:
        tweet_elements = driver.find_elements(By.CSS_SELECTOR, "article[data-testid='tweet']")
        print(f"現在のページで{len(tweet_elements)}件のツイート要素を検出")

        for tweet in tweet_elements:
            try:
                tweet_link = WebDriverWait(tweet, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/status/']"))
                ).get_attribute("href")
                tweet_id = tweet_link.split("/status/")[1].split("?")[0]
            except:
                print("ID取得失敗: 次のツイートへスキップ")
                continue

            if tweet_id in processed_ids:
                continue

            username = "名前取得失敗"
            selectors = [
                "a[role='link'] div span",  # 最新UI用
                "div[data-testid='User-Name'] span",  # 旧UI互換
                "div[dir='ltr'] span"  # 代替案
            ]

            for selector in selectors:
                try:
                    username_element = tweet.find_element(By.CSS_SELECTOR, selector)
                    username = username_element.text
                    break
                except:
                    continue

            try:
                text_element = tweet.find_element(By.CSS_SELECTOR, "div[data-testid='tweetText']")
                text = text_element.text
            except:
                text = "テキスト取得失敗"

            try:
                date_element = tweet.find_element(By.TAG_NAME, "time")
                date = date_element.get_attribute("datetime")
            except:
                date = "日付取得失敗"

            tweets.append({
                "id": tweet_id,
                "username": username,
                "text": text,
                "date": date
            })
            processed_ids.add(tweet_id)
            print(f"ツイート取得: {tweet_id} - {username}")

            if len(tweets) >= max_tweets:
                break

        scroll_and_wait()
        new_tweet_count = len(processed_ids)
        if new_tweet_count == previous_count:
            print("追加ツイートなし、スクレイピング終了")
            break
        previous_count = new_tweet_count

    return tweets

if __name__ == "__main__":
    driver = initialize_driver()
    try:
        login(driver)
        tweets = scrape_tweets(driver, "https://x.com/search?q=%E3%83%AA%E3%82%AF%E3%82%A4%E3%83%B3%20exia_vrc&src=typed_query&f=live")

        if tweets:
            output_dir = "twitter_data"
            os.makedirs(output_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_file = os.path.join(output_dir, f"results_{timestamp}.csv")
            json_file = os.path.join(output_dir, f"results_{timestamp}.json")

            pd.DataFrame(tweets).to_csv(csv_file, index=False)
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(tweets, f, ensure_ascii=False, indent=4)

            print(f"完了: {len(tweets)}件のデータを保存")
        else:
            print("取得データなし")

    finally:
        driver.quit()