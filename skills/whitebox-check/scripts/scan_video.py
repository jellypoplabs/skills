#!/usr/bin/env python3
"""生成出来的视频：找跳帧（硬切）和可疑的叠化，出逐帧检查图。

用法：
  python3 scan_video.py 成片.mp4 [--out 目录]

做三件事：
1. 每两帧之间的画面变化打分，列出最大的几处。分数明显高过其他地方（经验：比第二名高一倍、或者 6 以上）的，基本就是跳了一下。
2. 每秒 10 帧拼成检查图（每 4 秒一张），用眼睛看叠化：远景被换掉、人物变半透明、东西凭空出现。叠化是慢慢变的，打分抓不到，只能靠看。
3. 把分数最高的几处，前后各 6 帧单独拼一张，方便逐帧确认。
需要 ffmpeg。
"""
import os, re, subprocess, sys

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    video = args[0]
    out = args[args.index("--out") + 1] if "--out" in args else os.path.splitext(video)[0] + "_scan"
    os.makedirs(out, exist_ok=True)
    probe = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate:format=duration", "-of", "default=nw=1", video]).stdout
    num, den = re.search(r"r_frame_rate=(\d+)/(\d+)", probe).groups()
    fps = int(num) / int(den)
    dur = float(re.search(r"duration=([\d.]+)", probe).group(1))
    log = run(["ffmpeg", "-i", video, "-vf", "scale=640:-2,scdet=threshold=0:sc_pass=0,metadata=print:key=lavfi.scd.score:file=-", "-f", "null", "-"]).stdout
    scores = [float(x) for x in re.findall(r"lavfi\.scd\.score=([\d.]+)", log)]
    ranked = sorted(((s, i + 1) for i, s in enumerate(scores)), reverse=True)
    top = ranked[:8]
    lines = [f"# 跳帧扫描：{os.path.basename(video)}", "", f"{dur:.2f} 秒，{fps:.2f} fps，共 {len(scores) + 1} 帧", "", "| 帧 | 时间 | 变化分数 |", "|---|---|---|"]
    lines += [f"| {i} | {i / fps:.2f} 秒 | {s:.2f} |" for s, i in top]
    if len(top) >= 2 and (top[0][0] >= 6 or top[0][0] >= 2 * top[1][0]):
        lines += ["", f"**第 {top[0][1]} 帧（{top[0][1] / fps:.2f} 秒）很可能跳了一下，打开 cut_{top[0][1]:04d}.png 逐帧确认。**"]
    else:
        lines += ["", "没有明显的硬切。叠化还要看 sheet_*.png。"]
    for s, i in top[:3]:
        lo = max(0, i - 6)
        run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vf", f"select='between(n,{lo},{i + 5})',scale=320:-2,tile=6x2", "-frames:v", "1", os.path.join(out, f"cut_{i:04d}.png")])
    for start in range(0, int(dur) + 1, 4):
        run(["ffmpeg", "-v", "error", "-y", "-ss", str(start), "-t", "4", "-i", video, "-vf",
             f"fps=10,scale=256:-2,drawtext=text='%{{eif\\:t+{start}\\:d}}.%{{eif\\:mod((t+{start})*10\\,10)\\:d}}':x=6:y=6:fontsize=20:fontcolor=red:box=1:boxcolor=white@0.7,tile=8x5",
             "-frames:v", "1", os.path.join(out, f"sheet_{start:02d}s.png")])
    open(os.path.join(out, "scan.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print("\n检查图在", out)

if __name__ == "__main__":
    main()
