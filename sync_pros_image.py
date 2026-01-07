import os
import time
import io
import mimetypes
from pathlib import Path
from PIL import Image

# Google GenAI SDK (v1 beta/newer)
from google import genai
from google.genai import types

# === 配置区域 ===
# 建议将 Key 放在环境变量中，或者临时贴在这里 (Vertex AI 需要配置 Service Account json)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "key.json"

# 填入你的 Project ID
PROJECT_ID = "bamboo-magnet-483511-g8"
LOCATION = "global"

# 定义你的文件夹路径
SOURCE_DIR = "./ldpose_final/sync/source"  # 假肢图
TARGET_DIR = "./ldpose_final/sync/target"  # 底图（人）
OUTPUT_DIR = "./ldpose_final/sync/output"  # 结果

# 支持的图片扩展名
VALID_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff'}


def get_mime_type(file_path):
    """获取文件的 MIME 类型，默认为 image/jpeg"""
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type if mime_type else "image/jpeg"


def transfer_prosthetic_arm(client, source_path, target_path, output_path):
    try:
        # 1. 以二进制读取图片，避免 PIL 转换带来的兼容性问题
        with open(source_path, 'rb') as f:
            source_bytes = f.read()
        with open(target_path, 'rb') as f:
            target_bytes = f.read()

        source_mime = get_mime_type(source_path)
        target_mime = get_mime_type(target_path)

    except Exception as e:
        print(f"读取图片文件失败: {e}")
        return

    # 2. 构建 Prompt
    # 使用 types.Part.from_bytes 显式传入图片数据
    contents_list = [
        # --- 步骤 1: 源图片 (多人场景) ---
        "Step 1: Analyze the first image (Image A) below.",
        "Attention: This image may contain multiple people.",
        "Task: IGNORE all people with natural biological arms.",
        "LOCATE the ONLY person wearing a prosthetic/bionic arm.",
        "Extract the visual details (color, mechanical joints, material) of that specific prosthetic arm as our reference source.",
        types.Part.from_bytes(data=source_bytes, mime_type=source_mime),

        # --- 步骤 2: 目标图片 (基底) ---
        "Step 2: Analyze the second image (Image B) below. This is our target base. Keep this person's pose and background exactly as is.",
        types.Part.from_bytes(data=target_bytes, mime_type=target_mime),

        # --- 步骤 3: 最终指令 ---
        "Final Task: Generate a fused image based on Image B.",
        "Execution Rules:",
        "1. Source Selection: Using ONLY the prosthetic arm identified in Step 1 (from Image A).",
        "2. Target Application: Replace the arm of the person in Image B with that specific prosthetic arm.",
        "3. Blending: Ensure the prosthetic fits the body proportions and lighting of Image B perfectly.",
        "4. Output: A single high-quality photorealistic image."
    ]

    # 3. 配置安全设置
    # 处理医疗/假肢图像时，必须放宽安全限制，否则会被误判拦截
    safety_config = [
        types.SafetySetting(
            category="HARM_CATEGORY_DANGEROUS_CONTENT",
            threshold="BLOCK_ONLY_HIGH"
        ),
        types.SafetySetting(
            category="HARM_CATEGORY_HARASSMENT",
            threshold="BLOCK_ONLY_HIGH"
        ),
        types.SafetySetting(
            category="HARM_CATEGORY_HATE_SPEECH",
            threshold="BLOCK_ONLY_HIGH"
        ),
        types.SafetySetting(
            category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
            threshold="BLOCK_ONLY_HIGH"
        ),
    ]

    try:
        response = client.models.generate_content(
            model='gemini-3-pro-image-preview',
            contents=contents_list,
            config=types.GenerateContentConfig(
                temperature=0.5,
                safety_settings=safety_config,
                response_modalities = ['IMAGE'],
                image_config = types.ImageConfig(
                    aspect_ratio="16:9",
                    image_size="1K",
                ),
            )
        )

        # 4. 解析并保存结果
        if response.candidates and response.candidates[0].content.parts:
            image_found = False
            for part in response.candidates[0].content.parts:
                # 检查是否有内联数据 (图片)
                if part.inline_data:
                    image_bytes = part.inline_data.data
                    image_io = io.BytesIO(image_bytes)
                    final_image = Image.open(image_io)
                    final_image.save(output_path)
                    print(f"✅ 生成成功! 保存至: {output_path.name}")
                    image_found = True
                    break

            if not image_found:
                # 提取被拦截的原因（如果有）
                finish_reason = response.candidates[0].finish_reason
                print(f"⚠️ 生成完成但无图片。Finish Reason: {finish_reason}")
                print(f"模型文本回复: {response.text}")
        else:
            print("❌ API 返回空内容。可能是被安全策略完全拦截。")

    except Exception as e:
        print(f"❌ API 调用或处理出错: {e}")


def main(source_dir, target_dir, output_dir):
    source_path_obj = Path(source_dir)
    target_path_obj = Path(target_dir)
    output_path_obj = Path(output_dir)

    output_path_obj.mkdir(parents=True, exist_ok=True)

    if not source_path_obj.exists() or not target_path_obj.exists():
        print(f"错误: 输入目录不存在。请检查 {source_dir} 和 {target_dir}")
        return

    # 过滤非图片文件 (比如 .DS_Store 或 子文件夹)
    targets = [p for p in target_path_obj.iterdir() if p.is_file() and p.suffix.lower() in VALID_EXTS]
    sources = [p for p in source_path_obj.iterdir() if p.is_file() and p.suffix.lower() in VALID_EXTS]

    if not targets or not sources:
        print("错误: 源目录或目标目录中没有找到支持的图片文件。")
        return

    total_tasks = len(targets) * len(sources)
    print(f"=== 开始处理 === 目标图: {len(targets)} 张, 假肢源图: {len(sources)} 张")
    print(f"预计总生成数量: {total_tasks} 张")

    # 初始化 Client (Vertex AI 模式)
    try:
        client = genai.Client(
            vertexai=True,
            project=PROJECT_ID,
            location=LOCATION
        )
    except Exception as e:
        print(f"Client 初始化失败，请检查 GCP 凭证: {e}")
        return

    count = 0
    for target in targets:
        for source in sources:
            output_filename = f"sync_{target.stem}_with_{source.stem}.jpg"
            output_file_path = output_path_obj / output_filename

            if output_file_path.exists():
                print(f"[跳过] 文件已存在: {output_filename}")
                count += 1
                continue

            print(f"\n[{count + 1}/{total_tasks}] 正在处理: {target.name} + {source.name}")

            transfer_prosthetic_arm(client, source, target, output_file_path)
            count += 1

            # === 速率控制 ===
            # Vertex AI 通常配额较高，可以适当减少等待时间，但为了保险起见设为 3-5 秒
            # 如果遇到 429 Resource Exhausted 错误，请调大这个数字
            print("等待 3 秒以遵守 API 速率限制...")
            time.sleep(3)


if __name__ == "__main__":
    main(SOURCE_DIR, TARGET_DIR, OUTPUT_DIR)