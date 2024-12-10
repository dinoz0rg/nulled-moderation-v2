import requests
from bs4 import BeautifulSoup
from helpers import init_all_loggers, get_main_bot_logger, get_error_logger, get_ban_logger
from concurrent.futures import ThreadPoolExecutor, as_completed
from database import get_all_blacklist_data, SessionLocal
from dotenv import load_dotenv
import yaml
import os
import time
import sys

# Initialize database and environment variables
db = SessionLocal()
load_dotenv(dotenv_path=os.path.join('config', '.env'))
base_url = os.getenv("BASE_URL")

user_cookie_str = os.getenv("USER_COOKIE_STR")
mod_cookie_str = os.getenv("MOD_COOKIE_STR")
header = {"User-Agent": os.getenv("USER_AGENT")}

# Initialize loggers
init_all_loggers("INFO")
main_logger = get_main_bot_logger()
error_logger = get_error_logger()
ban_logger = get_ban_logger()

# Load YAML rules
def load_rules_from_yaml(filepath="config/rules.yaml"):
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)
    except Exception as e:
        error_logger.error(f"Error reading YAML rules from {filepath}: {e}")
        return {}

# Parse cookies from a string
def parse_cookies(cookie_str):
    cookies_list = cookie_str.split("; ")
    return {cookie.split("=", 1)[0]: cookie.split("=", 1)[1] for cookie in cookies_list}

def get_cookies():
    return parse_cookies(user_cookie_str)

def get_mod_cookies():
    return parse_cookies(mod_cookie_str)

# Build forum page URL
def build_url(base_url, page, sorted_page=False):
    return f"{base_url}page-{page}?sort_key=start_date" if sorted_page else f"{base_url}page-{page}"

# Fetch thread links from a forum page
def get_threads_section_info(url):
    main_logger.debug(f"Fetching threads from URL: {url}")
    try:
        response = requests.get(url, cookies=get_cookies(), headers=header)
        response.raise_for_status()
    except requests.RequestException as e:
        error_logger.error(f"Error fetching threads from URL {url}: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    threads = soup.find_all("td", class_="col_f_content")
    thread_links = []

    for thread in threads:
        if thread.find('s'):
            main_logger.debug("Strikethrough user found, skipping this thread.")
            continue

        username_element = thread.find("a", {"hovercard-ref": "member"})
        if not username_element:
            main_logger.debug("Username element missing in thread; skipping.")
            continue

        thread_link_element = thread.find("a", class_="topic_title highlight_unread")
        if thread_link_element:
            thread_links.append(thread_link_element["href"])
            main_logger.debug(f"Thread link found: {thread_link_element['href']}")

    return thread_links

# Fetch thread details
def get_internal_thread_info(url):
    main_logger.debug(f"Fetching internal thread info from URL: {url}")
    try:
        response = requests.get(url, cookies=get_mod_cookies(), headers=header)
        response.raise_for_status()
    except requests.RequestException as e:
        error_logger.error(f"Error fetching internal thread info from URL {url}: {e}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    try:
        op_userid = soup.find('a', {'hovercard-id': True})['hovercard-id']
        op_user_posts = int(soup.find_all('div', class_='pu-content')[0].get_text(strip=True).replace("Posts:", "").strip())
        op_user_threads = int(soup.find_all('div', class_='pu-content')[1].get_text(strip=True).replace("Threads:", "").strip())
        op_thread_title = soup.title.string
        op_thread_descriptions = soup.find('meta', {'name': 'description'}).get('content', '')
        op_thread_descriptions_full = soup.find('section', id='nulledPost').text.strip() if soup.find('section', id='nulledPost') else None
        op_thread_links = ', '.join(div.find('a', href=True)['href'] for div in soup.find_all('div', class_='hiddencontent') if div.find('a', href=True)) if soup.find_all('div', class_='hiddencontent') else ""
        op_thread_keywords = soup.find('meta', {'name': 'keywords'}).get('content', '')
        op_user_signature = soup.find("div", class_="signature").get_text(strip=True) if soup.find("div", class_="signature") else ""
        op_reputation = soup.find('span', class_='x-smalltext', string='Rep').find_previous('strong').get_text(strip=True) if soup.find('span', class_='x-smalltext', string='Rep') else None
        op_likes = soup.find('span', class_='x-smalltext', string='Likes').find_previous('strong').get_text(strip=True) if soup.find('span', class_='x-smalltext', string='Likes') else 0
        op_group = soup.find('li', class_='group_icon').find('img')['src'].split('/')[-1].replace('.png', '') if soup.find('li', class_='group_icon') and soup.find('li', class_='group_icon').find('img') else None

        return {
            "op_thread_url": url,
            "op_userid": op_userid,
            "op_user_posts": op_user_posts,
            "op_user_threads": op_user_threads,
            "op_thread_title": op_thread_title,
            "op_thread_descriptions": op_thread_descriptions,
            "op_thread_descriptions_full": op_thread_descriptions_full,
            "op_thread_links": op_thread_links,
            "op_thread_keywords": op_thread_keywords,
            "op_user_signature": op_user_signature,
            "op_reputation": op_reputation,
            "op_likes": int(op_likes),
            "op_group": op_group
        }
    except Exception as e:
        error_logger.error(f"Error parsing thread info from URL {url}: {e}")
        return None

# Evaluate rule conditions
def evaluate_conditions(thread_info, conditions):
    for field, condition in conditions.items():
        operator, value = condition.split()
        if not eval(f"{thread_info[field]} {operator} {value}"):
            return False
    return True

# Match blacklist fields
def field_match(field, keyword, thread_info):
    if field == "descriptions":
        return keyword.lower() in thread_info.get("op_thread_descriptions_full", "").lower()
    elif field == "links":
        return keyword in thread_info.get("op_thread_links", "")
    elif field == "titles":
        return keyword in thread_info.get("op_thread_title", "")
    return False

# Ban a user by user ID
def ban_user_by_uid(user_uid, reason):
    ban_url = f'{base_url}/misc.php?action=banMemberAndDeleteAllPosts&id={user_uid}'
    main_logger.debug(f"Attempting to ban user with ID: {user_uid}")
    try:
        response = requests.get(ban_url, cookies=get_mod_cookies(), headers=header)
        if response.ok:
            ban_logger.info(f"User banned successfully: {user_uid}, reason: {reason}")
            return True
        else:
            error_logger.error(f"Failed to ban user {user_uid}: {response.status_code}")
            return False
    except Exception as e:
        error_logger.error(f"Exception occurred during banning user {user_uid}: {e}")
        return False

# Monitor a single forum page
def monitor_forum_page(page_url, page, rules_config_path="config/rules.yaml"):
    rules = load_rules_from_yaml(rules_config_path).get("rules", [])
    url = build_url(page_url, page, sorted_page=True)
    links = get_threads_section_info(url)

    blacklist_data = get_all_blacklist_data(db)

    for link in links:
        main_logger.info(f"Processing thread link: {link}")
        thread_info = get_internal_thread_info(link)

        if not thread_info:
            error_logger.warning(f"Thread info not available for link: {link}")
            continue

        for rule in rules:
            if thread_info['op_group'] == rule["op_group"]:
                if evaluate_conditions(thread_info, rule["conditions"]):
                    for field in rule["blacklist_fields"]:
                        keywords = blacklist_data.get(field, [])
                        for keyword in keywords:
                            if field_match(field, keyword, thread_info):
                                reason = f"Keyword '{keyword}' found in {field} - {link}."
                                ban_user_by_uid(thread_info["op_userid"], reason)

# Monitor forum pages in cycles
def monitor_forum(max_threads=5, page_range=3, cycle_delay=120, stop_signal=None, rules_config_path="config/rules.yaml"):
    rules = load_rules_from_yaml(rules_config_path)
    if not rules:
        sys.exit("Terminating program due to missing or invalid rules.yaml file.")

    pages_url = [
        "/forum/70-monetizing-techniques/",
        "/forum/9-tutorials-guides-ebooks-etc/",
        "/forum/43-accounts/",
        "/forum/74-combolists/",
        "/forum/15-other-leaks/",
        "/forum/7-cracked-programs/",
        "/forum/90-cracking-tools/",
        "/forum/195-service-requests/"
    ]

    main_logger.info("Checker started.")
    while stop_signal is None or stop_signal():
        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            futures = []
            for page_url in pages_url:
                for page in range(1, page_range + 1):
                    url = base_url + page_url
                    futures.append(executor.submit(monitor_forum_page, url, page, rules_config_path))

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    error_logger.error(f"Error in thread execution: {e}")

        main_logger.info("Checker cycle completed. Delaying before next cycle.")
        time.sleep(cycle_delay)

if __name__ == "__main__":
    max_threads = 5
    page_range = 3
    cycle_delay = 120
    stop_signal = None
    rules_config_path = "config/rules.yaml"

    monitor_forum(
        max_threads=max_threads,
        page_range=page_range,
        cycle_delay=cycle_delay,
        stop_signal=stop_signal,
        rules_config_path=rules_config_path
    )
