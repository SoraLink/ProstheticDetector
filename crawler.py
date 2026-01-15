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
        # ==========================================
        # 1. 核心词：强调“人”和“生活状态” (避免白底产品图)
        # ==========================================
        # --- English ---
        "upper limb amputee daily life",  # 上肢截肢者 日常
        "person with prosthetic arm",  # 带着假肢臂的人
        "woman with bionic arm",  # 戴仿生手的女性 (女性图片通常露肤度高，结构清晰)
        "man with prosthetic hand",  # 戴假肢手的男性
        "prosthetic arm selfie",  # 假肢自拍 (这种图通常距离近，细节好)
        "amputee arm model",  # 上肢模特

        # --- 中文 ---
        "上肢假肢 生活照",
        "断臂 假肢",
        "仿生手 佩戴",
        "机械手 假肢 帅气",  # “帅气”经常能搜到高质量的赛博朋克风真人照
        "独臂女孩 生活",
        "安装假肢手",

        # ==========================================
        # 2. 动作特写类 (Action - 非常适合训练手部抓取)
        # ==========================================
        "prosthetic hand holding cup",  # 假肢拿杯子
        "prosthetic hand typing",  # 假肢打字
        "prosthetic hand driving",  # 假肢开车
        "bionic hand gripping",  # 仿生手抓取
        "prosthetic arm eating",  # 用假肢吃饭
        "shaking hands with prosthesis",  # 握手 (交互场景)
        "義手 料理",  # (日) 义手 做饭
        "義手 書く",  # (日) 义手 写字

        # ==========================================
        # 3. 专业/解剖术语 (搜出来的图最精准)
        # ==========================================
        "trans-radial amputee",  # 前臂截肢 (最常见的手部假肢形态)
        "trans-humeral amputee",  # 上臂截肢 (包含肘关节)
        "below elbow prosthesis",  # 肘下假肢
        "above elbow prosthesis",  # 肘上假肢
        "body powered hook prosthesis",  # 机械挂钩 (这种很常见，必须包含，否则数据不全)
        "myoelectric hand user",  # 肌电手用户

        # ==========================================
        # 4. 多语言补充 (日/德/俄 - 手部假肢大国)
        # ==========================================
        # --- Japanese (日本的义手文化很强，很多漫画家/艺术家带义手) ---
        "義手 女子",  # 义手 女生
        "義手 製作",  # 义手 制作 (会有佩戴测试图)
        "能動義手",  # 机械义手 (那种带线缆的)
        "筋電義手",  # 肌电义手

        # --- German (德国Ottobock是老巢) ---
        "Armprothese Alltag",  # 手臂假肢 日常
        "Armamputation Prothese",  # 手臂截肢 假肢
        "bionische hand",  # 仿生手

        # --- Russian ---
        "бионическая рука",  # 仿生手臂
        "протез руки киберпанк"  # 手臂假肢 赛博朋克 (俄语圈很流行这种改装风格)
    ]

    # 全局设置：每个关键词爬 500 张
    IMAGES_PER_KEYWORD = 200

    print(f"即将开始爬取 {len(keywords)} 组关键词，每组 {IMAGES_PER_KEYWORD} 张...")

    for kw in keywords:
        start_crawling(kw, max_num=IMAGES_PER_KEYWORD)

    print("\n\n所有任务全部完成！请检查 dataset_raw 文件夹。")