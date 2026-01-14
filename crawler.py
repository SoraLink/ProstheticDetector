import os
from icrawler.builtin import BaiduImageCrawler, BingImageCrawler


def start_crawling(keyword, max_num=100):
    # 创建保存路径
    save_dir = f'./dataset_raw/{keyword}'
    if not os.path.join(save_dir):
        os.makedirs(save_dir, exist_ok=True)

    print(f"=== 开始爬取关键词: {keyword} ===")

    # --- 1. 使用 Bing 爬虫 (通常质量较高) ---
    print(f"正在从 Bing 爬取 {keyword}...")
    bing_crawler = BingImageCrawler(
        downloader_threads=2,  # 线程数
        storage={'root_dir': save_dir}
    )
    bing_crawler.crawl(
        keyword=keyword,
        filters=None,
        max_num=max_num,
        file_idx_offset=0
    )

    # --- 2. 使用 百度 爬虫 (作为补充) ---
    # 注意：为了避免文件名冲突，这里可以设置不同的offset或单独文件夹，
    # 但icrawler通常会自动重命名避免覆盖，或者你可以分两个文件夹存。
    print(f"正在从 Baidu 爬取 {keyword}...")
    baidu_crawler = BaiduImageCrawler(
        downloader_threads=2,
        storage={'root_dir': save_dir}
    )
    baidu_crawler.crawl(
        keyword=keyword,
        max_num=max_num,
        file_idx_offset='auto'  # 自动接着编号
    )


if __name__ == '__main__':
    # 核心策略：关键词多样化
    # 单一的"假肢"会爬到很多假肢产品的电商白底图，这不是你想要的。
    # 你需要的是"人戴着假肢"的场景图。

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

    # 每个关键词爬取的数量
    images_per_keyword = 500

    for kw in keywords:
        try:
            start_crawling(kw, max_num=images_per_keyword)
        except Exception as e:
            print(f"爬取 {kw} 时发生错误: {e}")
            continue

    print("=== 所有爬取任务完成 ===")