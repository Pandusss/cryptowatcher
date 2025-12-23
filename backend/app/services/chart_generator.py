"""
Chart generator service
Pixel-perfect layout for 1701x1026 PNG
"""

import io
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from PIL import Image, ImageDraw
import httpx
import numpy as np

from app.utils.formatters import get_price_decimals 


logger = logging.getLogger("ChartGenerator")


class ChartGenerator:
    TEXT_COLOR = "#F0F0F0"
    TEXT_COLOR_SECONDARY = "#8B949E"
    GRID_COLOR = "#FFFFFF"

    PRICE_UP = "#2EA043"
    PRICE_DOWN = "#F85149"

    # === TARGET RESOLUTION ===
    WIDTH_PX = 1701
    HEIGHT_PX = 1026

    # === CARD GEOMETRY (FROM PHOTOSHOP) ===
    CARD_LEFT_PX = 112
    CARD_RIGHT_PX = 112
    CARD_TOP_PX = 147
    CARD_BOTTOM_PX = 146

    def __init__(self):
        self._base_dir = Path(__file__).parent.parent
        self._base_image_path = self._base_dir / "static" / "base.png"
        self._tp_image_path = self._base_dir / "static" / "tp.png"
        self._sl_image_path = self._base_dir / "static" / "sl.png"

    # ---------- FORMATTERS ----------

    def _format_price(self, price: Optional[float]) -> str:
        if price is None:
            return "N/A"
        decimals = get_price_decimals(price)
        return f"${price:.{decimals}f}"

    def _format_large(self, v: Optional[float]) -> str:
        if v is None:
            return "N/A"
        if v >= 1_000_000_000:
            return f"${v/1_000_000_000:.2f}B"
        if v >= 1_000_000:
            return f"${v/1_000_000:.2f}M"
        return f"${v/1_000:.2f}K"

    # ---------- LOADERS ----------

    async def _load_icon(self, url: Optional[str], size=56):
        if not url:
            return None
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.get(url)
                r.raise_for_status()

            img = Image.open(io.BytesIO(r.content)).convert("RGBA")
            img = img.resize((size, size), Image.Resampling.LANCZOS)

            mask = Image.new("L", (size, size), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)

            out = Image.new("RGBA", (size, size))
            out.paste(img, (0, 0), mask)
            return out
        except Exception:
            return None

    # ---------- MAIN ----------

    async def generate_chart(
        self,
        coin_symbol: str,
        coin_name: str,
        current_price: float,
        percent_change_24h: float,
        chart_data: List[Dict[str, Any]],
        days: int = 7,
        coin_icon_url: Optional[str] = None,
        market_cap: Optional[float] = None,
        volume_24h: Optional[float] = None,
        high_24h: Optional[float] = None,
        low_24h: Optional[float] = None,
        base_image_type: Optional[str] = None,
    ) -> Optional[bytes]:

        try:
            if base_image_type == "take-profit":
                base_img_path = self._tp_image_path
            elif base_image_type == "stop-loss":
                base_img_path = self._sl_image_path
            else:
                base_img_path = self._base_image_path
            
            base_img = Image.open(base_img_path)

            prices = [p["price"] for p in chart_data]
            dates = [
                datetime.fromtimestamp(p["timestamp"] / 1000, tz=timezone.utc)
                for p in chart_data
            ]

            if base_image_type == "stop-loss":
                color = self.PRICE_DOWN
            elif base_image_type == "take-profit":
                color = self.PRICE_UP
            else:
                color = self.PRICE_UP if percent_change_24h >= 0 else self.PRICE_DOWN

            fig = plt.figure(
                figsize=(self.WIDTH_PX / 120, self.HEIGHT_PX / 120),
                dpi=120
            )

            # ===== BACKGROUND =====
            ax_bg = fig.add_axes([0, 0, 1, 1])
            ax_bg.imshow(np.array(base_img))
            ax_bg.axis("off")

            # ===== CARD NORMALIZED GEOMETRY =====
            card_left = self.CARD_LEFT_PX / self.WIDTH_PX
            card_bottom = self.CARD_BOTTOM_PX / self.HEIGHT_PX
            card_width = 1 - (self.CARD_LEFT_PX + self.CARD_RIGHT_PX) / self.WIDTH_PX
            card_height = 1 - (self.CARD_TOP_PX + self.CARD_BOTTOM_PX) / self.HEIGHT_PX

            # ===== GRAPH =====
            ax = fig.add_axes([
                card_left + 0.025,
                card_bottom + 0.065,
                card_width - 0.09,
                card_height - 0.28
            ])
            ax.set_facecolor("none")

            ax.set_xlim(dates[0], dates[-1])
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
            ax.tick_params(axis="x", pad=8)

            y_min = min(prices)
            y_max = max(prices)
            ax.set_ylim(
                y_min - (y_max - y_min) * 0.05,
                y_max + (y_max - y_min) * 0.05
            )

            y_axis_min, _ = ax.get_ylim()

            ax.plot(dates, prices, color=color, linewidth=2.6)
            ax.fill_between(dates, prices, y_axis_min, color=color, alpha=0.30)
            
            ax.axhline(
                y=current_price,
                color=color,
                linestyle='--',
                linewidth=1.8,
                alpha=0.7,
                zorder=10
            )
            
            price_label = self._format_price(current_price)
            ax.text(
                dates[-1],
                current_price,
                f"{price_label} ",
                color=color,
                fontsize=9,
                fontweight='600',
                va='center',
                ha='left',
                alpha=0.9,
                zorder=11,
                bbox=dict(
                    boxstyle='round,pad=0.3',
                    facecolor='#1C1C1E',
                    edgecolor=color,
                    linewidth=1,
                    alpha=0.8
                )
            )

            ax.grid(True, color=self.GRID_COLOR, alpha=0.06)
            ax.tick_params(colors=self.TEXT_COLOR_SECONDARY, labelsize=10, length=0)
            ax.yaxis.tick_right()

            for s in ax.spines.values():
                s.set_visible(False)

            # ===== UI LAYER =====
            ax_ui = fig.add_axes([0, 0, 1, 1])
            ax_ui.axis("off")

            # ================= HEADER =================
            header_y = (self.HEIGHT_PX - 220) / self.HEIGHT_PX

            HEADER_LEFT = 0.115     # ← ДВИГАЕШЬ ВСЁ ТУТ
            ICON_SIZE = 256
            ICON_ZOOM = 0.2
            ICON_GAP_PX = 12

            icon = await self._load_icon(coin_icon_url, size=ICON_SIZE)

            if icon:
                ax_ui.add_artist(
                    AnnotationBbox(
                        OffsetImage(np.array(icon), zoom=ICON_ZOOM),
                        (HEADER_LEFT, header_y + 0.004),
                        frameon=False
                    )
                )

            icon_width_norm = (ICON_SIZE * ICON_ZOOM) / self.WIDTH_PX
            gap_norm = ICON_GAP_PX / self.WIDTH_PX

            header_x = HEADER_LEFT + icon_width_norm + gap_norm

            # --- TICKER ---
            ticker_text = ax_ui.text(
                header_x,
                header_y,
                coin_symbol,
                fontsize=26,
                fontweight="700",
                color=self.TEXT_COLOR,
                va="center",
                ha="left"
            )

            fig.canvas.draw()
            renderer = fig.canvas.get_renderer()
            bbox = ticker_text.get_window_extent(renderer=renderer)
            ticker_width_norm = bbox.width / self.WIDTH_PX

            # --- FULL NAME ---
            ax_ui.text(
                header_x + ticker_width_norm + gap_norm,
                header_y,
                f"/ {coin_name}",
                fontsize=16,
                color=self.TEXT_COLOR_SECONDARY,
                va="center",
                ha="left"
            )

            # ---- PRICE ----
            ax_ui.text(
                0.9,
                header_y,
                self._format_price(current_price),
                fontsize=26,
                fontweight="700",
                color=color,
                ha="right"
            )

            ax_ui.text(
                0.9,
                header_y - 0.035,
                f"{percent_change_24h:+.2f}%",
                fontsize=14,
                color=color,
                ha="right"
            )

            # ---- METRICS ----
            label_y = card_bottom + card_height - 0.145
            value_y = label_y - 0.035

            METRICS_COUNT = 4
            METRICS_PADDING_PX = 40  # одинаковый отступ слева и справа

            metrics_left = card_left + METRICS_PADDING_PX / self.WIDTH_PX
            metrics_right = card_left + card_width - METRICS_PADDING_PX / self.WIDTH_PX
            metrics_width = metrics_right - metrics_left

            xs = [
                metrics_left + (i + 0.5) * metrics_width / METRICS_COUNT
                for i in range(METRICS_COUNT)
            ]

            labels = ["24h High", "24h Low", "Volume", "Market Cap"]
            values = [
                self._format_price(high_24h),
                self._format_price(low_24h),
                self._format_large(volume_24h),
                self._format_large(market_cap),
            ]

            for x, l, v in zip(xs, labels, values):
                ax_ui.text(x, label_y, l,
                           fontsize=11, color=self.TEXT_COLOR_SECONDARY, ha="center")
                ax_ui.text(x, value_y, v,
                           fontsize=13, fontweight="600",
                           color=self.TEXT_COLOR, ha="center")

            # ---- FOOTER ----
            ax_ui.text(
                card_left + 0.01,
                card_bottom - 0.045,
                f"{coin_symbol}/USD — {days} day chart",
                fontsize=10,
                color=self.TEXT_COLOR_SECONDARY,
                alpha=0.8
            )

            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=150, pad_inches=0)
            plt.close(fig)

            buf.seek(0)
            return buf.read()

        except Exception as e:
            logger.error("Chart render failed", exc_info=e)
            return None


chart_generator = ChartGenerator()