import requests
from bs4 import BeautifulSoup
from helpers import init_all_loggers, get_main_bot_logger, get_error_logger, get_ban_logger
from database import get_all_blacklist_data, SessionLocal
from dotenv import load_dotenv
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

db = SessionLocal()
load_dotenv()
base_url = os.getenv("BASE_URL")

user_cookie_str = os.getenv("USER_COOKIE_STR")
mod_cookie_str = os.getenv("MOD_COOKIE_STR")
header = {"User-Agent": os.getenv("USER_AGENT")}


init_all_loggers("INFO")
main_logger = get_main_bot_logger()
error_logger = get_error_logger()
ban_logger = get_ban_logger()


def load_banned_keywords(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            keywords = [line.strip() for line in file if line.strip()]
            main_logger.debug(f"Loaded {len(keywords)} banned keywords from {filepath}")
            return keywords
    except Exception as e:
        error_logger.error(f"Error reading banned keywords from {filepath}: {e}")
        return []

def parse_cookies(cookie_str):
    cookies_list = cookie_str.split("; ")
    return {cookie.split("=", 1)[0]: cookie.split("=", 1)[1] for cookie in cookies_list}

def get_cookies():
    return parse_cookies(user_cookie_str)

def get_mod_cookies():
    return parse_cookies(mod_cookie_str)

def build_url(base_url, page, sorted_page=False):
    return f"{base_url}page-{page}?sort_key=start_date" if sorted_page else f"{base_url}page-{page}"


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
        # Extract User ID
        op_userid = soup.find('a', {'hovercard-id': True})['hovercard-id']

        # Extract number of posts and threads
        op_user_posts = int(soup.find_all('div', class_='pu-content')[0].get_text(strip=True).replace("Posts:", "").strip())
        op_user_threads = int(
            soup.find_all('div', class_='pu-content')[1].get_text(strip=True).replace("Threads:", "").strip()
        )

        # Extract metadata
        op_thread_title = soup.title.string.split(')', 1)[-1].strip() if soup.title.string.startswith('(') else soup.title.string
        op_thread_descriptions = soup.find('meta', {'name': 'description'}).get('content', '')
        op_thread_descriptions_full = soup.find('section', id='nulledPost').text.strip() if soup.find('section', id='nulledPost') else None
        hidden_contents = soup.find_all('div', class_='hiddencontent')
        op_thread_links = ', '.join(div.find('a', href=True)['href'] for div in hidden_contents if div.find('a', href=True)) if hidden_contents else ""
        op_thread_keywords = soup.find('meta', {'name': 'keywords'}).get('content', '')
        op_user_signature = soup.find("div", class_="signature").get_text(strip=True)

        # Extract reputation and likes if available
        op_reputation_div = soup.find('span', class_='x-smalltext', string='Rep')
        op_reputation = op_reputation_div.find_previous('strong').get_text(strip=True) if op_reputation_div else None
        op_likes_div = soup.find('span', class_='x-smalltext', string='Likes')
        op_likes = op_likes_div.find_previous('strong').get_text(strip=True) if op_likes_div else None

        # Extract group image URL and parse group name from it if available
        li_image_tag = soup.find('li', class_='group_icon').find('img')
        img_src = li_image_tag['src'] if li_image_tag else None
        op_group = img_src.split('/')[-1].replace('.png', '') if img_src else None
        ret = {
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
            "op_likes": op_likes,
            "op_group": op_group
        }
        return ret
    except Exception as e:
        error_logger.error(f"Error parsing thread info from URL {url}: {e}")
        return None


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


def monitor_forum_page(page_url, page):
    url = build_url(page_url, page, sorted_page=False)
    links = get_threads_section_info(url)

    blacklist_data = get_all_blacklist_data(db)
    for link in links:
        main_logger.info(f"Processing thread link: {link}")
        thread_info = get_internal_thread_info(link)

        if not thread_info:
            error_logger.warning(f"Thread info not available for link: {link}")
            continue

        if thread_info['op_group'] == "member":
            if thread_info["op_user_posts"] < 20 and thread_info["op_user_threads"] < 10:
                if int(thread_info['op_likes']) < 10:

                    # Ban user with blacklist descriptions.
                    for keyword in blacklist_data["descriptions"]:
                        if keyword.lower() in thread_info["op_thread_descriptions_full"].lower():
                            reason = f"Keyword '{keyword}' found in description."
                            ban_user_by_uid(thread_info["op_userid"], reason)

                    # Ban user with blacklist links.
                    for keyword in blacklist_data["links"]:
                        if keyword in thread_info["op_thread_links"]:
                            reason = f"Link '{keyword}' found in thread links."
                            ban_user_by_uid(thread_info["op_userid"], reason)

            # Ban user with blacklist title.
            if thread_info["op_user_posts"] < 5 and thread_info["op_user_threads"] < 5:
                for keyword in blacklist_data["titles"]:
                    if keyword in thread_info["op_thread_title"]:
                        reason = f"Keyword '{keyword}' found in title."
                        ban_user_by_uid(thread_info["op_userid"], reason)


def monitor_forum(max_threads=5, page_range=3, cycle_delay=120, stop_signal=None):
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
                    futures.append(executor.submit(monitor_forum_page, url, page))

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    error_logger.error(f"Error in thread execution: {e}")

        # Log the reload_param value (stop_signal state)
        reload_param = stop_signal() if stop_signal is not None else None
        ret = f"Checker cycle completed for all pages and URLs, reload_param: {reload_param}"
        if stop_signal is None or stop_signal():
            main_logger.info(f"{ret}, cycle_delay: {cycle_delay}s")
        else:
            main_logger.info(ret)

        # Delay before the next cycle
        time.sleep(cycle_delay)


if __name__ == "__main__":
    max_threads = 5
    page_range = 3
    cycle_delay = 120
    stop_signal = None

    monitor_forum(
        max_threads=max_threads,
        page_range=page_range,
        cycle_delay=cycle_delay,
        stop_signal=stop_signal
    )
