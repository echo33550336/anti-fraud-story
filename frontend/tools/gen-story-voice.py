"""按 contract/lines.json 批量生成非主角配音。

输出：public/voice/story/{key}.mp3（key 形如 N02_0）

用法：
  set PYTHONPATH=E:\\COM\\hackson\\.pydeps
  python tools/gen-story-voice.py            # 只补缺失
  python tools/gen-story-voice.py --force    # 全部重生成
  python tools/gen-story-voice.py --keys N02_0,N03_1  # 只生成指定句
"""
import asyncio
import json
import os
import sys

import edge_tts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINES = os.path.join(ROOT, "contract", "lines.json")
OUT = os.path.join(ROOT, "public", "voice", "story")
CONCURRENCY = 5


async def synth_one(sem, item, force):
    path = os.path.join(OUT, item["key"] + ".mp3")
    if os.path.exists(path) and os.path.getsize(path) > 1000 and not force:
        return ("skip", item["key"], os.path.getsize(path))
    async with sem:
        for attempt in range(3):
            try:
                com = edge_tts.Communicate(
                    item["text"], item["voice"],
                    rate=item.get("rate", "+0%"), pitch=item.get("pitch", "+0Hz"),
                )
                await com.save(path)
                size = os.path.getsize(path)
                if size > 500:
                    return ("ok", item["key"], size)
                raise RuntimeError(f"文件过小 {size}B")
            except Exception as e:  # noqa: BLE001
                if attempt == 2:
                    return ("err", item["key"], repr(e))
                await asyncio.sleep(1.2 * (attempt + 1))


async def main():
    force = "--force" in sys.argv
    keys = None
    if "--keys" in sys.argv:
        index = sys.argv.index("--keys")
        if index + 1 >= len(sys.argv):
            raise SystemExit("--keys 后需要逗号分隔的句子 key")
        keys = set(sys.argv[index + 1].split(","))
    with open(LINES, encoding="utf-8") as f:
        data = json.load(f)
    items = data["lines"]
    if keys is not None:
        items = [item for item in items if item["key"] in keys]
    os.makedirs(OUT, exist_ok=True)

    sem = asyncio.Semaphore(CONCURRENCY)
    done = 0
    ok = skip = err = 0
    total_bytes = 0
    fails = []

    tasks = [asyncio.create_task(synth_one(sem, it, force)) for it in items]
    for coro in asyncio.as_completed(tasks):
        status, key, info = await coro
        done += 1
        if status == "ok":
            ok += 1
            total_bytes += info
        elif status == "skip":
            skip += 1
            total_bytes += info
        else:
            err += 1
            fails.append((key, info))
        if done % 20 == 0 or done == len(items):
            print(f"  {done}/{len(items)}　新生成 {ok}　跳过 {skip}　失败 {err}", flush=True)

    print(f"\n完成：新生成 {ok}，跳过 {skip}，失败 {err}，合计 {total_bytes/1024:.0f} KB")
    for key, info in fails[:10]:
        print("  失败:", key, info)
    return 0 if err == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
