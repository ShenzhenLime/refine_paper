# =============================================================================
# Agent 调用指南
# =============================================================================
# 本脚本用于调用 MinerU API 批量解析 PDF 论文，生成结构化 Markdown。
#
# === 调用方式 ===
#
# 1. CLI（一次性批量）：
#    python 文件批量解析.py --pdf-dir "<PDF文件夹>" --out-dir "<输出文件夹>"
#    可选参数：--token <token>  --model vlm  --batch-max 50  --quiet
#
# 2. Agent 直接调用公开函数（推荐）：
#    from 文件批量解析 import parse_pdfs, parse_single_pdf
#
#    results = parse_pdfs(pdf_dir="C:/papers", out_dir="C:/output")
#    # 返回 list[dict]，每个 dict: pdf_name, status, output_dir, md_count, img_count, error
#
#    result = parse_single_pdf(pdf_path="C:/papers/xxx.pdf", out_dir="C:/output")
#    # 返回单个 dict，同上结构
#
# === 踩坑记录 ===
#
# 坑1：Windows GBK 编码不支持 emoji
#   - 现象：UnicodeEncodeError: 'gbk' codec can't encode character
#   - 解决：已将所有 emoji 替换为纯文本标签（[OK]/[FAIL]/[WARN]/[DONE] 等）
#
# 坑2：429 Too Many Requests
#   - 现象：第一次请求时 API 返回 429
#   - 原因：MinerU API 的瞬时限流，不是 batch 太大（API 支持 200 个文件）
#   - 解决：直接重试即可，无需减小 batch_max
#
# 坑3：减小 batch_max 导致超时被 kill
#   - 现象：用 --batch-max 5/10 分批跑，进程被 kill（exit 137）
#   - 原因：多批后总耗时远超单批，达到 shell 超时上限
#   - 解决：用默认 batch_max=50 一次性提交，31 个 PDF 约 2-3 分钟完成
#   - 法则：200 个以内全部用 batch_max=50 一把梭，不要减小批次
#
# 坑4：先测单个文件验证连通性
#   - 不确定 API 是否可用时，先调 parse_single_pdf 测一个最小的 PDF
#   - 单个成功后直接全量跑
# =============================================================================

import requests
import time
import zipfile
import shutil
import re
from pathlib import Path
import os

BASE_URL = "https://mineru.net"


def _sanitize_data_id(name: str) -> str:
    safe = re.sub(r'[^A-Za-z0-9_.\-]', '_', name)
    return safe[:128]


def _clean_directory(save_dir: Path):
    for item in save_dir.iterdir():
        if item.is_file() and item.suffix.lower() != ".md":
            item.unlink()
        elif item.is_dir() and item.name != "images":
            shutil.rmtree(item)


def _log(verbose: bool, msg: str):
    if verbose:
        print(msg)


def parse_single_pdf(
    pdf_path: str | Path,
    out_dir: str | Path,
    token: str | None = None,
    model_version: str = "vlm",
    verbose: bool = True,
) -> dict:
    """解析单个 PDF，返回结构化结果。

    返回 dict: pdf_name, status("success"|"failed"), output_dir, md_count, img_count, error
    """
    pdf_path = Path(pdf_path)
    out_dir = Path(out_dir)
    token = token or os.getenv("M_TOKEN")
    if not token:
        return {
            "pdf_name": pdf_path.name, "status": "failed",
            "output_dir": None, "md_count": 0, "img_count": 0,
            "error": "未提供 token，请设置 M_TOKEN 环境变量或传入 token 参数",
        }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    sid = _sanitize_data_id(pdf_path.stem)

    # 1. 获取上传链接
    _log(verbose, f"[上传链接] {pdf_path.name}")
    try:
        resp = requests.post(
            f"{BASE_URL}/api/v4/file-urls/batch",
            headers=headers,
            json={"files": [{"name": pdf_path.name, "data_id": sid}], "model_version": model_version},
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
    except Exception as e:
        return {
            "pdf_name": pdf_path.name, "status": "failed",
            "output_dir": None, "md_count": 0, "img_count": 0,
            "error": f"获取上传链接失败: {e}",
        }

    if result.get("code") != 0:
        return {
            "pdf_name": pdf_path.name, "status": "failed",
            "output_dir": None, "md_count": 0, "img_count": 0,
            "error": f"获取上传链接失败: {result.get('msg', '未知错误')}",
        }

    batch_id = result["data"]["batch_id"]
    upload_url = result["data"]["file_urls"][0]

    # 2. 上传
    _log(verbose, f"[上传] {pdf_path.name}")
    try:
        with open(pdf_path, "rb") as f:
            up_resp = requests.put(upload_url, data=f, headers={"Content-Type": ""}, timeout=120)
        if up_resp.status_code not in (200, 204):
            return {
                "pdf_name": pdf_path.name, "status": "failed",
                "output_dir": None, "md_count": 0, "img_count": 0,
                "error": f"上传失败: HTTP {up_resp.status_code}",
            }
    except Exception as e:
        return {
            "pdf_name": pdf_path.name, "status": "failed",
            "output_dir": None, "md_count": 0, "img_count": 0,
            "error": f"上传失败: {e}",
        }

    # 3. 轮询
    _log(verbose, f"[等待] {pdf_path.name}")
    poll_url = f"{BASE_URL}/api/v4/extract-results/batch/{batch_id}"
    start_time = time.time()
    item = None

    while time.time() - start_time < 1800:
        try:
            poll_resp = requests.get(poll_url, headers=headers, timeout=30)
            poll_resp.raise_for_status()
            poll_result = poll_resp.json()
        except Exception as e:
            _log(verbose, f"  查询状态失败: {e}")
            time.sleep(5)
            continue

        if poll_result.get("code") != 0:
            return {
                "pdf_name": pdf_path.name, "status": "failed",
                "output_dir": None, "md_count": 0, "img_count": 0,
                "error": f"查询状态出错: {poll_result.get('msg', '未知错误')}",
            }

        item = poll_result["data"]["extract_result"][0]
        state = item["state"]
        if state == "failed":
            return {
                "pdf_name": pdf_path.name, "status": "failed",
                "output_dir": None, "md_count": 0, "img_count": 0,
                "error": f"解析失败: {item.get('err_msg', '')}",
            }
        if state == "done":
            break
        _log(verbose, f"  [{int(time.time() - start_time)}s] {state}")
        time.sleep(5)
    else:
        return {
            "pdf_name": pdf_path.name, "status": "failed",
            "output_dir": None, "md_count": 0, "img_count": 0,
            "error": "轮询超时",
        }

    # 4. 下载 & 解压
    _log(verbose, f"[下载] {pdf_path.name}")
    save_dir = out_dir / pdf_path.stem
    save_dir.mkdir(parents=True, exist_ok=True)

    try:
        zip_resp = requests.get(item["full_zip_url"], timeout=120)
        zip_resp.raise_for_status()
    except Exception as e:
        return {
            "pdf_name": pdf_path.name, "status": "failed",
            "output_dir": None, "md_count": 0, "img_count": 0,
            "error": f"下载失败: {e}",
        }

    zip_path = save_dir / "temp.zip"
    with open(zip_path, "wb") as f:
        f.write(zip_resp.content)

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(save_dir)
    except Exception as e:
        zip_path.unlink(missing_ok=True)
        return {
            "pdf_name": pdf_path.name, "status": "failed",
            "output_dir": None, "md_count": 0, "img_count": 0,
            "error": f"解压失败: {e}",
        }

    zip_path.unlink(missing_ok=True)
    _clean_directory(save_dir)

    md_files = list(save_dir.glob("*.md"))
    img_dir = save_dir / "images"
    img_count = len(list(img_dir.iterdir())) if img_dir.exists() else 0

    return {
        "pdf_name": pdf_path.name,
        "status": "success",
        "output_dir": str(save_dir.absolute()),
        "md_count": len(md_files),
        "img_count": img_count,
        "error": None,
    }


def parse_pdfs(
    pdf_dir: str | Path,
    out_dir: str | Path,
    token: str | None = None,
    model_version: str = "vlm",
    batch_max: int = 50,
    poll_interval: int = 5,
    poll_timeout: int = 1800,
    verbose: bool = True,
) -> list[dict]:
    """批量解析 PDF 文件夹，返回结构化结果列表。

    参数:
        pdf_dir/pdf    - PDF 文件夹路径
        out_dir        - 输出目录
        token          - MinerU API Token (不传则读环境变量 M_TOKEN)
        model_version  - 模型版本 (pipeline / vlm / MinerU-HTML)
        batch_max      - 单次批量上限 (API 限制 50)
        poll_interval  - 轮询间隔秒数
        poll_timeout   - 轮询超时秒数
        verbose        - 是否打印进度

    返回:
        list[dict], 每个元素: pdf_name, status, output_dir, md_count, img_count, error
    """
    pdf_dir = Path(pdf_dir)
    out_dir = Path(out_dir)
    token = token or os.getenv("M_TOKEN")

    results: list[dict] = []

    if not token:
        _log(verbose, "[ERROR] 未提供 token，请设置 M_TOKEN 环境变量或传入 token 参数")
        return results

    pdf_files = sorted(set(pdf_dir.glob("*.pdf")) | set(pdf_dir.glob("*.PDF")))
    if not pdf_files:
        _log(verbose, f"在 {pdf_dir} 中未找到任何 PDF 文件")
        return results

    _log(verbose, f"找到 {len(pdf_files)} 个 PDF 文件")
    for i, f in enumerate(pdf_files, 1):
        _log(verbose, f"  [{i}] {f.name}")

    out_dir.mkdir(parents=True, exist_ok=True)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    batch_count = (len(pdf_files) + batch_max - 1) // batch_max

    for bi in range(batch_count):
        start = bi * batch_max
        end = start + batch_max
        batch = pdf_files[start:end]
        label = f"{bi + 1}/{batch_count}"
        _log(verbose, f"\n{'='*60}")
        _log(verbose, f"[批次 {label}] ({len(batch)} 个文件)")

        id_map: dict[str, str] = {}
        files_payload = []
        for f in batch:
            sid = _sanitize_data_id(f.stem)
            while sid in id_map:
                sid = _sanitize_data_id(f.stem) + f"_{len(id_map)}"
            id_map[sid] = f.stem
            files_payload.append({"name": f.name, "data_id": sid})

        # 1. 获取上传链接
        _log(verbose, "获取上传链接...")
        try:
            resp = requests.post(
                f"{BASE_URL}/api/v4/file-urls/batch",
                headers=headers,
                json={"files": files_payload, "model_version": model_version},
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()
        except Exception as e:
            _log(verbose, f"[ERROR] 请求上传链接失败: {e}")
            for f in batch:
                results.append({
                    "pdf_name": f.name, "status": "failed",
                    "output_dir": None, "md_count": 0, "img_count": 0,
                    "error": str(e),
                })
            continue

        if result.get("code") != 0:
            err = result.get("msg", "未知错误")
            _log(verbose, f"[ERROR] 获取上传链接失败: {err}")
            for f in batch:
                results.append({
                    "pdf_name": f.name, "status": "failed",
                    "output_dir": None, "md_count": 0, "img_count": 0,
                    "error": err,
                })
            continue

        batch_id = result["data"]["batch_id"]
        urls = result["data"]["file_urls"]

        # 2. 上传
        _log(verbose, "上传文件...")
        upload_ok: set[str] = set()
        for i, (path, upload_url) in enumerate(zip(batch, urls)):
            try:
                with open(path, "rb") as f:
                    up_resp = requests.put(
                        upload_url, data=f,
                        headers={"Content-Type": ""}, timeout=120,
                    )
                if up_resp.status_code in (200, 204):
                    _log(verbose, f"  [{i+1}/{len(batch)}] [OK] {path.name}")
                    upload_ok.add(path.name)
                else:
                    _log(verbose, f"  [{i+1}/{len(batch)}] [FAIL] {path.name} (HTTP {up_resp.status_code})")
                    results.append({
                        "pdf_name": path.name, "status": "failed",
                        "output_dir": None, "md_count": 0, "img_count": 0,
                        "error": f"上传失败: HTTP {up_resp.status_code}",
                    })
            except Exception as e:
                _log(verbose, f"  [{i+1}/{len(batch)}] [FAIL] {path.name} - {e}")
                results.append({
                    "pdf_name": path.name, "status": "failed",
                    "output_dir": None, "md_count": 0, "img_count": 0,
                    "error": f"上传失败: {e}",
                })

        # 3. 轮询
        _log(verbose, "等待解析完成...")
        poll_url = f"{BASE_URL}/api/v4/extract-results/batch/{batch_id}"
        start_time = time.time()
        items = []

        while time.time() - start_time < poll_timeout:
            try:
                poll_resp = requests.get(poll_url, headers=headers, timeout=30)
                poll_resp.raise_for_status()
                poll_result = poll_resp.json()
            except Exception as e:
                _log(verbose, f"  查询状态失败: {e}")
                time.sleep(poll_interval)
                continue

            if poll_result.get("code") != 0:
                _log(verbose, f"  查询状态出错: {poll_result.get('msg', '未知错误')}")
                break

            items = poll_result["data"]["extract_result"]
            states = [it["state"] for it in items]
            done = sum(1 for s in states if s == "done")
            fail = sum(1 for s in states if s == "failed")
            elapsed = int(time.time() - start_time)
            _log(verbose, f"  [{elapsed}s] done: {done}, fail: {fail}, pending: {len(states) - done - fail}")

            if all(s in ("done", "failed") for s in states):
                _log(verbose, f"[OK] 批次 {label} 全部处理完毕\n")
                break
            time.sleep(poll_interval)
        else:
            _log(verbose, f"[TIMEOUT] 批次 {label} 轮询超时\n")

        # 4. 下载
        _log(verbose, "下载解析结果...")
        for item in items:
            fname = item.get("file_name", "unknown")
            if fname not in upload_ok:
                continue

            api_data_id = item.get("data_id", "").strip()
            state = item.get("state", "unknown")
            local_name = id_map.get(api_data_id, Path(fname).stem)

            if state == "failed":
                err = item.get("err_msg", "")
                _log(verbose, f"  [FAIL] {fname} 解析失败: {err}")
                results.append({
                    "pdf_name": fname, "status": "failed",
                    "output_dir": None, "md_count": 0, "img_count": 0,
                    "error": err,
                })
                continue

            if state != "done" or "full_zip_url" not in item:
                _log(verbose, f"  [WARN] 跳过 {fname} (状态: {state})")
                results.append({
                    "pdf_name": fname, "status": "failed",
                    "output_dir": None, "md_count": 0, "img_count": 0,
                    "error": f"未完成 (状态: {state})",
                })
                continue

            save_dir = out_dir / local_name
            save_dir.mkdir(parents=True, exist_ok=True)

            try:
                zip_resp = requests.get(item["full_zip_url"], timeout=120)
                zip_resp.raise_for_status()
            except Exception as e:
                _log(verbose, f"  [FAIL] 下载失败: {fname} - {e}")
                results.append({
                    "pdf_name": fname, "status": "failed",
                    "output_dir": None, "md_count": 0, "img_count": 0,
                    "error": f"下载失败: {e}",
                })
                continue

            zip_path = save_dir / "temp.zip"
            with open(zip_path, "wb") as f:
                f.write(zip_resp.content)

            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(save_dir)
            except Exception as e:
                _log(verbose, f"  [FAIL] 解压失败: {fname} - {e}")
                zip_path.unlink(missing_ok=True)
                results.append({
                    "pdf_name": fname, "status": "failed",
                    "output_dir": None, "md_count": 0, "img_count": 0,
                    "error": f"解压失败: {e}",
                })
                continue

            zip_path.unlink(missing_ok=True)
            _clean_directory(save_dir)

            md_files = list(save_dir.glob("*.md"))
            img_dir = save_dir / "images"
            img_count = len(list(img_dir.iterdir())) if img_dir.exists() else 0
            _log(verbose, f"  [OK] {fname} -> {save_dir.name}/  (MD: {len(md_files)}, 图片: {img_count})")
            results.append({
                "pdf_name": fname,
                "status": "success",
                "output_dir": str(save_dir.absolute()),
                "md_count": len(md_files),
                "img_count": img_count,
                "error": None,
            })

    success = sum(1 for r in results if r["status"] == "success")
    fail = sum(1 for r in results if r["status"] == "failed")
    _log(verbose, f"\n{'='*60}")
    _log(verbose, f"[DONE] 全部完成: {success} 成功, {fail} 失败")
    _log(verbose, f"结果保存在: {out_dir.absolute()}")

    return results


# ==================== CLI 入口 ====================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MinerU PDF 批量解析")
    parser.add_argument("--pdf-dir", type=str, required=True, help="PDF 文件夹路径")
    parser.add_argument("--out-dir", type=str, required=True, help="输出目录")
    parser.add_argument("--token", type=str, default=None, help="MinerU API Token（默认读 M_TOKEN）")
    parser.add_argument("--model", type=str, default="vlm", help="模型版本 (pipeline/vlm/MinerU-HTML)")
    parser.add_argument("--batch-max", type=int, default=50, help="单次批量上限")
    parser.add_argument("--quiet", action="store_true", help="静默模式")

    args = parser.parse_args()

    results = parse_pdfs(
        pdf_dir=args.pdf_dir,
        out_dir=args.out_dir,
        token=args.token,
        model_version=args.model,
        batch_max=args.batch_max,
        verbose=not args.quiet,
    )

    if any(r["status"] == "failed" for r in results):
        exit(1)
