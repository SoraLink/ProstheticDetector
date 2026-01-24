import os
from PIL import Image


def fix_specific_file(file_path, output_root, rotate_angle=0):
    """
    专门修复 000065.jpg 这种 MPO 文件
    rotate_angle: 旋转角度。通常是 -90 (逆时针90度) 或 90 (顺时针90度)
    """
    if not os.path.exists(file_path):
        print(f"错误: 找不到文件 {file_path}")
        return

    # 准备输出文件夹
    file_name = os.path.basename(file_path)
    file_stem = os.path.splitext(file_name)[0]
    save_dir = os.path.join(output_root, file_stem)

    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    print(f"正在单独修复: {file_name}")
    print(f"目标保存目录: {save_dir}")
    print(f"强制旋转角度: {rotate_angle} 度")

    try:
        with Image.open(file_path) as img:
            n_frames = getattr(img, 'n_frames', 1)

            for i in range(n_frames):
                img.seek(i)
                frame = img.copy()

                # 【强制旋转】
                # expand=True 非常重要，它保证旋转后画布会自动调整大小，不会被裁切
                if rotate_angle != 0:
                    frame = frame.rotate(rotate_angle, expand=True)

                if frame.mode != 'RGB':
                    frame = frame.convert('RGB')

                save_name = f"{i:05d}.jpg"
                save_path = os.path.join(save_dir, save_name)
                frame.save(save_path, quality=95)
                print(f"  -> 第 {i} 帧已覆盖保存")

    except Exception as e:
        print(f"修复失败: {e}")


# --- 配置区 ---

# 1. 这里填那个出问题的文件的完整路径
target_file = "/DATA/dataset_raw/000065.jpg"

# 2. 这里填你之前提取图片的那个输出根目录
# (脚本会自动找到 000065 那个子文件夹并覆盖里面的图片)
output_folder = "/DATA/dataset_raw_extracted"

# 3. 这里填你想旋转的角度
# 如果现在的图是向左倒的（逆时针躺着），填 -90
# 如果现在的图是向右倒的（顺时针躺着），填 90
rotation = -90

if __name__ == "__main__":
    fix_specific_file(target_file, output_folder, rotation)