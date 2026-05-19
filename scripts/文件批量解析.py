import requests
import time
import zipfile
import shutil
import re
from pathlib import Path
import os

## 参考文档：https://mineru.net/apiManage/docs
# ==================== 本地必须配置区域 ====================
TOKEN = os.getenv('M_TOKEN')                     # 讲官网申请到的token设置为系统环境变量，命名为'M_TOKEN'，重启Vscode后即可使用。或者直接在这里复制token字符串（不推荐，可能泄露）。
PDF_DIR = Path(r"C:\file\大三下\经济大数据与人工智能\ai_class\keyan\test\pdf_paper")        # 存放 PDF 的文件夹
OUT_DIR = Path(r"C:\file\大三下\经济大数据与人工智能\ai_class\keyan\test\paper")                   # 输出总文件夹


# ==================== 可选配置区域 ====================
MODEL_VERSION = "vlm"                        # 模型版本: pipeline / vlm / MinerU-HTML
BATCH_MAX = 50                              # API 限制：单次申请链接不能超过 50 个
POLL_INTERVAL = 5                           # 轮询间隔（秒）
POLL_TIMEOUT = 1800                         # 最多等 30 分钟
# ===============================================

BASE_URL = "https://mineru.net"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}"
}


def sanitize_data_id(name: str) -> str:
    """
    清洗 data_id：只保留 [A-Za-z0-9_.-]，不超 128 字符。
    """
    safe = re.sub(r'[^A-Za-z0-9_.\-]', '_', name)
    return safe[:128]


def clean_directory(save_dir: Path):
    """
    删除目录中除 .md 文件和 images/ 文件夹外的所有内容。
    """
    for item in save_dir.iterdir():
        if item.is_file() and item.suffix.lower() != ".md":
            item.unlink()
        elif item.is_dir() and item.name != "images":
            shutil.rmtree(item)


def process_batch(pdf_batch: list[Path], batch_label: str):
    """
    处理一批（最多 50 个）PDF：获取上传链接 → 上传 → 等待解析 → 下载结果。
    返回 (done_count, fail_count)。
    """
    n = len(pdf_batch)

    # 1. 获取上传链接
    print(f"\n{'='*60}")
    print(f"【批次 {batch_label}】获取上传链接（{n} 个文件）...")

    # 构建 data_id → 原始 stem 的映射，API 用清洗后的 data_id，本地文件夹保留中文
    id_map: dict[str, str] = {}
    files_payload = []
    for f in pdf_batch:
        sid = sanitize_data_id(f.stem)
        # 如果清洗后相同就直接用；如果有重复（不同中文变相同下划线），加序号区分
        while sid in id_map:
            sid = sanitize_data_id(f.stem) + f"_{len(id_map)}"
        id_map[sid] = f.stem
        files_payload.append({"name": f.name, "data_id": sid})

    data = {
        "files": files_payload,
        "model_version": MODEL_VERSION,
    }
    try:
        resp = requests.post(
            f"{BASE_URL}/api/v4/file-urls/batch",
            headers=HEADERS,
            json=data,
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
    except Exception as e:
        print(f"❌ 请求上传链接失败: {e}")
        return 0, n

    if result.get("code") != 0:
        print(f"❌ 获取上传链接失败: {result.get('msg', '未知错误')}")
        return 0, n

    batch_id = result["data"]["batch_id"]
    urls = result["data"]["file_urls"]
    if len(urls) != n:
        print(f"⚠️ 返回链接数 {len(urls)} ≠ 文件数 {n}，以实际为准")

    print(f"✅ batch_id: {batch_id}")

    # 2. 上传（PUT，不设 Content-Type）
    print(f"【批次 {batch_label}】上传文件...")
    ok_upload = 0
    for i, (path, upload_url) in enumerate(zip(pdf_batch, urls)):
        try:
            with open(path, "rb") as f:
                up_resp = requests.put(
                    upload_url,
                    data=f,
                    headers={"Content-Type": ""},  # API 要求不设 Content-Type
                    timeout=120,
                )
            if up_resp.status_code in (200, 204):
                print(f"  [{i+1}/{n}] ✅ {path.name}")
                ok_upload += 1
            else:
                print(f"  [{i+1}/{n}] ❌ {path.name} (HTTP {up_resp.status_code})")
        except Exception as e:
            print(f"  [{i+1}/{n}] ❌ {path.name} - {e}")

    # 3. 轮询
    print(f"【批次 {batch_label}】等待解析完成...")
    poll_url = f"{BASE_URL}/api/v4/extract-results/batch/{batch_id}"
    start_time = time.time()
    items = []

    while time.time() - start_time < POLL_TIMEOUT:
        try:
            poll_resp = requests.get(poll_url, headers=HEADERS, timeout=30)
            poll_resp.raise_for_status()
            poll_result = poll_resp.json()
        except Exception as e:
            print(f"  查询状态失败: {e}")
            time.sleep(POLL_INTERVAL)
            continue

        if poll_result.get("code") != 0:
            print(f"  查询状态出错: {poll_result.get('msg', '未知错误')}")
            break

        items = poll_result["data"]["extract_result"]
        states = [it["state"] for it in items]
        done = sum(1 for s in states if s == "done")
        fail = sum(1 for s in states if s == "failed")
        elapsed = int(time.time() - start_time)
        print(f"  [{elapsed}s] 完成: {done}, 失败: {fail}, 处理中/等待: {len(states) - done - fail}")

        if all(s in ("done", "failed") for s in states):
            print(f"✅ 批次 {batch_label} 全部处理完毕。\n")
            break
        time.sleep(POLL_INTERVAL)
    else:
        print(f"⏰ 批次 {batch_label} 轮询超时，跳过未完成文件。\n")

    # 4. 下载结果
    print(f"【批次 {batch_label}】下载解析结果...")
    done_count = 0
    fail_count = 0

    for item in items:
        fname = item.get("file_name", "unknown")
        api_data_id = item.get("data_id", "").strip()
        state = item.get("state", "unknown")

        # 用映射表找回原始中文名作为本地文件夹名，找不到则回退到文件名 stem
        local_name = id_map.get(api_data_id, Path(fname).stem)

        if state == "failed":
            err = item.get("err_msg", "")
            print(f"  ❌ {fname} 解析失败: {err}")
            fail_count += 1
            continue

        if state != "done" or "full_zip_url" not in item:
            print(f"  ⚠️ 跳过 {fname} (状态: {state})")
            fail_count += 1
            continue

        save_dir = OUT_DIR / local_name
        save_dir.mkdir(parents=True, exist_ok=True)

        # 下载 ZIP
        try:
            zip_resp = requests.get(item["full_zip_url"], timeout=120)
            zip_resp.raise_for_status()
        except Exception as e:
            print(f"  ❌ 下载失败: {fname} - {e}")
            fail_count += 1
            continue

        zip_path = save_dir / "temp.zip"
        with open(zip_path, "wb") as f:
            f.write(zip_resp.content)

        # 解压
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(save_dir)
        except Exception as e:
            print(f"  ❌ 解压失败: {fname} - {e}")
            zip_path.unlink(missing_ok=True)
            fail_count += 1
            continue

        zip_path.unlink(missing_ok=True)

        # 清理多余文件
        clean_directory(save_dir)

        md_files = list(save_dir.glob("*.md"))
        img_dir = save_dir / "images"
        img_count = len(list(img_dir.iterdir())) if img_dir.exists() else 0
        print(f"  ✅ {fname} -> {save_dir.name}/  (MD: {len(md_files)} 个, 图片: {img_count} 张)")
        done_count += 1

    return done_count, fail_count


def main():
    # 1. 扫描所有 PDF
    # Windows 不区分大小写，用 set 去重避免 *.pdf 和 *.PDF 重复匹配
    pdf_files = sorted(set(PDF_DIR.glob("*.pdf")) | set(PDF_DIR.glob("*.PDF")))
    if not pdf_files:
        print(f"在 {PDF_DIR} 中未找到任何 PDF 文件，程序终止。")
        return

    print(f"找到 {len(pdf_files)} 个 PDF 文件：")
    for i, f in enumerate(pdf_files, 1):
        print(f"  [{i}] {f.name}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 2. 分批处理（每批 ≤ 50）
    total_done = 0
    total_fail = 0
    batch_count = (len(pdf_files) + BATCH_MAX - 1) // BATCH_MAX

    for bi in range(batch_count):
        start = bi * BATCH_MAX
        end = start + BATCH_MAX
        batch = pdf_files[start:end]
        label = f"{bi + 1}/{batch_count}"
        d, f = process_batch(batch, label)
        total_done += d
        total_fail += f

    print(f"\n{'='*60}")
    print(f"🎉 全部完成！成功: {total_done}, 失败/跳过: {total_fail}")
    print(f"结果保存在: {OUT_DIR.absolute()}")


if __name__ == "__main__":
    main()
