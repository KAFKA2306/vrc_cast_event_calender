import pandas as pd
import json
import os
import time
import random
import logging
import pickle
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException

def setup_logging():
    log_dir = "twitter_logs"
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f"scraper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger('twitter_scraper')

def initialize_driver():
    options = Options()
    options.add_argument(f"user-data-dir={os.path.abspath('selenium_profile')}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=800,2000")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def login_if_needed(driver, logger):
    driver.get("https://twitter.com/home")
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-testid='primaryColumn']")))
        logger.info("Already logged in")
        return True
    except:
        logger.info("Login required")
        driver.get("https://twitter.com/i/flow/login")
        TWITTER_USERNAME = os.environ.get("TWITTER_USERNAME")
        TWITTER_PASSWORD = os.environ.get("TWITTER_PASSWORD")
        
        username_field = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input[autocomplete='username']"))
        )
        username_field.send_keys(TWITTER_USERNAME)
        time.sleep(random.uniform(1, 2))
        
        next_button = driver.find_element(By.XPATH, "//span[contains(text(), '次へ')]")
        next_button.click()
        time.sleep(random.uniform(2, 3))
        
        password_field = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='password']"))
        )
        password_field.send_keys(TWITTER_PASSWORD)
        time.sleep(random.uniform(1, 2))
        
        login_button = driver.find_element(By.XPATH, "//span[contains(text(), 'ログイン')]")
        login_button.click()
        time.sleep(random.uniform(5, 10))
        logger.info("Login completed")
        return True

def load_checkpoint(checkpoint_file):
    if os.path.exists(checkpoint_file):
        with open(checkpoint_file, 'rb') as f:
            return pickle.load(f)
    return [], set(), 0

def save_checkpoint(tweets, processed_ids, scroll_position, checkpoint_file):
    with open(checkpoint_file, 'wb') as f:
        pickle.dump((tweets, processed_ids, scroll_position), f)

def save_interim_results(tweets, output_dir, timestamp):
    if not tweets:
        return
    
    os.makedirs(output_dir, exist_ok=True)
    
    interim_csv = os.path.join(output_dir, f"interim_results_{timestamp}.csv")
    interim_json = os.path.join(output_dir, f"interim_results_{timestamp}.json")
    
    pd.DataFrame(tweets).to_csv(interim_csv, index=False)
    with open(interim_json, 'w', encoding='utf-8') as f:
        json.dump(tweets, f, ensure_ascii=False, indent=4)

def load_previous_results(output_dir):
    all_tweets = []
    all_ids = set()
    
    interim_files = [f for f in os.listdir(output_dir) if f.startswith("interim_results_") and f.endswith(".csv")]
    
    for file in interim_files:
        try:
            df = pd.read_csv(os.path.join(output_dir, file))
            for _, row in df.iterrows():
                tweet_id = str(row['id'])
                if tweet_id not in all_ids:
                    all_ids.add(tweet_id)
                    all_tweets.append(row.to_dict())
        except Exception as e:
            continue
    
    return all_tweets, all_ids

def scrape_tweets(driver, search_url, max_tweets=500, max_scroll_attempts=2, checkpoint_interval=10, logger=None):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    checkpoint_file = f"twitter_data/checkpoint_{timestamp}.pkl"
    output_dir = "twitter_data"
    
    tweets, processed_ids, last_position = load_checkpoint(checkpoint_file)
    
    if tweets:
        logger.info(f"Resuming from checkpoint with {len(tweets)} tweets already collected")
    else:
        previous_tweets, previous_ids = load_previous_results(output_dir)
        if previous_tweets:
            tweets = previous_tweets
            processed_ids = previous_ids
            logger.info(f"Loaded {len(tweets)} tweets from previous interim results")
        else:
            logger.info("Starting new scraping session")
    
    driver.get(search_url)
    time.sleep(random.uniform(3, 5))
    
    if last_position > 0:
        driver.execute_script(f"window.scrollTo(0, {last_position});")
        time.sleep(random.uniform(2, 3))
    
    logger.info("Scraping started")
    
    scroll_attempts = 0
    tweets_count_at_last_save = len(tweets)
    
    try:
        while len(tweets) < max_tweets and scroll_attempts < max_scroll_attempts:
            tweet_selectors = [
                "article[data-testid='tweet']",
                "article[role='article']",
                "div[data-testid='cellInnerDiv']"
            ]
            
            tweet_elements = []
            for selector in tweet_selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    tweet_elements = elements
                    break
            
            logger.info(f"Found {len(tweet_elements)} tweet elements on current page")
            
            for tweet in tweet_elements:
                try:
                    pinned = tweet.find_elements(By.CSS_SELECTOR, "div[data-testid='socialContext']")
                    retweet = tweet.find_elements(By.CSS_SELECTOR, "span[data-testid='socialContext']")
                    
                    if pinned or retweet:
                        continue
                    
                    tweet_link_selectors = [
                        "a[href*='/status/']",
                        "a[role='link'][href*='/status/']"
                    ]
                    
                    tweet_link = None
                    for selector in tweet_link_selectors:
                        links = tweet.find_elements(By.CSS_SELECTOR, selector)
                        if links:
                            for link in links:
                                href = link.get_attribute("href")
                                if href and "/status/" in href:
                                    tweet_link = href
                                    break
                        if tweet_link:
                            break
                    
                    if not tweet_link:
                        continue
                    
                    tweet_id = tweet_link.split("/status/")[1].split("?")[0]
                    
                    if tweet_id in processed_ids:
                        continue
                    
                    username_selectors = [
                        "a[role='link'] div span",
                        "div[data-testid='User-Name'] span",
                        "div[dir='ltr'] span"
                    ]
                    
                    username = "名前取得失敗"
                    for selector in username_selectors:
                        try:
                            elements = tweet.find_elements(By.CSS_SELECTOR, selector)
                            if elements:
                                username = elements[0].text
                                break
                        except:
                            continue
                    
                    text_selectors = [
                        "div[data-testid='tweetText']",
                        "div[lang]"
                    ]
                    
                    text = "テキスト取得失敗"
                    for selector in text_selectors:
                        try:
                            elements = tweet.find_elements(By.CSS_SELECTOR, selector)
                            if elements:
                                text = elements[0].text
                                break
                        except:
                            continue
                    
                    date = "日付取得失敗"
                    try:
                        date_element = tweet.find_element(By.TAG_NAME, "time")
                        date = date_element.get_attribute("datetime")
                    except:
                        pass
                    
                    tweets.append({
                        "id": tweet_id,
                        "username": username,
                        "text": text,
                        "date": date
                    })
                    processed_ids.add(tweet_id)
                    logger.info(f"Tweet collected: {username}")
                    
                    if len(tweets) >= max_tweets:
                        break
                except Exception as e:
                    logger.error(f"Error processing tweet: {str(e)}")
                    continue
            
            if len(tweets) >= max_tweets:
                break
            
            current_position = driver.execute_script("return window.pageYOffset;")
            driver.execute_script("window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});")
            time.sleep(random.uniform(2, 4))
            
            new_position = driver.execute_script("return window.pageYOffset;")
            new_tweet_count = len(processed_ids)
            
            if new_position == current_position or new_tweet_count == len(processed_ids):
                scroll_attempts += 1
                logger.info(f"No new content: attempt {scroll_attempts}/{max_scroll_attempts}")
                
                if scroll_attempts >= max_scroll_attempts:
                    logger.info(f"Max scroll attempts reached. Saving collected data ({len(tweets)} tweets).")
                    save_interim_results(tweets, output_dir, timestamp)
            else:
                scroll_attempts = 0
                logger.info(f"New content found: {len(tweets)} tweets collected so far")
            
            if len(tweets) - tweets_count_at_last_save >= checkpoint_interval:
                save_checkpoint(tweets, processed_ids, new_position, checkpoint_file)
                save_interim_results(tweets, output_dir, timestamp)
                tweets_count_at_last_save = len(tweets)
                logger.info(f"Checkpoint saved with {len(tweets)} tweets")
    
    except Exception as e:
        logger.error(f"Error during scraping: {str(e)}")
        save_checkpoint(tweets, processed_ids, driver.execute_script("return window.pageYOffset;"), checkpoint_file)
        save_interim_results(tweets, output_dir, timestamp)
        logger.info(f"Emergency save completed with {len(tweets)} tweets")
    
    if os.path.exists(checkpoint_file):
        os.remove(checkpoint_file)
    
    return tweets

def main(search_result_url, max_scroll_attempts=2):
    logger = setup_logging()
    output_dir = "twitter_data"
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file = os.path.join(output_dir, f"results_{timestamp}.csv")
    json_file = os.path.join(output_dir, f"results_{timestamp}.json")
    
    driver = None
    
    try:
        logger.info("Initializing web driver")
        driver = initialize_driver()
        
        login_success = login_if_needed(driver, logger)
        if not login_success:
            logger.error("Login failed")
            return
        
        tweets = scrape_tweets(
            driver=driver,
            search_url=search_result_url,
            max_tweets=500,
            max_scroll_attempts=max_scroll_attempts,
            checkpoint_interval=10,
            logger=logger
        )
        
        if tweets:
            pd.DataFrame(tweets).to_csv(csv_file, index=False)
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(tweets, f, ensure_ascii=False, indent=4)
            
            logger.info(f"Completed: {len(tweets)} tweets saved to {csv_file} and {json_file}")
            
            # 中間ファイルのクリーンアップ
            interim_files = [f for f in os.listdir(output_dir) if f.startswith("interim_results_")]
            for file in interim_files:
                try:
                    os.remove(os.path.join(output_dir, file))
                    logger.info(f"Removed interim file: {file}")
                except:
                    logger.warning(f"Could not remove interim file: {file}")
        else:
            logger.warning("No tweets collected")
    except Exception as e:
        logger.error(f"Critical error: {str(e)}")
        if driver:
            current_url = driver.current_url
            logger.info(f"Last URL before error: {current_url}")
            
            # エラー発生時も中間結果を統合して保存
            all_tweets, _ = load_previous_results(output_dir)
            if all_tweets:
                emergency_file = os.path.join(output_dir, f"emergency_results_{timestamp}.csv")
                pd.DataFrame(all_tweets).to_csv(emergency_file, index=False)
                logger.info(f"Emergency save: {len(all_tweets)} tweets saved to {emergency_file}")
    finally:
        if driver:
            driver.quit()
            logger.info("Web driver closed")

if __name__ == "__main__":
    search_result_url_01 = "https://x.com/search?q=%E3%83%AA%E3%82%AF%E3%82%A4%E3%83%B3%20exia_vrc&src=typed_query&f=live"
    search_result_url_02 = "https://x.com/search?q=lang%3Aja%20(%E3%82%A4%E3%83%99%E3%83%B3%E3%83%88%20OR%20%E5%8F%82%E5%8A%A0%E6%96%B9%E6%B3%95%20OR%20%E5%8F%82%E5%8A%A0%E6%9D%A1%E4%BB%B6%20OR%20%E9%96%8B%E5%82%AC%20OR%20%E4%B8%BB%E5%82%AC%20OR%20join%20OR%20%E3%82%B8%E3%83%A7%E3%82%A4%E3%83%B3%20OR%20%E3%83%AA%E3%82%AF%E3%82%A4%E3%83%B3%20OR%20reqin%20OR%20%E3%83%AA%E3%82%AF%E3%82%A8%E3%82%B9%E3%83%88%E3%82%A4%E3%83%B3%E3%83%90%E3%82%A4%E3%83%88%20OR%20%22request%20invite%22%20OR%20%E6%9C%AC%E6%97%A5%20OR%20%E5%96%B6%E6%A5%AD%20OR%20%E5%BF%9C%E5%8B%9F)%20(VRChat%20OR%20VRC)%20min_retweets%3A3&src=typed_query"
    
    main(search_result_url=search_result_url_02, max_scroll_attempts=10)
