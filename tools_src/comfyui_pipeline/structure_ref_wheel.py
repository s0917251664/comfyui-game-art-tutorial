"""icon_asset ``--structure-ref`` 的範本圖輔助函式:輪盤(放射狀等分)範本與拆圖層遮罩。

這是本機 Pillow 繪圖輔助,不組 ComfyUI graph;用法見 docs/knowledge/art/structure-ref.md。
原本在 image_graphs.py,移除圖片 builder 時搬到這裡(函式內容未改)。
"""
import math

try:
    from PIL import Image as PILImage, ImageDraw
except ImportError:  # 只有真的要畫範本圖時才需要 Pillow
    PILImage = None
    ImageDraw = None

from .image_graphs import validate_dimensions


def _require_pillow():
    if PILImage is None or ImageDraw is None:
        raise RuntimeError("這個 helper 需要 Pillow。")


def build_wheel_segment_template(n_segments, width=1024, height=1024,
                                  colors=((124, 40, 168), (20, 158, 148)), gold=(212, 175, 55),
                                  frame_ratio=None, bead_count=0, hub_ratio=0.12):
    """畫一張『交錯色塊扇形 + 金色分隔線/外框/中心軸』的範本圖,是 icon_asset 的 --structure-ref
    的其中一種產生方式(輪盤/放射狀等分圖示適用)——不是獨立的 CLI task,是給呼叫端(agent 或
    人類)在需要「放射狀精準等分」這種結構時自己呼叫來產生範本檔案用,範例見
    docs/knowledge/art/structure-ref.md。

    frame_ratio(選用,0~1):給了就額外畫一圈獨立的外框環帶(獎區扇形只填到 frame_ratio 對應
    的內側半徑,環帶本身填 gold 顏色),不給就跟原本一樣只在最外緣畫一條細外框線。
    bead_count(選用,搭配 frame_ratio 用):在外框環帶中線畫幾顆等間距白色圓珠裝飾。
    hub_ratio:中心鈕半徑佔整體半徑的比例,搭配 build_wheel_layer_masks() 拆圖層時務必用同一個值,
    否則遮罩邊界會跟這張範本對不齊。
    """
    validate_dimensions(width, height)
    _require_pillow()
    img = PILImage.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = width / 2, height / 2
    radius = min(width, height) * 0.45
    line_width = max(3, min(width, height) // 200)
    wedge_radius = radius * frame_ratio if frame_ratio else radius

    if frame_ratio:
        # 先畫滿版外框圓蓋住整個範圍,獎區扇形疊上去之後,外圍那圈環帶(wedge_radius~radius
        # 之間)自然只留下框色沒被蓋到,不用另外算環狀多邊形。
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=gold)

    for i in range(n_segments):
        a0 = 2 * math.pi * i / n_segments - math.pi / 2
        a1 = 2 * math.pi * (i + 1) / n_segments - math.pi / 2
        points = [(cx, cy)]
        for s in range(13):
            a = a0 + (a1 - a0) * s / 12
            points.append((cx + wedge_radius * math.cos(a), cy + wedge_radius * math.sin(a)))
        draw.polygon(points, fill=colors[i % len(colors)])

    if frame_ratio and bead_count:
        bead_r = (radius + wedge_radius) / 2
        bead_size = (radius - wedge_radius) * 0.35
        for i in range(bead_count):
            a = 2 * math.pi * i / bead_count
            bx = cx + bead_r * math.sin(a)
            by = cy - bead_r * math.cos(a)
            draw.ellipse([bx - bead_size, by - bead_size, bx + bead_size, by + bead_size], fill=(255, 255, 255))

    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], outline=gold, width=line_width)
    for i in range(n_segments):
        angle = 2 * math.pi * i / n_segments
        x = cx + wedge_radius * math.sin(angle)
        y = cy - wedge_radius * math.cos(angle)
        draw.line([cx, cy, x, y], fill=gold, width=line_width)
    hub_radius = radius * hub_ratio
    draw.ellipse([cx - hub_radius, cy - hub_radius, cx + hub_radius, cy + hub_radius], fill=gold)
    return img


def build_wheel_layer_masks(width=1024, height=1024, frame_ratio=0.86, hub_ratio=0.22):
    """搭配 build_wheel_segment_template(frame_ratio=...) 產生的合成圖,回傳三張跟 layer_split
    格式相容的遮罩(RGBA,要保留進該圖層的區域 alpha=0,其餘 alpha=255):外框環帶、內部獎區、
    中心指針。frame_ratio/hub_ratio 務必跟產生合成圖時用的值一致,否則裁出來的圖層邊界會對不齊。

    中心指針的機關形狀(例如彈片)常常會伸出 hub 圓圈一小段延伸到獎區範圍,這裡刻意把
    hub_ratio 訂得比範本圖畫的中心鈕大一些(範本圖固定畫 0.12,這裡預設 0.22),
    讓指針延伸出去的部分還是被歸進指針圖層,不會被切給獎區圖層。
    """
    validate_dimensions(width, height)
    _require_pillow()
    cx, cy = width / 2, height / 2
    radius = min(width, height) * 0.45
    wedge_radius = radius * frame_ratio
    hub_radius = radius * hub_ratio

    def _ring_mask(r_inner, r_outer):
        m = PILImage.new("RGBA", (width, height), (0, 0, 0, 255))
        d = ImageDraw.Draw(m)
        if r_outer > 0:
            d.ellipse([cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer], fill=(0, 0, 0, 0))
        if r_inner > 0:
            d.ellipse([cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner], fill=(0, 0, 0, 255))
        return m

    frame_mask = _ring_mask(wedge_radius, radius)
    prize_mask = _ring_mask(hub_radius, wedge_radius)
    pointer_mask = _ring_mask(0, hub_radius)
    return frame_mask, prize_mask, pointer_mask


