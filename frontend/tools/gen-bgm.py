"""为 15 幕程序化合成背景音乐（无版权素材，可重跑）。

输出：public/voice/bgm/act01.mp3 … act15.mp3（约 26 秒无缝循环，单声道 44.1kHz / 64kbps）

做法：加法合成。每幕给定调性、和弦进行、速度、亮度、噪声底与琶音型，
     渲染「低频铺底 + 和弦垫 + 琶音脉冲 + 空气噪声 → 轻微延迟 → tanh 限幅 → mp3」。

用法：python tools/gen-bgm.py
"""
import os
import wave

import lameenc
import numpy as np

SR = 44100
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public", "voice", "bgm")
rng = np.random.default_rng(20261031)

A4 = 440.0


def hz(semitone_from_a4):
    return A4 * (2 ** (semitone_from_a4 / 12))


# 和弦用「相对根音的半音」表示
MINOR = [0, 3, 7]
MAJOR = [0, 4, 7]
MIN7 = [0, 3, 7, 10]
MAJ7 = [0, 4, 7, 11]

# 每幕：[根音半音(相对A4), 和弦集合, 进行(和弦下标), BPM, 亮度, 噪声量, 琶音型]
ACTS = {
    1:  dict(root=-9, chords=[MAJOR, MINOR, MAJOR, MAJOR], prog=[0, 2, 3, 0], bpm=64,
              bright=0.45, noise=0.016, arp=[0, 4, 2, 4], name="走出剧院 · 暖·期待"),
    2:  dict(root=-12, chords=[MINOR, MINOR, MIN7, MINOR], prog=[0, 0, 2, 1], bpm=58,
              bright=0.22, noise=0.030, arp=[0, 0, 3, 0], name="陌生来电 · 暗流"),
    3:  dict(root=-7, chords=[MINOR, MAJOR, MINOR, MAJOR], prog=[0, 1, 0, 3], bpm=66,
              bright=0.38, noise=0.020, arp=[0, 2, 4, 2], name="主动核实 · 清醒"),
    4:  dict(root=-5, chords=[MAJ7, MAJOR, MAJ7, MINOR], prog=[0, 1, 2, 3], bpm=60,
              bright=0.55, noise=0.014, arp=[0, 4, 1, 4], name="看起来很正规 · 假体面"),
    5:  dict(root=-10, chords=[MINOR, MIN7, MINOR, MIN7], prog=[0, 1, 0, 2], bpm=70,
              bright=0.30, noise=0.026, arp=[0, 3, 0, 3], name="第一次转账 · 不安"),
    6:  dict(root=-10, chords=[MIN7, MINOR, MIN7, MINOR], prog=[0, 1, 2, 1], bpm=78,
              bright=0.34, noise=0.034, arp=[0, 3, 5, 3], name="连环转账 · 加速"),
    7:  dict(root=-14, chords=[MINOR, MINOR, MINOR, MINOR], prog=[0, 0, 0, 0], bpm=52,
              bright=0.16, noise=0.042, arp=[0, 0, 0, 0], name="对方失联 · 空洞"),
    8:  dict(root=-7, chords=[MAJ7, MAJOR, MAJ7, MAJOR], prog=[0, 1, 2, 1], bpm=68,
              bright=0.62, noise=0.012, arp=[0, 4, 2, 4], name="熟悉的头像 · 温柔的假象"),
    9:  dict(root=-4, chords=[MAJOR, MAJOR, MINOR, MAJOR], prog=[0, 1, 2, 1], bpm=72,
              bright=0.58, noise=0.016, arp=[0, 2, 4, 2], name="128 元山货 · 人情味"),
    10: dict(root=-4, chords=[MAJOR, MAJ7, MAJOR, MAJ7], prog=[0, 1, 0, 2], bpm=64,
              bright=0.60, noise=0.014, arp=[0, 4, 2, 4], name="真货到了 · 松弛"),
    11: dict(root=-9, chords=[MIN7, MAJOR, MIN7, MAJOR], prog=[0, 1, 2, 1], bpm=74,
              bright=0.44, noise=0.022, arp=[0, 3, 4, 3], name="信任升级 · 铺陈"),
    12: dict(root=-11, chords=[MINOR, MIN7, MINOR, MIN7], prog=[0, 1, 0, 2], bpm=80,
              bright=0.36, noise=0.030, arp=[0, 3, 5, 3], name="3000 元投资 · 压"),
    13: dict(root=-12, chords=[MINOR, MINOR, MIN7, MINOR], prog=[0, 2, 1, 0], bpm=84,
              bright=0.28, noise=0.038, arp=[0, 3, 0, 5], name="追加费用 · 重复下坠"),
    14: dict(root=-13, chords=[MINOR, MIN7, MINOR, MIN7], prog=[0, 1, 2, 3], bpm=88,
              bright=0.24, noise=0.046, arp=[0, 3, 5, 7], name="最后一次付款 · 顶点"),
    15: dict(root=-9, chords=[MIN7, MAJOR, MAJ7, MAJOR], prog=[0, 1, 2, 3], bpm=56,
              bright=0.50, noise=0.018, arp=[0, 4, 2, 4], name="终场前的核实 · 落定"),
}


def env_adsr(n, attack, decay, sustain, release):
    a = max(1, int(attack * SR))
    d = max(1, int(decay * SR))
    r = max(1, int(release * SR))
    s = max(0, n - a - d - r)
    curve = np.concatenate([
        np.linspace(0, 1, a, endpoint=False),
        np.linspace(1, sustain, d, endpoint=False),
        np.full(s, sustain),
        np.linspace(sustain, 0, r),
    ])
    if len(curve) < n:
        curve = np.pad(curve, (0, n - len(curve)))
    return curve[:n]


def pad_note(freq, dur, amp, bright):
    """和弦垫：三个泛音叠加 + 轻微失谐，慢起慢落"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    partials = [(1.0, 1.0), (2.0, 0.45 * bright + 0.12), (3.0, 0.22 * bright)]
    out = np.zeros(n, dtype=np.float64)
    for mult, level in partials:
        det = 1.0 + rng.uniform(-0.0012, 0.0012)
        out += level * np.sin(2 * np.pi * freq * mult * det * t)
        out += 0.35 * level * np.sin(2 * np.pi * freq * mult * 1.003 * t)
    lfo = 1.0 + 0.12 * np.sin(2 * np.pi * rng.uniform(0.07, 0.15) * t + rng.uniform(0, 6.28))
    return out * lfo * env_adsr(n, dur * 0.35, dur * 0.1, 0.7, dur * 0.45) * amp


def pluck(freq, dur, amp, bright):
    """琶音脉冲：指数衰减"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    wave_ = np.sin(2 * np.pi * freq * t)
    wave_ += 0.5 * bright * np.sin(2 * np.pi * freq * 2 * t)
    wave_ += 0.25 * bright * np.sin(2 * np.pi * freq * 3.01 * t)
    decay = np.exp(-t * (4.0 + 6.0 * (1 - bright)))
    attack = np.minimum(1.0, t / 0.008)
    return wave_ * decay * attack * amp


def bass_note(freq, dur, amp):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.sin(2 * np.pi * freq * t) + 0.2 * np.sin(2 * np.pi * freq * 2 * t)
    return out * env_adsr(n, 0.25, 0.2, 0.8, 0.5) * amp


def render_act(cfg, bars=4, beat=0.5, tail=2.5):
    bpm = cfg["bpm"]
    spb = 60.0 / bpm                     # 一拍秒数
    bar = spb * 4                        # 一小节
    total = bar * bars
    n = int((total + tail) * SR)
    mix = np.zeros(n, dtype=np.float64)

    root = hz(cfg["root"])
    bright = cfg["bright"]

    for b in range(bars):
        chord_idx = cfg["prog"][b % len(cfg["prog"])]
        chord = cfg["chords"][chord_idx % len(cfg["chords"])]
        t0 = b * bar

        # 和弦垫：每个音一个声部
        for k, semi in enumerate(chord):
            f = root * (2 ** (semi / 12))
            seg = pad_note(f, bar * 1.15, 0.16, bright)
            i = int(t0 * SR)
            end = min(n, i + len(seg))
            mix[i:end] += seg[:end - i]

        # 低音：每小节落两下
        for half in (0.0, bar * 0.5):
            f = root * 0.5
            seg = bass_note(f, spb * 2.0, 0.30)
            i = int((t0 + half) * SR)
            end = min(n, i + len(seg))
            mix[i:end] += seg[:end - i]

        # 琶音：八分音符
        pattern = cfg["arp"]
        steps = int(bar / (spb * 0.5))
        for s in range(steps):
            degree = pattern[s % len(pattern)]
            semi = chord[degree % len(chord)] + 12 * (1 + degree // len(chord))
            f = root * (2 ** (semi / 12))
            amp = 0.085 if s % 2 == 0 else 0.06
            seg = pluck(f, spb * 1.4, amp, bright)
            i = int((t0 + s * spb * 0.5) * SR)
            end = min(n, i + len(seg))
            mix[i:end] += seg[:end - i]

    # 空气噪声（低通）
    noise = rng.normal(0, 1, n)
    kernel = np.hanning(256)
    kernel /= kernel.sum()
    noise = np.convolve(noise, kernel, mode="same")
    mix += noise * cfg["noise"] * 6.0

    # 轻微立体感：单声道 + 短延迟再叠加（导出前转双声道由 mp3 编码器处理）
    delay = int(0.037 * SR)
    wet = np.copy(mix)
    wet[delay:] += 0.28 * mix[:-delay]
    mix = wet

    # 循环尾部：与开头交叉淡入淡出，做到无缝
    fade = int(1.6 * SR)
    body = mix[:int(total * SR)]
    tailpart = mix[int(total * SR):int(total * SR) + fade]
    if len(tailpart) == fade and len(body) > fade:
        ramp = np.linspace(0, 1, fade)
        body[:fade] = body[:fade] * ramp + tailpart * (1 - ramp)

    # 归一化 + 软限幅
    body = body / (np.max(np.abs(body)) + 1e-9) * 0.82
    body = np.tanh(body * 1.25) * 0.86
    # 统一响度：把每段拉到相同的 RMS，避免切幕时忽大忽小
    rms = float(np.sqrt(np.mean(body ** 2))) + 1e-9
    target_rms = 0.085
    body = body * (target_rms / rms)
    peak = float(np.max(np.abs(body)))
    if peak > 0.95:
        body = body * (0.95 / peak)
    return (body * 32767).astype(np.int16)


def encode_mp3(samples, path, bitrate=64):
    enc = lameenc.Encoder()
    enc.set_bit_rate(bitrate)
    enc.set_in_sample_rate(SR)
    enc.set_channels(1)
    enc.set_quality(4)
    data = enc.encode(samples.tobytes())
    data += enc.flush()
    with open(path, "wb") as f:
        f.write(data)


def main():
    os.makedirs(OUT, exist_ok=True)
    total = 0
    for act, cfg in sorted(ACTS.items()):
        pcm = render_act(cfg)
        path = os.path.join(OUT, f"act{act:02d}.mp3")
        encode_mp3(pcm, path)
        size = os.path.getsize(path)
        total += size
        print(f"  act{act:02d}.mp3  {size/1024:6.0f} KB  {len(pcm)/SR:5.1f}s  {cfg['name']}")
    print(f"\n完成 15 段，合计 {total/1024/1024:.2f} MB → {OUT}")


if __name__ == "__main__":
    main()
