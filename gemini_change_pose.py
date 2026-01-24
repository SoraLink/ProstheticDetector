import os
import time
import io
import mimetypes
from pathlib import Path
from PIL import Image

from google import genai
from google.genai import types

# === 配置区域 (已完全还原) ===
# os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "key.json"
PROJECT_ID = "project-fe4de98f-5478-4cee-b84"
LOCATION = "global"  # 还原为 global

SOURCE_DIR = "/DATA/full_body_images"
OUTPUT_DIR = "/DATA/full_body_images_change_pose_round3"
VALID_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff'}

# Model ID (还原为你原本使用的模型)
MODEL_ID = 'gemini-3-pro-image-preview'


def get_mime_type(file_path):
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type if mime_type else "image/jpeg"


def transfer_prosthetic_arm(client, source_path, output_path):
    try:
        with open(source_path, 'rb') as f:
            source_bytes = f.read()
        source_mime = get_mime_type(source_path)
    except Exception as e:
        print(f"读取图片文件失败: {e}")
        return

    contents_list = [
        types.Part.from_bytes(data=source_bytes, mime_type=source_mime),
        "Change the pose of the person in the image, but strictly preserve the exact appearance, structure, and texture "
        "of the prosthetic limb. Ensure the person is wearing the prosthetic limb naturally, with a seamless and "
        "realistic fit."
    ]

    safety_config = [
        types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_ONLY_HIGH"),
        types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_ONLY_HIGH"),
        types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_ONLY_HIGH"),
        types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_ONLY_HIGH"),
    ]

    attempt_count = 0
    while True:
        attempt_count += 1
        try:
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=contents_list,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    safety_settings=safety_config,
                    response_modalities=['IMAGE'],
                )
            )

            if response.candidates and response.candidates[0].content.parts:
                image_found = False
                for part in response.candidates[0].content.parts:
                    if part.inline_data:
                        image_bytes = part.inline_data.data
                        image_io = io.BytesIO(image_bytes)
                        final_image = Image.open(image_io)

                        final_image.save(output_path, format="JPEG", quality=95)
                        print(f"✅ 生成成功! 保存至: {output_path.name}")

                        image_found = True
                        break

                if not image_found:
                    print(f"⚠️ 生成完成但无图片。Finish Reason: {response.candidates[0].finish_reason}")

                # 成功执行，跳出重试循环
                break

            else:
                print("❌ API 返回空内容。")
                break

        except Exception as e:
            # 这里的 retry 逻辑保持不动，避免 429 导致直接退出
            print(f"❌ 发生错误: {e}")
            print(f"⚠️ 正在等待 10 秒后进行第 {attempt_count + 1} 次重试...")
            time.sleep(10)
            continue


def main(source_dir, output_dir):
    source_path_obj = Path(source_dir)
    output_path_obj = Path(output_dir)
    output_path_obj.mkdir(parents=True, exist_ok=True)

    sources = [p for p in source_path_obj.iterdir() if p.is_file() and p.suffix.lower() in VALID_EXTS]

    total_tasks = len(sources)
    print(f"预计总生成数量: {total_tasks} 张")

    try:
        client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
    except Exception as e:
        print(f"Client 初始化失败: {e}")
        return

    count = 0

    for source in sources:
        # === 只改了这里：解决同名不同后缀文件被跳过的问题 ===
        # 获取原始后缀（例如 png），去掉前面的点，并转为小写
        original_ext = source.suffix[1:].lower()

        # 新文件名 = 原文件名_后缀名.jpg
        # 例如: photo.png -> photo_png.jpg
        base_output_name = f"{source.stem}_{original_ext}"

        check_filename = f"{base_output_name}.jpg"
        check_path = output_path_obj / check_filename

        if check_path.exists():
            print(f"[跳过] 文件已存在: {check_filename}")
            count += 1
            continue

        output_file_path = check_path
        print(f"[{count + 1}/{total_tasks}] 处理: {source.name} -> {check_filename}")

        transfer_prosthetic_arm(client, source, output_file_path)

        count += 1
        time.sleep(3)


if __name__ == "__main__":
    main(SOURCE_DIR, OUTPUT_DIR)