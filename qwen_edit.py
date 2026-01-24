import torch
import os
from PIL import Image
from diffusers import QwenImageEditPlusPipeline

# ================= 🔧 配置区 =================
model_id = "Qwen/Qwen-Image-Edit-2511"

# 文件夹路径
input_folder = "/DATA/dataset_raw/"  # 请把你的原图放在这里
output_root = "/DATA/qwen_generated/"  # 结果会自动保存在这里

# 阶段 1：补全全身 (让模型在当前画幅内重绘为全身)
# 注意：我微调了 Prompt，去掉了 "downwards" 这种方位词，让模型自由发挥
expand_prompt = "Expand this partial photo into a complete, full-body portrait."

# 阶段 2：姿势列表
pose_prompts = []

# 负面提示词
negative_prompt = "altered prosthesis, modified design, changed texture, messy connection, fake looking stump, plastic look, bad anatomy, blurred details, extra limbs, missing limbs, cropped image, deformed hands, blurry face, ugly, low quality, distortion"

guidance_scale_value = 7.5
# ============================================

print("📦 正在以 bfloat16 精度加载模型 (启用 Sequential CPU Offload)...")

pipeline = QwenImageEditPlusPipeline.from_pretrained(
    model_id,
    torch_dtype=torch.bfloat16,
    use_safetensors=True
)
# 显存优化
pipeline.enable_sequential_cpu_offload()

print("✅ 模型加载完成！开始流水线处理...")

# ================= 🔄 主循环逻辑 =================

os.makedirs(output_root, exist_ok=True)
supported_exts = ('.jpg', '.jpeg', '.png', '.webp')

# 检查输入文件夹是否存在
if not os.path.exists(input_folder):
    os.makedirs(input_folder)
    print(f"⚠️ 输入文件夹 {input_folder} 不存在，已自动创建。请放入图片后重新运行。")
    exit()

files = [f for f in os.listdir(input_folder) if f.lower().endswith(supported_exts)]
print(f"📂 发现 {len(files)} 张图片待处理。")

for idx, filename in enumerate(files):
    file_path = os.path.join(input_folder, filename)
    file_name_no_ext = os.path.splitext(filename)[0]

    # 创建每张图的专属输出目录
    current_output_dir = os.path.join(output_root, file_name_no_ext)
    if os.path.exists(current_output_dir):
        continue

    os.makedirs(current_output_dir, exist_ok=True)

    print(f"\n[{idx + 1}/{len(files)}] 正在处理: {filename}")

    try:
        # === load image ===
        original_image = Image.open(file_path).convert("RGB")

        # -------------------------------------------------
        # Step 1: 生成全身照 (Base Full Body)
        # -------------------------------------------------
        print("   🔹 Step 1: 正在生成全身照基准图...")

        full_body_image = pipeline(
            image=original_image,
            prompt=expand_prompt,
            negative_prompt=negative_prompt,
            num_inference_steps=30,
            guidance_scale=guidance_scale_value,
        ).images[0]

        # 保存这一步的结果，作为下一步的输入
        base_save_path = os.path.join(current_output_dir, "01_full_body_base.jpg")
        full_body_image.save(base_save_path)
        print(f"      ✅ 基准全身照已保存")

        # -------------------------------------------------
        # Step 2: 基于全身照生成多姿势 (Pose Variations)
        # -------------------------------------------------
        print("   🔸 Step 2: 正在生成姿势变体...")

        # for p_idx, pose_prompt in enumerate(pose_prompts):
        #     print(f"      Running Pose {p_idx + 1}...")
        #
        #     pose_image = pipeline(
        #         image=full_body_image,  # 【关键】这里用的是刚刚生成的全身照，不是原图
        #         prompt=pose_prompt,
        #         negative_prompt=negative_prompt,
        #         num_inference_steps=50,
        #         guidance_scale=guidance_scale_value,
        #     ).images[0]
        #
        #     pose_save_path = os.path.join(current_output_dir, f"02_pose_{p_idx + 1}.jpg")
        #     pose_image.save(pose_save_path)

    except Exception as e:
        print(f"   ❌ 处理图片 {filename} 时发生错误: {e}")

print("\n🎉 所有任务处理完成！")