import os
import time
import re
import requests
from DrissionPage import ChromiumPage
from tqdm import tqdm

# --- 配置 ---
SAVE_DIR = 'Ins_Data'
if not os.path.exists(SAVE_DIR): os.makedirs(SAVE_DIR)


def download_file_with_bar(url, folder, name, desc="下载中"):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    file_path = os.path.join(folder, name)
    try:
        # Ins 的 CDN 链接通常不需要 Cookie 也能下，但有时效性
        response = requests.get(url, headers=headers, stream=True, timeout=20)
        total_size = int(response.headers.get('content-length', 0))
        if total_size < 100: return False

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
    return re.sub(r'[\\/:*?"<>|]', '_', text)[:50].strip()


def process_media_node(node, folder, index):
    """
    终极适配版：同时兼容 GraphQL 和 REST API 两种数据结构
    优先下载封面图/第一帧。
    """

    # --- 1. 定义一个内部函数来提取图片 URL ---
    def get_best_image_url(data):
        # 方式 A: GraphQL 结构 (display_url)
        if 'display_url' in data:
            return data['display_url']

        # 方式 B: REST API 结构 (image_versions2 -> candidates)
        if 'image_versions2' in data:
            candidates = data['image_versions2'].get('candidates', [])
            if candidates:
                # 通常第一个是最高清的
                return candidates[0].get('url')

        # 方式 C: 备用结构 (display_resources)
        if 'display_resources' in data:
            resources = data['display_resources']
            if resources:
                return resources[-1].get('src')  # 最后一个通常最大

        # 方式 D: 轮播图子节点 (carousel_parent_id)
        if 'candidates' in data:  # 有时直接就是 candidates
            return data['candidates'][0].get('url')

        return None

    # --- 2. 开始提取 ---
    img_url = get_best_image_url(node)

    # 调试日志：如果没找到，打印出来看看这到底是个什么东西
    if not img_url:
        print(f"   ⚠️ [调试] 节点 {index} 解析失败，可用键: {list(node.keys())}")
        # 如果你想看详细数据，取消下面这行的注释
        # print(node)
        return

    # --- 3. 确定文件名 (视频封面 vs 普通图片) ---
    is_video = node.get('is_video', False) or 'video_versions' in node

    if is_video:
        file_name = f"video_cover_{index}.jpg"
        desc = f"视频封面 {index}"

        # (可选) 顺便下载视频文件
        # 提取视频 URL 的逻辑也需要兼容
        video_url = node.get('video_url')
        if not video_url and 'video_versions' in node:
            v_versions = node.get('video_versions', [])
            if v_versions:
                video_url = v_versions[0].get('url')

        if video_url:
            download_file_with_bar(video_url, folder, f"video_{index}.mp4", desc=f"视频原片 {index}")

    else:
        file_name = f"img_{index}.jpg"
        desc = f"图片 {index}"

    # --- 4. 下载图片/封面 ---
    # print(f"   🖼️ 捕获图片: {desc}")
    download_file_with_bar(img_url, folder, file_name, desc=desc)


def start_ins_sniffer():
    page = ChromiumPage()

    # --- 【新增】就是缺了这一行 ---
    print("正在前往 Instagram...")
    page.get('https://www.instagram.com/explore/search/keyword/?q=%23prostheticarm')
    # ---------------------------

    # --- 核心：监听 Instagram 的 GraphQL 接口 ---
    page.listen.start(targets=['graphql', '/api/v1/media'])

    print("🚀 【Instagram 监听器】已启动！")

    # --- 核心：监听 Instagram 的 GraphQL 接口 ---
    # Ins 的网页端点击帖子时，通常会触发 graphql 请求获取详情
    # 或者 api/v1/media 相关的请求
    # 我们监听包含 'graphql' 或 'media' 的包
    page.listen.start(targets=['graphql', '/api/v1/media'])

    print("🚀 【Instagram 监听器】已启动！")
    print("------------------------------------------------")
    print("1. 请确保你的梯子已开启，且浏览器能访问 Ins。")
    print("2. 登录 Ins，搜索『prosthetics』(假肢) 或相关词。")
    print("3. 点击任意帖子进入详情弹窗，脚本自动下载。")
    print("------------------------------------------------")

    processed_ids = set()

    for packet in page.listen.steps():
        try:
            # 1. 解析响应
            try:
                # 有些包可能没有 body 或者不是 JSON
                response = packet.response.body
                if not isinstance(response, dict): continue
            except:
                continue

            # 2. 定位数据核心
            # Ins 的 JSON 结构很多变，通常是在 data -> shortcode_media 下
            data_node = response.get('data', {})
            media_data = None

            # 情况 A: 这是一个标准的详情页查询
            if 'shortcode_media' in data_node:
                media_data = data_node['shortcode_media']
            # 情况 B: 这是一个 items 列表 (通常在 timeline 中)
            elif 'items' in response:
                # 这种情况下通常包含多个，我们简化处理，只拿第一个
                if len(response['items']) > 0:
                    media_data = response['items'][0]

            if not media_data: continue

            # 3. 提取 ID 进行去重
            shortcode = media_data.get('shortcode') or media_data.get('code')
            if not shortcode or shortcode in processed_ids:
                continue

            # 4. 获取文案作为文件夹名
            edges = media_data.get('edge_media_to_caption', {}).get('edges', [])
            caption = "Untitled"
            if edges and len(edges) > 0:
                caption = edges[0].get('node', {}).get('text', '')
                caption = caption.replace('\n', ' ')[:30]  # 只取前30个字

            # 如果没有文案，用用户名
            if caption == "Untitled":
                owner = media_data.get('owner', {})
                caption = owner.get('username', 'UnknownUser')

            safe_title = clean_filename(caption)
            folder = os.path.join(SAVE_DIR, f"{shortcode}_{safe_title}")
            if not os.path.exists(folder): os.makedirs(folder)

            print(f"\n📸 捕获到 Ins 帖子: {shortcode}")
            processed_ids.add(shortcode)

            # --- 5. 核心下载逻辑 ---

            # 判断是否是“多图/轮播” (Sidecar)
            type_name = media_data.get('__typename') or media_data.get('media_type')

            # 如果包含 children (多图模式)
            if 'edge_sidecar_to_children' in media_data:
                children = media_data['edge_sidecar_to_children']['edges']
                print(f"   🖼️ 这是一个图集，包含 {len(children)} 个文件")
                for idx, child in enumerate(children):
                    node = child['node']
                    process_media_node(node, folder, idx + 1)

            # 如果是 carousel_media (API 变种)
            elif 'carousel_media' in media_data:
                children = media_data['carousel_media']
                print(f"   🖼️ 这是一个图集，包含 {len(children)} 个文件")
                for idx, node in enumerate(children):
                    process_media_node(node, folder, idx + 1)

            # 如果是单图或单视频
            else:
                process_media_node(media_data, folder, 1)

            print("✅ 处理完成")

        except Exception as e:
            # print(f"DEBUG Error: {e}")
            pass


if __name__ == '__main__':
    start_ins_sniffer()