"""裁掉素材里的 AI 生成水印：左上角「AI生成」徽标、右下角「小云雀AI」标识。

水印都贴在最外圈，按比例裁掉上下边缘即可，不需要逐图描边。
裁剪后分辨率仍远高于页面实际显示尺寸（横图 2848×1600、竖图 1728×2304）。

用法：
  python tools/clean-art-watermarks.py --dry-run      # 只打印会裁掉多少
  python tools/clean-art-watermarks.py                # 就地处理 public/art/*.jpg
  python tools/clean-art-watermarks.py --backup       # 就地处理，同时把原图复制到 public/art-original/
  python tools/clean-art-watermarks.py --top 0.13 --bottom 0.11   # 调裁剪比例

注意：这是有损操作。原始素材在 frontend-js2.zip 里，始终可以还原。
"""
import argparse
import os
import shutil

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "public", "art")
BACKUP = os.path.join(ROOT, "public", "art-original")


def main():
    parser = argparse.ArgumentParser(description="裁掉 public/art 里的 AI 生成水印")
    parser.add_argument("--top", type=float, default=0.125, help="从上边缘裁掉的比例（默认 0.125）")
    parser.add_argument("--bottom", type=float, default=0.105, help="从下边缘裁掉的比例（默认 0.105）")
    parser.add_argument("--quality", type=int, default=90, help="JPEG 质量（默认 90）")
    parser.add_argument("--dry-run", action="store_true", help="只打印结果，不写文件")
    parser.add_argument("--backup", action="store_true", help="处理前把原图复制到 public/art-original/")
    args = parser.parse_args()

    if not (0 <= args.top < 0.4 and 0 <= args.bottom < 0.4 and args.top + args.bottom < 0.8):
        raise SystemExit("裁剪比例不合理：top/bottom 各自 < 0.4 且之和 < 0.8")

    files = sorted(name for name in os.listdir(ART) if name.lower().endswith((".jpg", ".jpeg")))
    if not files:
        raise SystemExit(f"没有找到 JPEG 素材：{ART}")
    if args.backup and not args.dry_run:
        os.makedirs(BACKUP, exist_ok=True)

    saved = 0
    for name in files:
        path = os.path.join(ART, name)
        source = Image.open(path)
        width, height = source.size
        top = int(round(height * args.top))
        bottom = int(round(height * args.bottom))
        box = (0, top, width, height - bottom)
        out = source.crop(box)
        if args.dry_run:
            print(f"{name:16s} {width}x{height} → {out.width}x{out.height}")
            continue
        if args.backup:
            shutil.copy2(path, os.path.join(BACKUP, name))
        out.convert("RGB").save(path, "JPEG", quality=args.quality, optimize=True, progressive=True)
        saved += 1
        print(f"{name:16s} {width}x{height} → {out.width}x{out.height}  {os.path.getsize(path)//1024} KB")

    if args.dry_run:
        print(f"\n共 {len(files)} 张；去掉 --dry-run 即就地处理。")
    else:
        print(f"\n完成：处理 {saved} 张。 原图备份：{BACKUP if args.backup else '未开启（--backup 可开启）'}")


if __name__ == "__main__":
    main()
