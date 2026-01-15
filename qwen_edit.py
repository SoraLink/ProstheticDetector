import torch
import os
from PIL import Image
from diffusers import QwenImageEditPlusPipeline, QwenImageTransformer2DModel
from transformers import BitsAndBytesConfig

# ================= 配置区 =================
model_id = "Qwen/Qwen-Image-Edit-2511"

# 输入文件夹路径 (请确保这个路径是正确的)
input_folder = "./prosthetic_arm_element_refined"
# 输出保存路径 (自动创建)
output_folder = "./results_output"

# Prompt 设置 (保持你的要求)
prompt = "Create a full-body photograph of an amputee person wearing the exact prosthetic arm from the input image. The prosthesis retained its exact appearance and texture, but is repositioned into a new, dynamic angle. Ensure a photorealistic, natural connection between the stump and the device."
negative_prompt = "altered prosthesis, modified design, changed texture, messy connection, fake looking stump, plastic look, bad anatomy, blurred details, extra limbs, missing limbs, cropped image"

# 引导系数 (建议稍微调高一点，因为你的指令很复杂，要求全身且不改假肢)
guidance_scale_value = 7.5
# =========================================

# 0. 创建输出目录
os.makedirs(output_folder, exist_ok=True)

print("🚀 正在准备 8-bit 量化配置...")

# 1. 定义 8-bit 量化配置
# 注意：你代码里写的是 load_in_8bit=True，所以我把注释里的 4-bit 改成了 8-bit 以免混淆
quant_config = BitsAndBytesConfig(
    load_in_8bit=True,
    bnb_8bit_compute_dtype=torch.bfloat16
)

print("📦 正在加载 Transformer (8-bit 量化版)...")

# 2. 单独加载 Transformer 并应用量化
# 模型加载必须放在循环外面，否则每张图都要重新加载模型，会极其慢
transformer = QwenImageTransformer2DModel.from_pretrained(
    model_id,
    subfolder="transformer",
    quantization_config=quant_config,
    torch_dtype=torch.bfloat16
)

print("🔗 正在组装完整 Pipeline...")

# 3. 加载 Pipeline
pipeline = QwenImageEditPlusPipeline.from_pretrained(
    model_id,
    transformer=transformer,
    torch_dtype=torch.bfloat16,
    device_map="balanced"
)

print("✅ 模型加载完成，准备开始批量处理...")

# 4. 开始循环处理文件夹中的图片
# 支持的图片格式
supported_extensions = ('.png', '.jpg', '.jpeg', '.webp', '.bmp')

# 获取文件夹内所有文件并排序（防止乱序）
file_list = sorted(os.listdir(input_folder))

for filename in file_list:
    # 检查是否是图片文件
    if filename.lower().endswith(supported_extensions):
        input_path = os.path.join(input_folder, filename)
        output_filename = f"gen_{filename}"  # 生成的文件名前加个 gen_
        output_path = os.path.join(output_folder, output_filename)

        print(f"🎨 正在处理: {filename} ...")

        try:
            # 打开图片
            image = Image.open(input_path).convert("RGB")

            # 生成
            output = pipeline(
                image=image,
                prompt=prompt,
                negative_prompt=negative_prompt,
                num_inference_steps=30,
                guidance_scale=guidance_scale_value,
            ).images[0]

            # 保存结果
            output.save(output_path)
            print(f"   ✅ 已保存到: {output_path}")

        except Exception as e:
            print(f"   ❌ 处理 {filename} 时出错: {e}")

print("\n🎉 所有图片处理完成！")