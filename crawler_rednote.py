import os
import time
import random
import requests
import pandas as pd
from DrissionPage import ChromiumPage

# --- 配置区 ---
KEYWORD = '戴假肢'
TARGET_COUNT = 1000
SAVE_DIR = 'XHS_Data'


class XHSSpider:
    def __init__(self):
        self.page = ChromiumPage()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.xiaohongshu.com/'
        }
        if not os.path.exists(SAVE_DIR): os.makedirs(SAVE_DIR)

    def download(self, url, folder, name):
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            if res.status_code == 200:
                with open(os.path.join(folder, name), 'wb') as f:
                    f.write(res.content)
        except:
            pass

    def get_list(self):
        print(f"开始搜索关键词: {KEYWORD}")
        self.page.get(f'https://www.xiaohongshu.com/search_result?keyword={KEYWORD}')

        # 核心修改：等待页面首批数据加载出来，超时时间15秒
        if self.page.wait.ele_displayed('.note-item', timeout=15):
            print("页面加载成功，开始提取...")
        else:
            print("页面加载超时，请检查是否需要扫码登录或网络是否通畅")
            return []

        note_urls = set()
        while len(note_urls) < TARGET_COUNT:
            # 获取当前所有笔记卡片
            items = self.page.eles('.note-item')

            for item in items:
                try:
                    # 增加判断：只有找到 a 标签才提取 href
                    a_target = item.ele('tag:a', timeout=2)  # 缩短单个查找超时
                    if a_target:
                        link = a_target.attr('href')
                        if link and 'explore' in link:  # 确保是笔记链接
                            note_urls.add(link)
                except Exception:
                    continue  # 某个卡片坏了就跳过，不报错

                if len(note_urls) >= TARGET_COUNT: break

            print(f"已收集链接: {len(note_urls)} / {TARGET_COUNT}")

            # 滚动并等待新内容加载
            self.page.scroll.to_bottom()
            time.sleep(random.uniform(2, 4))

            # 检查是否有滑动验证码
            if self.page.ele('text=验证码'):
                print("检测到验证码，请在浏览器中手动完成！")
                while self.page.ele('text=验证码'):
                    time.sleep(2)

        return list(note_urls)

    def parse_and_download(self, url):
        """第二步：进入详情页下载媒体资源"""
        self.page.get(url)
        time.sleep(random.uniform(2, 4))

        try:
            title = self.page.ele('.title').text[:15] or "未命名"
            note_id = url.split('/')[-1]
            folder = os.path.join(SAVE_DIR, f"{note_id}_{title}")
            if not os.path.exists(folder): os.makedirs(folder)

            # 解析视频
            video = self.page.ele('tag:video')
            if video:
                v_url = video.attr('src')
                print(f"下载视频: {title}")
                self.download(v_url, folder, "video.mp4")

            # 解析图片
            imgs = self.page.eles('.pic')
            for i, img in enumerate(imgs):
                i_url = img.attr('src')
                if i_url:
                    self.download(i_url, folder, f"img_{i}.jpg")
        except Exception as e:
            print(f"解析失败: {url}, 错误: {e}")

    def run(self):
        urls = self.get_list()
        for i, url in enumerate(urls):
            print(f"正在处理第 {i + 1}/{len(urls)} 个笔记...")
            self.parse_and_download(url)
            # 每下载5个休息一下，防止封IP
            if i % 5 == 0: time.sleep(random.uniform(5, 10))


# --- 启动 ---
if __name__ == '__main__':
    spider = XHSSpider()
    spider.run()