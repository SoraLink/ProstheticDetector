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
SOURCE_DIR = "./prosthetic_arm_element_refined"  # 假肢图
OUTPUT_DIR = "./sync_prosthetic_arm_image"  # 结果

# 支持的图片扩展名
VALID_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff'}


def get_mime_type(file_path):
    """获取文件的 MIME 类型，默认为 image/jpeg"""
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type if mime_type else "image/jpeg"


def transfer_prosthetic_arm(client, source_path, output_path):
    try:
        # 1. 以二进制读取图片，避免 PIL 转换带来的兼容性问题
        with open(source_path, 'rb') as f:
            source_bytes = f.read()

        source_mime = get_mime_type(source_path)

    except Exception as e:
        print(f"读取图片文件失败: {e}")
        return

    # 2. 构建 Prompt
    # 使用 types.Part.from_bytes 显式传入图片数据
    prompts_data = [
        [
            types.Part.from_bytes(data=source_bytes, mime_type=source_mime),
            """
            Generate a photorealistic **full-body photograph (wide shot)** of a person with an upper-limb amputation wearing the specific prosthetic arm shown in the input image.

            **Logical Requirements:**
            1. **The Person:** Must be an amputee. The amputation level must logically match the type of the prosthetic provided.
            2. **The Wear:** The person is wearing the prosthetic naturally. The connection point (socket) fits perfectly onto the person's residual limb. It must not look glued on; it must look like a functioning part of their body.
            3. **The Prosthetic (Design Fidelity & Enhancement):** Retain the core structure, shape, and specific design details of the prosthetic arm from the reference. However, you are allowed to **refine and enhance the texture resolution, sharpness, and lighting interaction**. The goal is make the prosthetic look realistic and seamlessly integrated into the scene.
            4. **Adaptation (Model's Task):** You MUST adjust the prosthetic's **pose, position, rotation, and scale** to align perfectly with the person's body posture and proportions.

            **CRITICAL INSTRUCTION: IGNORE THE INPUT BACKGROUND.** The input image contains a fake checkerboard/grid pattern background. You must completely discard this background and extract ONLY the prosthetic arm device.

            **Scene & Framing:**
            **The entire person must be visible from head to toe within the frame.** The background, lighting, and the person's dynamic full-body pose can be adjusted freely to ensure the image looks real, natural, and high-quality.
            """
        ]
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
    for idx, contents_list in enumerate(prompts_data):
        try:
            current_output_path = output_path.with_name(f"{output_path.stem}_{idx}{output_path.suffix}")
            if current_output_path.exists():
                print(f"  [跳过] 已存在: {current_output_path.name}")
                continue

            print(f"  正在生成第 {idx + 1} 张 -> {current_output_path.name} ...")
            response = client.models.generate_content(
                model='gemini-3-pro-image-preview',
                contents=contents_list,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    safety_settings=safety_config,
                    response_modalities = ['IMAGE'],
                    image_config = types.ImageConfig(
                        aspect_ratio="1:1",
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
                        final_image.save(current_output_path, format="PNG")
                        print(f"✅ 生成成功! 保存至: {current_output_path.name}")
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


def main(source_dir, output_dir):
    source_path_obj = Path(source_dir)
    output_path_obj = Path(output_dir)

    output_path_obj.mkdir(parents=True, exist_ok=True)

    if not source_path_obj.exists():
        print(f"错误: 输入目录不存在。请检查 {source_dir}")
        return

    # 过滤非图片文件 (比如 .DS_Store 或 子文件夹)
    sources = [p for p in source_path_obj.iterdir() if p.is_file() and p.suffix.lower() in VALID_EXTS]

    if not sources:
        print("错误: 源目录或目标目录中没有找到支持的图片文件。")
        return

    total_tasks = len(sources)
    print(f"=== 开始处理 === 假肢源图: {len(sources)} 张")
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
    for source in sources:
        output_filename = f"{source.stem}_arm_element.png"
        output_file_path = output_path_obj / output_filename

        print(f"\n[{count + 1}/{total_tasks}] 正在处理: {source.name}")

        transfer_prosthetic_arm(client, source, output_file_path)
        count += 1

        # === 速率控制 ===
        # Vertex AI 通常配额较高，可以适当减少等待时间，但为了保险起见设为 3-5 秒
        # 如果遇到 429 Resource Exhausted 错误，请调大这个数字
        print("等待 3 秒以遵守 API 速率限制...")
        time.sleep(3)


if __name__ == "__main__":
    main(SOURCE_DIR, OUTPUT_DIR)