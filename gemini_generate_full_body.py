import os
import time
import io
import mimetypes
from pathlib import Path
from PIL import Image

from google import genai
from google.genai import types

# === 配置区域 ===
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "key.json"
PROJECT_ID = "inbound-byway-484610-f0"
LOCATION = "global"

SOURCE_DIR = "/DATA/partial_body_images"
OUTPUT_DIR = "/DATA/full_body_images"
VALID_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff'}
# Model ID
MODEL_ID = 'gemini-3-pro-image-preview'


def get_mime_type(file_path):
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type if mime_type else "image/jpeg"


def transfer_prosthetic_arm(client, source_path, output_path):
    # ... (函数内容保持不变) ...
    try:
        with open(source_path, 'rb') as f:
            source_bytes = f.read()

        source_mime = get_mime_type(source_path)

    except Exception as e:
        print(f"读取图片文件失败: {e}")
        return

    contents_list = [
        types.Part.from_bytes(data=source_bytes, mime_type=source_mime),
        "Expand this partial photo into a complete, full-body portrait."
    ]

    safety_config = [
        types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_ONLY_HIGH"),
        types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_ONLY_HIGH"),
        types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_ONLY_HIGH"),
        types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_ONLY_HIGH"),
    ]

    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=contents_list,
            config=types.GenerateContentConfig(
                temperature=0.5,
                safety_settings=safety_config,
                response_modalities=['IMAGE'],
                image_config=types.ImageConfig(
                    image_size="1K",
                ),
            )
        )

        if response.candidates and response.candidates[0].content.parts:
            image_count = 0  # 计数器

            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    image_bytes = part.inline_data.data
                    image_io = io.BytesIO(image_bytes)
                    final_image = Image.open(image_io)
                    new_filename = f"{output_path.stem}_{image_count}{output_path.suffix}"
                    save_path = output_path.parent / new_filename

                    final_image.save(save_path, format="JPEG", quality=95)
                    print(f"✅ 生成成功! 第 {image_count + 1} 张保存至: {save_path.name}")

                    image_count += 1

            if image_count == 0:
                print(f"⚠️ 生成完成但无图片。Finish Reason: {response.candidates[0].finish_reason}")
        else:
            print("❌ API 返回空内容。")

    except Exception as e:
        print(f"❌ API 调用出错: {e}")


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
        base_output_name = f"sync_{source.stem}"
        check_filename = f"{base_output_name}_0.jpg"
        check_path = output_path_obj / check_filename

        if check_path.exists():
            print(f"[跳过] 文件已存在: {check_filename}")
            count += 1
            continue

        output_file_path = output_path_obj / (base_output_name + ".jpg")
        print(f"[{count + 1}/{total_tasks}] 处理: {source.name}")
        transfer_prosthetic_arm(client, source, output_file_path)
        count += 1
        time.sleep(3)


if __name__ == "__main__":
    main(SOURCE_DIR, OUTPUT_DIR)