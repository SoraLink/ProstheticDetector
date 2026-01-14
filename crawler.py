import os
import time
from icrawler.builtin import BaiduImageCrawler, BingImageCrawler


def start_crawling(keyword, max_num=500):
    # 创建保存路径，自动处理文件夹不存在的情况
    # 替换空格为下划线，避免文件夹名字有空格
    safe_keyword = keyword.replace(" ", "_")
    save_dir = os.path.join('.', 'dataset_raw', safe_keyword)

    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    print(f"=== 正在启动任务: {keyword} | 目标数量: {max_num} ===")

    # --- 1. Bing 爬虫 (通常是主力) ---
    try:
        print(f"  -> [Bing] 正在爬取...")
        bing_crawler = BingImageCrawler(
            downloader_threads=4,  # 4线程通常比较稳
            storage={'root_dir': save_dir},
            log_level='ERROR'  # 减少控制台刷屏，只显示错误
        )
        bing_crawler.crawl(
            keyword=keyword,
            filters=None,
            max_num=max_num,
            file_idx_offset='auto'  # 自动接着编号，防止覆盖
        )
    except Exception as e:
        print(f"  !! [Bing] 出错: {e}")

    # --- 2. Baidu 爬虫 (作为补充) ---
    # 如果觉得Bing够用了，可以把下面这段注释掉
    try:
        print(f"  -> [Baidu] 正在爬取...")
        baidu_crawler = BaiduImageCrawler(
            downloader_threads=4,
            storage={'root_dir': save_dir},
            log_level='ERROR'
        )
        baidu_crawler.crawl(
            keyword=keyword,
            max_num=max_num,
            file_idx_offset='auto'
        )
    except Exception as e:
        print(f"  !! [Baidu] 出错: {e}")

    print(f"=== {keyword} 完成. 休息 2 秒防止封IP ===\n")
    time.sleep(2)  # 简单的防封策略


if __name__ == '__main__':

    # 纯净版多语言关键词列表 (侧重生活化、时尚、日常)
    keywords = [
        # --- 中文 ---
        "残疾人 假肢 生活照", "穿戴假肢 行走",
        "下肢假肢 穿搭", "假肢 穿牛仔裤", "假肢 穿裙子",
        "上肢假肢 写字", "仿生手 拿东西",
        "假肢模特 街拍", "截肢 康复 走路",

        # --- English ---
        "amputee daily life", "person with prosthetic leg walking",
        "prosthetic arm working", "amputee cooking",
        "amputee fashion model", "prosthetic leg street style",
        "woman with prosthetic leg dress", "man with prosthetic leg shorts",
        "bionic arm user at home", "prosthetic limb casual wear",

        # --- Japanese ---
        "義足 私服", "義足 モデル",
        "義足 日常生活", "義手 働く", "切断 おしゃれ",

        # --- Korean ---
        "의족 패션", "의족 일상", "의수 착용",
        "절단 장애인 모델", "의족 스커트", "의족 반바지",

        # --- Traditional Chinese ---
        "穿戴義肢 生活", "截肢者 日常", "義肢 穿搭",
        "義肢 女孩", "科技義肢 行走", "截肢 復健 生活",

        # --- German ---
        "Beinprothese Alltag", "Armprothese greifen",
        "Menschen mit Prothese", "Prothese unter Kleidung",
        "Oberschenkelprothese gehen",

        # --- Spanish ---
        "vida diaria amputado", "mujer con prótesis",
        "hombre con prótesis caminando", "prótesis de pierna ropa casual",

        # --- Russian ---
        "протез ноги в быту", "девушка с протезом", "киберрука",

        # --- French ---
        "prothèse de jambe mode", "vivre avec une prothèse", "femme amputée rue",

        # --- Portuguese ---
        "vida de amputado", "mulher com prótese", "prótese perna dia a dia"
    ]

    # 全局设置：每个关键词爬 500 张
    IMAGES_PER_KEYWORD = 200

    print(f"即将开始爬取 {len(keywords)} 组关键词，每组 {IMAGES_PER_KEYWORD} 张...")

    for kw in keywords:
        start_crawling(kw, max_num=IMAGES_PER_KEYWORD)

    print("\n\n所有任务全部完成！请检查 dataset_raw 文件夹。")