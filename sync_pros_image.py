import os
import time
import io
import mimetypes
import random  # <--- 新增导入
from pathlib import Path
from PIL import Image

# Google GenAI SDK
from google import genai
from google.genai import types

# === 配置区域 ===
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "key.json"
PROJECT_ID = "bamboo-magnet-483511-g8"
LOCATION = "global"

SOURCE_DIR = "./prosthetic_arm_element_refined"
TARGET_DIR = "./target_images"
OUTPUT_DIR = "./sync_merge_prosthetic_arm_images"
VALID_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff'}

# 每张 Target 图片随机匹配的 Source 数量
SAMPLES_PER_TARGET = 100

# Model ID
MODEL_ID = 'gemini-3-pro-image-preview'


def get_mime_type(file_path):
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type if mime_type else "image/jpeg"


def transfer_prosthetic_arm(client, source_path, target_path, output_path):
    # ... (函数内容保持不变) ...
    try:
        with open(source_path, 'rb') as f:
            source_bytes = f.read()
        with open(target_path, 'rb') as f:
            target_bytes = f.read()

        source_mime = get_mime_type(source_path)
        target_mime = get_mime_type(target_path)

    except Exception as e:
        print(f"读取图片文件失败: {e}")
        return

    contents_list = [
        "Step 1: REFERENCE ANALYSIS (Image A below).",
        types.Part.from_bytes(data=source_bytes, mime_type=source_mime),
        """
        - **Identify:** This is a specific prosthetic arm device.
        - **Instruction:** Analyze its material (carbon fiber, metal joints), color, and structure. 
        - **CRITICAL:** IGNORE any background patterns (grids/checkerboards) in Image A. Focus ONLY on the object.
        """,

        "Step 2: TARGET COMPOSITION (Image B below).",
        types.Part.from_bytes(data=target_bytes, mime_type=target_mime),
        """
        - **Identify:** This image provides the target person, their pose, the lighting environment, and the background.
        - **Task:** We need to modify this person's appearance while maintaining the overall scene integrity.
        """,

        "Step 3: GENERATION TASK.",
        """
        **Goal:** Generate a photorealistic image that looks structurally identical to Image B, but with a specific modification.

        **Execution Steps:**
        1. **Amputation & Replacement:** Digitally replace the visible arm of the person in Image B with the prosthetic arm from Image A.
        2. **Anatomical Adaptation:** The prosthetic MUST be attached naturally to the person's shoulder/body. 
           - If the arm in Image B is a left arm, flip/rotate the prosthetic from Image A to become a left arm.
           - Adjust the size/scale of the prosthetic to match the person's body proportions perfectly.
        3. **Scene Integration:** - RENDER the prosthetic with the EXACT lighting, shadows, and color tone of Image B. 
           - The prosthetic should reflect the environment of Image B, not Image A.
        4. **Fidelity:** Keep the person's face, clothing (other than the sleeve), and the background as close to Image B as possible.
        """
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
            image_found = False
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    image_bytes = part.inline_data.data
                    image_io = io.BytesIO(image_bytes)
                    final_image = Image.open(image_io)

                    # 显式保存为 JPEG
                    final_image.save(output_path, format="JPEG", quality=95)
                    print(f"✅ 生成成功! 保存至: {output_path.name}")
                    image_found = True
                    break

            if not image_found:
                print(f"⚠️ 生成完成但无图片。Finish Reason: {response.candidates[0].finish_reason}")
        else:
            print("❌ API 返回空内容。")

    except Exception as e:
        print(f"❌ API 调用出错: {e}")


def main(source_dir, target_dir, output_dir):
    source_path_obj = Path(source_dir)
    target_path_obj = Path(target_dir)
    output_path_obj = Path(output_dir)
    output_path_obj.mkdir(parents=True, exist_ok=True)

    if not source_path_obj.exists() or not target_path_obj.exists():
        print(f"错误: 输入目录不存在。")
        return

    targets = [p for p in target_path_obj.iterdir() if p.is_file() and p.suffix.lower() in VALID_EXTS]
    sources = [p for p in source_path_obj.iterdir() if p.is_file() and p.suffix.lower() in VALID_EXTS]

    if not targets or not sources:
        print("错误: 目录中无图片。")
        return

    # === 计算任务总量 ===
    # 实际抽样数取 设定值 和 总源图数 的较小值
    actual_sample_size = min(len(sources), SAMPLES_PER_TARGET)
    total_tasks = len(targets) * actual_sample_size

    print(f"=== 开始处理 ===")
    print(f"Target 图片: {len(targets)} 张")
    print(f"Source 图片: {len(sources)} 张 (每张 Target 随机抽取 {actual_sample_size} 张 Source)")
    print(f"预计总生成数量: {total_tasks} 张")

    try:
        client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
    except Exception as e:
        print(f"Client 初始化失败: {e}")
        return

    count = 0
    for target in targets:
        print(f"\n--- 正在处理 Target: {target.name} ---")

        # === 随机采样逻辑 ===
        # 如果源图数量大于采样数，则随机抽取；否则使用全部源图
        if len(sources) > SAMPLES_PER_TARGET:
            selected_sources = random.sample(sources, SAMPLES_PER_TARGET)
        else:
            selected_sources = sources

        for source in selected_sources:
            output_filename = f"sync_{target.stem}_with_{source.stem}.jpg"
            output_file_path = output_path_obj / output_filename

            if output_file_path.exists():
                print(f"[跳过] 文件已存在: {output_filename}")
                count += 1
                continue

            print(f"[{count + 1}/{total_tasks}] 配对: {target.stem[:10]}... + {source.stem[:10]}...")
            transfer_prosthetic_arm(client, source, target, output_file_path)
            count += 1

            # 保持速率控制
            # 如果任务量很大，建议保留 sleep 避免触发 Quota 限制
            time.sleep(3)


if __name__ == "__main__":
    main(SOURCE_DIR, TARGET_DIR, OUTPUT_DIR)