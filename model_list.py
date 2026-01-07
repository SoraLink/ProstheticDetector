import os
from google import genai

# === 配置 ===
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "key.json"
PROJECT_ID = "bamboo-magnet-483511-g8"
LOCATION = "us-central1"


def list_available_models():
    try:
        client = genai.Client(
            vertexai=True,
            project=PROJECT_ID,
            location=LOCATION
        )

        print(f"🔍 正在扫描 {LOCATION} 区域的所有可用模型...\n")

        # 获取迭代器
        all_models = client.models.list()

        print(f"{'MODEL ID (填入代码的值)':<50} | {'DISPLAY NAME'}")
        print("-" * 80)

        found_count = 0
        for m in all_models:
            # 新版 SDK 属性访问方式：直接取 name 和 display_name
            # 有些对象可能没有 display_name，做个容错
            m_name = getattr(m, 'name', 'Unknown ID').split('/')[-1]  # 去掉 'models/' 前缀
            m_display = getattr(m, 'display_name', 'No Display Name')

            # 关键词过滤
            if "gemini" in m_name.lower() or "imagen" in m_name.lower():
                print(f"{m_name:<50} | {m_display}")
                found_count += 1

        if found_count == 0:
            print("\n❌ 未找到包含 Gemini 或 Imagen 的模型。请检查 key.json 权限或 Region。")
        else:
            print(f"\n✅ 共找到 {found_count} 个模型。")
            print("请尝试寻找类似 'gemini-3.0-pro', 'gemini-experimental' 或 'imagen-3.0' 的名称。")

    except Exception as e:
        print(f"\n❌ 查询发生错误: {e}")
        # 打印一下 dir(m) 帮助调试（如果第一次循环就错了，这里可能打印不出来，但作为兜底）
        print("建议检查 Google Cloud Console 网页端以获取最准确列表。")


if __name__ == "__main__":
    list_available_models()