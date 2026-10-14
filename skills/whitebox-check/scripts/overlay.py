#!/usr/bin/env python3
"""白模关键帧 vs 参考图：并排 + 半透明叠加，一眼看构图有没有对上。

用法：
  python3 overlay.py 白模截图1.png 参考图1.png [白模截图2.png 参考图2.png ...] --out 对比.png

图按顺序两两一组。每一行：左 白模，中 参考图，右 两张叠在一起。
看右边那张：栏杆、地平线、房子边缘、人物和小物体的位置，应该和白模的线重合。
常见的跑偏：主体被画大了、位置往上挪了、镜头角度变了、多出太阳或彩虹。跑偏的那张让图片生成重做一次，提示里写「严格按白模的构图，不要放大，不要改镜头角度」。

注意：这里故意不给自动分数。试过按轮廓重合度打分，对的和错的配对分不开，会给出假的「通过」。叠图要用眼睛看。
需要 Pillow：pip install pillow
"""
import sys
from PIL import Image, ImageDraw

def main():
    args = sys.argv[1:]
    out = "overlay.png"
    if "--out" in args:
        out = args[args.index("--out") + 1]
        args = args[:args.index("--out")] + args[args.index("--out") + 2:]
    if len(args) < 2 or len(args) % 2:
        sys.exit(__doc__)
    W, H = 480, 270
    rows = []
    for i in range(0, len(args), 2):
        wb = Image.open(args[i]).convert("RGB").resize((W, H))
        rf = Image.open(args[i + 1]).convert("RGB").resize((W, H))
        row = Image.new("RGB", (W * 3, H))
        row.paste(wb, (0, 0)); row.paste(rf, (W, 0)); row.paste(Image.blend(wb, rf, 0.5), (W * 2, 0))
        d = ImageDraw.Draw(row)
        for k in range(1, 3):
            d.line((W * k, 0, W * k, H), fill=(255, 255, 255), width=2)
        d.rectangle((4, 4, 40, 22), fill=(0, 0, 0)); d.text((10, 7), str(i // 2 + 1), fill=(255, 255, 0))
        rows.append(row)
    sheet = Image.new("RGB", (W * 3, H * len(rows)))
    for k, r in enumerate(rows):
        sheet.paste(r, (0, H * k))
    sheet.save(out)
    print("saved", out, "（左：白模，中：参考图，右：叠加）")

if __name__ == "__main__":
    main()
