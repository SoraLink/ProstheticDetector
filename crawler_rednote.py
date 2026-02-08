import os
import time
import re
import requests
from DrissionPage import ChromiumPage
from tqdm import tqdm

# --- 配置 ---
SAVE_DIR = 'XHS_Manual_Selected'
if not os.path.exists(SAVE_DIR): os.makedirs(SAVE_DIR)


def download_file_with_bar(url, folder, name, desc="下载中"):
    """带进度条的下载工具"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.xiaohongshu.com/'
    }
    file_path = os.path.join(folder, name)
    try:
        response = requests.get(url, headers=headers, stream=True, timeout=20)
        total_size = int(response.headers.get('content-length', 0))
        # 如果文件小于 1KB，可能是假文件
        if total_size < 1000: return False

        with tqdm(total=total_size, unit='iB', unit_scale=True, desc=desc, ncols=80) as bar:
            with open(file_path, 'wb') as file:
                for data in response.iter_content(1024):
                    bar.update(len(data))
                    file.write(data)
        return True
    except Exception as e:
        print(f"   ❌ 下载失败: {e}")
        return False


def clean_filename(text):
    """清洗文件名，防止 Windows 报错"""
    return re.sub(r'[\\/:*?"<>|]', '_', text)[:50]  # 限制长度防止溢出


def start_sniffer():
    page = ChromiumPage()

    # --- 核心：开启数据包监听 ---
    # 我们只监听包含 'web/v1/feed' 的数据包，这是小红书加载笔记详情的 API
    page.listen.start('web/v1/feed')

    print("🚀 【监听模式】辅助程序已启动！")
    print("------------------------------------------------")
    print("操作指南：")
    print("1. 在浏览器搜索『假肢』，必须先登录！")
    print("2. 随意点击你感兴趣的笔记（点开弹窗）。")
    print("3. 程序会自动捕获数据包并下载，不需要等页面渲染。")
    print("------------------------------------------------")

    # 记录已处理的笔记 ID，防止重复下载同一篇
    processed_ids = set()

    # 循环监听网络流
    for packet in page.listen.steps():
        try:
            # 获取数据包中的 JSON 内容
            response = packet.response.body

            # 确保数据结构正确
            if not isinstance(response, dict) or 'data' not in response:
                continue

            items = response.get('data', {}).get('items', [])
            if not items: continue

            # 通常点击一个笔记，API 会返回这个笔记的详细信息
            for item in items:
                # 提取核心数据
                note_card = item.get('note_card', {})
                note_id = item.get('id') or item.get('note_id')

                # 如果这个 ID 已经处理过，或者是无效数据，跳过
                if not note_id or note_id in processed_ids:
                    continue

                title = note_card.get('title', '无标题')
                user_name = note_card.get('user', {}).get('nickname', '未知作者')
                desc = note_card.get('desc', '')  # 如果你需要文字描述，可以在这里保存

                print(f"\n📡 捕获到笔记: [{title}] - 作者: {user_name}")

                # 创建文件夹
                safe_title = clean_filename(title)
                folder = os.path.join(SAVE_DIR, f"{note_id}_{safe_title}")
                if not os.path.exists(folder): os.makedirs(folder)

                processed_ids.add(note_id)  # 标记为已处理

                # --- 1. 处理视频 ---
                # 在 JSON 里，视频地址通常是 masterUrl，绝对不是 blob
                video_info = note_card.get('video', {})
                media_info = video_info.get('media', {}).get('stream', {}).get('h264', [])

                if media_info:
                    # 获取最高清晰度 (masterUrl)
                    video_url = media_info[0].get('masterUrl')
                    if video_url:
                        print(f"   🎥 发现视频，开始下载...")
                        download_file_with_bar(video_url, folder, "video.mp4", desc="视频进度")

                # --- 2. 处理图片 ---
                image_list = note_card.get('image_list', [])
                if image_list:
                    print(f"   🖼️ 发现 {len(image_list)} 张图片...")
                    for idx, img in enumerate(image_list):
                        # 优先尝试获取原图 URL (通常在 info_list 或 url_default)
                        img_url = img.get('url_default', '') or img.get('url', '')

                        # 小红书原图 trick: 确保 url 指向高清
                        if 'spectrum' in img_url:
                            # 有时候 JSON 里的 url 是压缩过的，这里不做替换也行，通常 API 返回的已经很清楚了
                            pass

                        if img_url:
                            download_file_with_bar(img_url, folder, f"img_{idx}.jpg", desc=f"图 {idx + 1}")

                print(f"✅ 处理完成！请继续点击下一个。")

        except Exception as e:
            # 忽略一些解析错误，保持程序运行
            # print(e)
            pass


if __name__ == '__main__':
    start_sniffer()