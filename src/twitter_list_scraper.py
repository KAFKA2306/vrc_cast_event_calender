from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import pandas as pd
import os
import logging
from datetime import datetime
from webdriver_manager.chrome import ChromeDriverManager

def setup_logging():
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"{log_dir}/twitter_scraper_{timestamp}.log"
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

def initialize_driver():
    logger.info("ドライバー初期化開始")
    options = Options()
    options.add_argument(f"user-data-dir={os.path.abspath('selenium_profile')}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    logger.info("ドライバー初期化完了")
    return driver

def check_login_status(driver):
    logger.info("ログイン状態確認中")
    driver.get("https://twitter.com/home")
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-testid='primaryColumn']"))
        )
        logger.info("ログイン状態：ログイン済み")
        return True
    except:
        logger.info("ログイン状態：未ログイン")
        return False

def login(driver):
    logger.info("ログイン処理開始")
    TWITTER_USERNAME = os.environ.get("TWITTER_USERNAME")
    TWITTER_PASSWORD = os.environ.get("TWITTER_PASSWORD")
    driver.get("https://twitter.com/login")
    wait = WebDriverWait(driver, 30)
    username_input = wait.until(EC.visibility_of_element_located((By.NAME, "text")))
    username_input.send_keys(TWITTER_USERNAME)
    username_input.send_keys(Keys.ENTER)
    time.sleep(2)
    password_input = wait.until(EC.visibility_of_element_located((By.NAME, "password")))
    password_input.send_keys(TWITTER_PASSWORD)
    password_input.send_keys(Keys.ENTER)
    time.sleep(5)
    return check_login_status(driver)

def wait_for_popup(driver):
    logger.info("ポップアップ検索中")
    popup_selectors = [
        "section[aria-labelledby][role='region']",
        "div[role='dialog'][aria-modal='true']",
        "div[aria-label][role='dialog']",
        "div.css-175oi2r.r-yfoy6g.r-184en5c"
    ]
    for selector in popup_selectors:
        try:
            popup = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            logger.info(f"ポップアップ検出成功: {selector}")
            return popup
        except:
            continue
    return None

def get_list_members(driver, list_members_url, max_members=200):
    logger.info(f"リストメンバー取得開始: {list_members_url}")
    driver.get(list_members_url)
    time.sleep(7)
    
    popup = wait_for_popup(driver)
    if popup is None:
        return []
    
    logger.info(f"ポップアップ要素のクラス: {popup.get_attribute('class')}")
    logger.info(f"ポップアップ内の子要素数: {len(popup.find_elements(By.XPATH, './*'))}")
    
    members = []
    processed = set()
    last_count = 0
    scroll_attempts = 0
    max_scroll_attempts = 30
    
    user_card_selectors = [
        "div[data-testid='UserCell']",
        "div[role='listitem']",
        "a[role='link'][href*='/']",
        "div.css-175oi2r div.css-175oi2r.r-1iusvr4",
        "div[data-testid='cellInnerDiv']"
    ]
    
    logger.info("メンバースクロール開始")
    while scroll_attempts < max_scroll_attempts:
        user_cards = []
        for selector in user_card_selectors:
            try:
                cards = popup.find_elements(By.CSS_SELECTOR, selector)
                if cards:
                    logger.info(f"ユーザーカード検出: '{selector}' で {len(cards)}件")
                    user_cards = cards
                    break
            except:
                continue
        
        if not user_cards:
            try:
                user_cards = popup.find_elements(By.XPATH, ".//div[contains(@class, 'r-1iusvr4')]//a[contains(@href, '/')]")
                logger.info(f"XPathでカード検出: {len(user_cards)}件")
            except:
                pass
        
        logger.info(f"現在のカード数: {len(user_cards)}, 処理済み: {len(processed)}")
        
        for card in user_cards:
            try:
                link_elem = None
                try:
                    if card.tag_name == 'a':
                        link_elem = card
                    else:
                        link_elem = card.find_element(By.XPATH, ".//a[contains(@href, '/')]")
                except:
                    continue
                
                profile_url = link_elem.get_attribute("href")
                if not profile_url:
                    continue
                
                if 'search?q=' in profile_url or '/i/' in profile_url or not '/' in profile_url:
                    continue
                    
                acc_id = profile_url.split("/")[-1]
                if acc_id in processed:
                    continue
                    
                processed.add(acc_id)
                members.append({
                    "account_id": acc_id,
                    "profile_url": profile_url
                })
                logger.info(f"ユーザー追加: {acc_id}")
            except:
                continue
        
        try:
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", popup)
            time.sleep(0.5)
            ActionChains(driver).move_to_element(popup).send_keys(Keys.PAGE_DOWN).perform()
            time.sleep(0.5)
            if user_cards:
                driver.execute_script("arguments[0].scrollIntoView(false);", user_cards[-1])
            driver.execute_script("arguments[0].scrollTop += 500;", popup)
        except:
            pass
        
        time.sleep(3)
        
        if len(members) == last_count:
            scroll_attempts += 1
            logger.info(f"新規ユーザーなし: 試行 {scroll_attempts}/{max_scroll_attempts}")
        else:
            scroll_attempts = 0
            logger.info(f"新規ユーザーあり: 現在 {len(members)}人")
        
        if len(members) >= max_members:
            break
            
        last_count = len(members)
    
    return members

def get_profile_and_tweets(driver, profile_url):
    logger.info(f"プロフィール取得開始: {profile_url}")
    driver.get(profile_url)
    time.sleep(5)
    
    profile = ""
    try:
        bio_elem = driver.find_element(By.CSS_SELECTOR, "div[data-testid='UserDescription']")
        profile = bio_elem.text
        logger.info(f"プロフィール取得成功: {len(profile)} 文字")
    except:
        pass
    
    pinned_tweet = ""
    try:
        pinned_elem = driver.find_element(By.XPATH, "//div[@data-testid='cellInnerDiv']//span[contains(text(),'固定されたポスト') or contains(text(),'Pinned Tweet')]/ancestor::div[@data-testid='cellInnerDiv']//a[contains(@href, '/status/')]")
        pinned_tweet = pinned_elem.get_attribute("href")
        logger.info(f"固定ツイート取得成功: {pinned_tweet}")
    except:
        logger.info("固定ツイートなし")
    
    latest_tweet = ""
    try:
        tweet_elems = driver.find_elements(By.XPATH, "//article[@data-testid='tweet']")
        if tweet_elems:
            latest_tweet_elem = tweet_elems[0].find_element(By.XPATH, ".//a[contains(@href, '/status/')]")
            latest_tweet = latest_tweet_elem.get_attribute("href")
            logger.info(f"最新ツイート取得成功: {latest_tweet}")
    except:
        pass
    
    return profile, pinned_tweet, latest_tweet

if __name__ == "__main__":
    logger.info("スクリプト実行開始")
    driver = initialize_driver()
    try:
        if not check_login_status(driver):
            login(driver)
        
        list_members_url = "https://x.com/i/lists/1834685283276935624/members"
        members = get_list_members(driver, list_members_url, max_members=250)
        
        logger.info(f"{len(members)}人のプロフィール情報取得開始")
        results = []
        for i, member in enumerate(members):
            logger.info(f"プロフィール取得中 ({i+1}/{len(members)}): {member['account_id']}")
            profile, pinned_tweet, latest_tweet = get_profile_and_tweets(driver, member["profile_url"])
            results.append({
                "account_id": member["account_id"],
                "url": member["profile_url"],
                "profile": profile,
                "固定ツイート": pinned_tweet,
                "最新ツイート": latest_tweet
            })
        
        logger.info("CSVファイル保存開始")
        df = pd.DataFrame(results)
        os.makedirs("twitter_profiles", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"twitter_profiles/profiles_raw_{timestamp}.csv"
        df.to_csv(output_file, index=False, encoding="utf-8-sig")
        logger.info(f"CSVファイル保存成功: {output_file}")
    finally:
        driver.quit()
        logger.info("ドライバーを終了しました")
