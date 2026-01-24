import os

import instaloader
from datetime import datetime
from itertools import dropwhile, takewhile

# ================= 配置区 =================
# 建议注册一个小号专门用来爬，防止主号被风控限制
USER = "soral_ink"

# 这里填你要爬的标签 (去掉了 # 号)
# 这些标签下的图，全是你要的“真人+假肢+生活”
HASHTAGS = [
    "prostheticarm",  # 基础
    "bionicarm",  # 仿生/酷
    "amputee",  # 截肢者(量最大，需清洗)
    "amputeemodel",  # 模特(质量高)
    "amputeelife",  # 生活日常
    "adaptiveathlete",  # 运动/健身(身体线条清晰)
    "cyborg",  # 赛博朋克风(很多改装假肢)
    "transradial",  # 前臂截肢(针对手部)
]
YOUR_SESSION_ID = "80023077484%3AZmh4K7xqaUaxIz%3A26%3AAYgGCnzx9AondXHLdTMe3l8EzENBuy8QxUwyhz_ajg"
SAVE_ROOT = "/DATA/dataset_raw/instagram"
MAX_COUNT_PER_TAG = 500  # 每个标签爬多少张


# =========================================

def crawl_instagram():
    # 1. 初始化
    L = instaloader.Instaloader(
        download_pictures=True,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False
    )

    # 2. 登录 (强烈建议登录，否则爬不了几张就会报错 401/429)
    try:
        L.context._session.cookies.set("sessionid", YOUR_SESSION_ID, domain=".instagram.com")
        L.context.username = USER
        # 强制告诉程序“我已经登录了”
        L.context._is_logged_in = True

        print(f"✅ Cookie 注入成功，伪装身份: {USER}")
    except Exception as e:
        print(f"❌ 注入失败: {e}")
        return

    # 3. 开始循环爬取
    for tag in HASHTAGS:
        print(f"\n🚀 正在抓取标签: #{tag}")

        # 加载标签对象
        try:
            posts = instaloader.NodeIterator(
                L.context, "95b06a4663c3290b2e84835688d07399",  # 这是一个内部query hash，通常库会自动处理
                lambda d: d['data']['hashtag']['edge_hashtag_to_media'],
                lambda n: instaloader.Post(L.context, n),
                {'tag_name': tag},
                None
            )

            # 或者更简单的用法（推荐）：
            posts = instaloader.Hashtag.from_name(L.context, tag).get_posts()

            count = 0
            for post in posts:
                if count >= MAX_COUNT_PER_TAG:
                    break

                # 只要图片，不要视频
                if not post.is_video:
                    # 下载
                    # target=SAVE_ROOT/tag 这样会自动分文件夹
                    L.download_post(post, target=f"{tag}_images")
                    count += 1
                    print(f"  [{count}/{MAX_COUNT_PER_TAG}] 下载: {post.shortcode}")

        except Exception as e:
            print(f"  !! 抓取 #{tag} 时出错: {e}")
            continue


if __name__ == "__main__":
    crawl_instagram()