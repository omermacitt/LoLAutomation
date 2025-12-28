import json
import re

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from lcu import lcu_request


def extract_selected_rune_ids(container):
    """
    From a 'relative box-border' container, find all
    'flex w-full justify-between' blocks and return the
    keystone-tooltip-XXXX ids whose img has opacity-100.
    """
    rune_ids = []

    flex_rows = container.find_elements(
        By.CSS_SELECTOR, "div.flex.w-full.justify-between"
    )

    for flex in flex_rows:
        choices = flex.find_elements(By.CSS_SELECTOR, "div.py-1.text-center")

        for choice in choices:
            cls = choice.get_attribute("class") or ""
            if "keystone-tooltip-" not in cls:
                continue

            try:
                img = choice.find_element(By.CSS_SELECTOR, "img")
            except Exception:
                continue

            img_cls = img.get_attribute("class") or ""
            if "opacity-100" not in img_cls:
                continue

            m = re.search(r"keystone-tooltip-(\d+)", cls)
            if m:
                rune_ids.append(m.group(1))

    return rune_ids


def extract_shard_ids(row):
    """
    In the shards area, selected shards have img src like
    .../perkShard/5005... and class containing opacity-100.
    Extract those numeric ids.
    """
    shard_ids = []

    imgs = row.find_elements(By.CSS_SELECTOR, "img[src*='perkShard/']")
    for img in imgs:
        img_cls = img.get_attribute("class") or ""
        if "opacity-100" not in img_cls:
            continue

        src = img.get_attribute("src") or ""
        m = re.search(r"perkShard/(\d+)", src)
        if m:
            shard_ids.append(m.group(1))

    return shard_ids


def get_all_champions_from_lcu() -> list[dict]:
    """
    LCU'dan tüm şampiyonları çeker.
    /lol-game-data/assets/v1/champion-summary.json
    """
    res = lcu_request("GET", "/lol-game-data/assets/v1/champion-summary.json")
    res.raise_for_status()
    return res.json()


def champion_slug(champion: dict) -> str:
    """
    OP.GG URL'inde kullanılacak champion slug'ı.
    Temel mantık: alias'ı lower() yapmak, bazı özel isimler için
    manuel map gerekirse buraya eklenebilir.
    """
    alias = (champion.get("alias") or champion.get("name") or "").strip()
    special = {
        "MonkeyKing": "wukong",
        "FiddleSticks": "fiddlesticks",
    }
    if alias in special:
        return special[alias]
    return alias.lower()


def scrape_runes_for_champion(driver: webdriver.Chrome, slug: str) -> dict:
    """
    Verilen champion slug'ı için OP.GG runes sayfasını
    scrape edip rune_X yapıları döndürür.
    """
    url = (
        f"https://op.gg/lol/champions/{slug}/runes/top"
        "?region=global&type=ranked&tier=emerald_plus&patch=15.23"
    )

    driver.get(url)

    base_xpath = (
        "/html/body/div[9]/main/div/div[2]/section/section[2]/div[2]/div/table/tbody/tr"
    )

    WebDriverWait(driver, 15).until(
        EC.presence_of_all_elements_located((By.XPATH, base_xpath))
    )

    rows = driver.find_elements(By.XPATH, base_xpath)

    result: dict[str, dict] = {}

    for i, row in enumerate(rows, start=1):
        lines = [l.strip() for l in row.text.splitlines() if l.strip()]

        primary = lines[0] if len(lines) > 0 else ""
        secondary = lines[1] if len(lines) > 1 else ""
        shards_label = lines[2] if len(lines) > 2 else "Shards"
        pick_rate = lines[3] if len(lines) > 3 else ""
        game_count = lines[4] if len(lines) > 4 else ""
        win_rate = lines[5] if len(lines) > 5 else ""

        containers = row.find_elements(
            By.CSS_SELECTOR, "div.relative.box-border"
        )

        primary_runes: list[str] = []
        secondary_runes: list[str] = []

        if len(containers) > 0:
            primary_runes = extract_selected_rune_ids(containers[0])
        if len(containers) > 1:
            secondary_runes = extract_selected_rune_ids(containers[1])

        shards_runes = extract_shard_ids(row)

        row_key = f"rune_{i}"
        result[row_key] = {
            primary: primary_runes,
            secondary: secondary_runes,
            shards_label: shards_runes,
            "Pick Rate": pick_rate,
            "Game Count": game_count,
            "Win Rate": win_rate,
        }

    return result


def scrape_all_champions():
    """
    LCU'dan tüm şampiyonları alır, her biri için OP.GG'den
    rune verisini çekip {champ_slug: {rune_1: {...}, ...}} döndürür
    ve JSON olarak yazdırır.
    """
    champions = get_all_champions_from_lcu()
    print("///////////////////////////////")
    print(champions)
    print("///////////////////////////////")
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    # chrome_options.add_argument("--headless=new")

    driver = webdriver.Chrome(options=chrome_options)

    all_result: dict[str, dict] = {}

    try:
        for champ in champions:
            print("**********************")
            print(champ)
            print("**********************")
            slug = champion_slug(champ)
            if not slug:
                continue
            print("slug: ", slug)
            print(f"Scraping runes for champion: {slug}")

            try:
                champ_result = scrape_runes_for_champion(driver, slug)
            except Exception as e:
                print(f"Failed to scrape {slug}: {e}")
                continue

            all_result[slug] = champ_result

        print(json.dumps(all_result, ensure_ascii=False, indent=2))
        with open("runes.json", "w", encoding="utf-8") as f:
            json.dump(all_result, f, ensure_ascii=False, indent=2)

        input("\nrunes.json oluşturuldu. Çıkmak için Enter'a bas...")
    finally:
        driver.quit()


if __name__ == "__main__":
    scrape_all_champions()

