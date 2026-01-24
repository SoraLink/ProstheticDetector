import os
import time
import shutil  # 用于移动文件
import requests
from icrawler.builtin import BaiduImageCrawler, BingImageCrawler
from selenium import webdriver
from selenium.common import StaleElementReferenceException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from simple_image_download import simple_image_download
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

# ================= 配置区 =================
# 图片保存根目录
ROOT_DIR = '/DATA/dataset_raw'
# 每个引擎最大下载数 (全局统一控制)
MAX_NUM = 500


# =========================================

def start_crawling(keyword, driver):
    # 1. 准备路径 (空格转下划线)
    safe_keyword = keyword.replace(" ", "_")
    save_dir = os.path.join(ROOT_DIR, safe_keyword)

    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    print(f"\n{'=' * 30}\n🚀 启动任务: [{keyword}]\n📂 目标路径: {save_dir}\n{'=' * 30}")

    # --- 1. Bing 爬虫 ---
    try:
        print(f"  -> [Bing] 正在搜索...")
        bing_crawler = BingImageCrawler(
            downloader_threads=4,
            storage={'root_dir': save_dir},
            log_level='ERROR'
        )
        bing_crawler.crawl(
            keyword=keyword,
            max_num=MAX_NUM,  # 这里用了 MAX_NUM
            file_idx_offset='auto'
        )
    except Exception as e:
        print(f"  !! [Bing] 出错: {e}")

    # --- 2. Baidu 爬虫 ---
    try:
        print(f"  -> [Baidu] 正在搜索...")
        baidu_crawler = BaiduImageCrawler(
            downloader_threads=4,
            storage={'root_dir': save_dir},
            log_level='ERROR'
        )
        baidu_crawler.crawl(
            keyword=keyword,
            max_num=MAX_NUM,  # 这里用了 MAX_NUM
            file_idx_offset='auto'
        )
    except Exception as e:
        print(f"  !! [Baidu] 出错: {e}")

    # --- 3. Google 爬虫 ---
    # try:
    #     print(f"  -> [Google] 正在搜索...")
    #     downloader = simple_image_download.simple_image_download
    #
    #     # 下载 (使用 MAX_NUM)
    #     downloader().download(keyword, limit=MAX_NUM)
    #
    #     # 移动并改名
    #     src_dir = os.path.join(os.getcwd(), 'simple_images', keyword)
    #
    #     if os.path.exists(src_dir):
    #         print(f"  -> [Google] 正在移动并重命名文件...")
    #         files = os.listdir(src_dir)
    #         for f in files:
    #             src_file = os.path.join(src_dir, f)
    #             dst_file = os.path.join(save_dir, f"google_{f}")
    #             shutil.move(src_file, dst_file)
    #
    #         shutil.rmtree(src_dir)
    #         try:
    #             shutil.rmtree(os.path.join(os.getcwd(), 'simple_images'))
    #         except:
    #             pass
    #     else:
    #         print(f"  ⚠️ [Google] 未找到临时目录，请手动检查")
    #
    # except Exception as e:
    #     print(f"  !! [Google] 出错: {e}")

    # --- 4. Pinterest 爬虫 ---
    try:
        print(f"  -> [Pinterest] 正在搜索...")
        driver.get(f"https://www.pinterest.com/search/pins/?q={keyword}")
        time.sleep(5)

        image_urls = set()  # 用集合去重，存的全是字符串(URL)，字符串永远不会过期
        print("     正在采集图片链接...")

        # 动态计算滚动次数
        scroll_times = int(MAX_NUM / 10) + 10

        for s in range(scroll_times):
            # 1. 如果已经抓够了，直接跳出循环，不再浪费时间滚动
            if len(image_urls) >= MAX_NUM:
                print(f"     ✅ 链接收集完毕 ({len(image_urls)}个)，停止滚动。")
                break

            # 2. 滚动页面
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # 稍微快一点

            # 3. 【核心修改】抓到一个是一个，立刻提取字符串
            try:
                imgs = driver.find_elements(By.TAG_NAME, "img")
                for img in imgs:
                    try:
                        # 拿到 src 字符串立刻存起来，不要保留 img 对象
                        src = img.get_attribute("src")
                        if src and "236x" in src:
                            hd_src = src.replace("236x", "564x")  # 换成高清图
                            image_urls.add(hd_src)

                        # 如果这一个循环里已经够了，也可以提前停
                        if len(image_urls) >= MAX_NUM:
                            break
                    except StaleElementReferenceException:
                        # 如果这个元素刚好过期了，直接跳过看下一个，绝不报错
                        continue
            except:
                pass

            # 实时显示进度
            if s % 2 == 0:
                print(f"     已锁定链接: {len(image_urls)} / {MAX_NUM}")

        # --- 4. 批量下载 (这是最稳的，因为链接都在手上了，哪怕断网都不怕丢进度) ---
        print(f"     📥 [Pinterest] 开始极速下载 {min(len(image_urls), MAX_NUM)} 张...")

        download_count = 0
        for i, url in enumerate(list(image_urls)):
            if download_count >= MAX_NUM:
                break

            try:
                # 给个3秒超时，下不动就跳过，保证速度
                resp = requests.get(url, timeout=3)
                if resp.status_code == 200:
                    file_name = f"pin_{i}.jpg"
                    file_path = os.path.join(save_dir, file_name)
                    with open(file_path, 'wb') as f:
                        f.write(resp.content)
                    download_count += 1
            except:
                pass

        print(f"     [Pinterest] 实际下载成功: {download_count} 张")

    except Exception as e:
        print(f"  !! [Pinterest] 出错: {e}")

    print(f"✅ {keyword} 处理完成.\n")
    time.sleep(1)


if __name__ == '__main__':

    # 你的关键词列表
    english_keywords = [
        "person with prosthetic arm",
        "upper limb amputee",
        "woman with prosthetic arm",
        "man with prosthetic arm",
        "prosthetic arm user",
        "wearing a prosthetic arm",
        "person with bionic arm",
        "amputee arm model",
        "person with artificial arm",
    ]

    other_languages_map = {
        "zh": ["戴假肢的人", "戴假肢的男性", "戴假肢的女性", "佩戴上肢假肢", "戴仿生手的人"],
        "fr": ["personne avec une prothèse de bras", "homme avec une prothèse de bras",
               "femme avec une prothèse de bras", "portant une prothèse de bras", "personne avec un bras bionique"],
        "uk": ["людина з протезом руки", "чоловік з протезом руки", "жінка з протезом руки", "носити протез руки",
               "людина з біонічним протезом"],
        "ja": ["義手の人", "義手の男性", "義手の女性", "義手を装着している", "バイオニックアームの人"],
        "ru": ["человек с протезом руки", "мужчина с протезом руки", "женщина с протезом руки", "ношение протеза руки",
               "человек с бионической рукой"],
        "de": ["Person mit Armprothese", "Mann mit Armprothese", "Frau mit Armprothese", "Armprothese tragen",
               "Person mit bionischem Arm"],
        "es": ["persona con prótesis de brazo", "hombre con prótesis de brazo", "mujer con prótesis de brazo",
               "usando prótesis de brazo", "persona con brazo biónico"]
    }

    search_keywords = []
    search_keywords.extend(english_keywords)
    for lang, words in other_languages_map.items():
        search_keywords.extend(words)

    # 浏览器配置
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")

    print(f"即将开始爬取 {len(search_keywords)} 组关键词，每组目标 {MAX_NUM} 张...")

    driver = None
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

        for kw in search_keywords:
            start_crawling(kw, driver)

        driver.quit()
        print("\n🎉🎉 所有任务全部完成！请检查 /DATA/dataset_raw 文件夹。")

    except Exception as e:
        print(f"❌ 浏览器或主程序出错: {e}")