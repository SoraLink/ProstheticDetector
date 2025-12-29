from huggingface_hub import HfApi, login

# 1. 如果你还没有在终端登录过，取消下面这行的注释并填入 Token
# login(token="hf_你的Write权限Token")

# ================= 配置 =================
REPO_ID = "Soralink/LDPoseP"  # 你的仓库 ID
REPO_TYPE = "dataset"  # 重要：必须指定是 dataset，默认是 model

# 你要上传的文件 (刚才生成的)
LOCAL_FILE_PATH = "test_annotations_merged.json"

# 上传到仓库后的路径 (我建议放在 annotations 文件夹下，保持整洁)
PATH_IN_REPO = "annotations/test_annotations_merged.json"


# =======================================

def upload_to_hf():
    print(f"正在上传 {LOCAL_FILE_PATH} 到 {REPO_ID} ...")

    api = HfApi()

    try:
        api.upload_file(
            path_or_fileobj=LOCAL_FILE_PATH,
            path_in_repo=PATH_IN_REPO,
            repo_id=REPO_ID,
            repo_type=REPO_TYPE,
            commit_message=f"Update R2 merged annotations: {LOCAL_FILE_PATH}"
        )
        print("✅ 上传成功！")
        print(f"查看地址: https://huggingface.co/datasets/{REPO_ID}/blob/main/{PATH_IN_REPO}")

    except Exception as e:
        print(f"❌ 上传失败: {e}")
        print("提示：请检查是否运行了 'huggingface-cli login' 或者 token 是否有 Write 权限。")


if __name__ == "__main__":
    upload_to_hf()