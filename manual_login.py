import instaloader

# ==========================================
# 🔴 把你从浏览器 F12 里复制的 sessionid 填在这里
# ==========================================
YOUR_SESSION_ID = "80023077484%3AZmh4K7xqaUaxIz%3A26%3AAYgGCnzx9AondXHLdTMe3l8EzENBuy8QxUwyhz_ajg"
USERNAME = "soral_ink"


# ==========================================

def create_session_manually():
    print(f"🔧 正在手动构建 {USERNAME} 的 Session 文件...")

    L = instaloader.Instaloader()

    # 强行注入 Session ID，绕过所有密码验证和浏览器读取
    L.context._session.cookies.set("sessionid", YOUR_SESSION_ID, domain=".instagram.com")
    L.context.username = USERNAME

    try:
        # 测试一下是否生效
        print("正在连接 Instagram 验证...")
        profile = instaloader.Profile.from_username(L.context, USERNAME)
        print(f"✅ 成功！已识别用户: {profile.userid}")

        # 保存为文件，以后就不用再操作了
        filename = f"session-{USERNAME}"
        L.save_session_to_file(filename=filename)
        print(f"💾 Session 文件已生成: {filename}")
        print("👉 现在你可以直接运行之前的爬虫代码了，它会自动读取这个文件。")

    except Exception as e:
        print(f"❌ 失败: {e}")
        print("请检查你的 sessionid 是否复制完整，或者是否已经过期。")


if __name__ == "__main__":
    create_session_manually()