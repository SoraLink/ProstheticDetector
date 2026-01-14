import torch
from PIL import Image
from diffusers import QwenImageEditPlusPipeline

# ================= 配置区 =================
model_id = "Qwen/Qwen-Image-Edit-2511"
image_path = "./coco/train2017/000000000731.jpg" # 换成你的图片路径
prompt = "Change the hand into a mechanical prosthetic hand, realistic, 8k"
# =========================================

print("🚀 正在加载模型 (使用 PyTorch 原生加速)...")

# 1. 加载模型 (注意：这里删掉了 device_map="auto")
pipeline = QwenImageEditPlusPipeline.from_pretrained(
    model_id,
    torch_dtype=torch.bfloat16,
)

# 2. 手动扔进显卡 (5090 显存够大，直接塞进去最稳)
pipeline.to("cuda")

# 3. 强制关闭 xformers (避免触发没有安装的组件报错)
pipeline.set_use_memory_efficient_attention_xformers(False)

print("🎨 正在生成...")

image = Image.open(image_path).convert("RGB")

output = pipeline(
    image=image,
    prompt=prompt,
    num_inference_steps=30,
    guidance_scale=6.0,
    image_guidance_scale=1.5,
).images[0]

output.save("result_final.png")
print("✅ 成功生成 result_final.png")