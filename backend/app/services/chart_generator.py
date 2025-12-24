"""
Chart generator service
Pixel-perfect layout for 1701x1026 PNG
"""

import io
import logging
import time
import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path
from collections import OrderedDict

import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams['path.simplify'] = True
matplotlib.rcParams['path.simplify_threshold'] = 1.0
matplotlib.rcParams['agg.path.chunksize'] = 10000

from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
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
        self._cryptowatcher_image_path = self._base_dir / "static" / "cryptowatcher.png"
        
        self._card_left = self.CARD_LEFT_PX / self.WIDTH_PX
        self._card_bottom = self.CARD_BOTTOM_PX / self.HEIGHT_PX
        self._card_width = 1 - (self.CARD_LEFT_PX + self.CARD_RIGHT_PX) / self.WIDTH_PX
        self._card_height = 1 - (self.CARD_TOP_PX + self.CARD_BOTTOM_PX) / self.HEIGHT_PX
        self._header_y = (self.HEIGHT_PX - 220) / self.HEIGHT_PX
        
        ICON_SIZE = 256
        ICON_ZOOM = 0.2
        ICON_GAP_PX = 12
        self._icon_width_norm = (ICON_SIZE * ICON_ZOOM) / self.WIDTH_PX
        self._icon_gap_norm = ICON_GAP_PX / self.WIDTH_PX
        
        self._base_img_array = np.array(Image.open(self._base_image_path))
        self._tp_img_array = np.array(Image.open(self._tp_image_path))
        self._sl_img_array = np.array(Image.open(self._sl_image_path))
        
        self._load_cryptowatcher_icon()
        
        self._icon_cache: OrderedDict = OrderedDict()
        self._icon_cache_max_size = 100
        self._icon_cache_ttl = 3600
        
        self._circle_masks = {}
        for size in [56, 256]:
            mask = Image.new("L", (size, size), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
            self._circle_masks[size] = mask
        
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(5.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
        )

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

    def _load_cryptowatcher_icon(self):
        """Preloads and processes cryptowatcher icon once"""
        try:
            cryptowatcher_img = Image.open(self._cryptowatcher_image_path).convert("RGBA")
            original_width, original_height = cryptowatcher_img.size
            
            CRYPTOWATCHER_ICON_SIZE = 128
            icon_height = CRYPTOWATCHER_ICON_SIZE
            icon_width = int(CRYPTOWATCHER_ICON_SIZE * original_width / original_height)
            
            cryptowatcher_img = cryptowatcher_img.resize((icon_width, icon_height), Image.Resampling.LANCZOS)
            
            img_array = np.array(cryptowatcher_img)
            img_array[:, :, 3] = (img_array[:, :, 3] * 0.4).astype(np.uint8)
            
            self._cryptowatcher_zoom = 16 / icon_height
            self._cryptowatcher_img_array = img_array
        except Exception as e:
            logger.warning(f"Failed to load cryptowatcher icon: {e}")
            self._cryptowatcher_img_array = None
            self._cryptowatcher_zoom = None

    async def _load_icon(self, url: Optional[str], size=56):
        """Loads icon with caching and HTTP client reuse, returns np.array"""
        if not url:
            return None
        
        cache_key = f"{url}_{size}"
        current_time = time.time()
        
        if cache_key in self._icon_cache:
            cached_arr, cached_time = self._icon_cache[cache_key]
            if current_time - cached_time < self._icon_cache_ttl:
                self._icon_cache.move_to_end(cache_key)
                return cached_arr
            else:
                del self._icon_cache[cache_key]
        
        try:
            r = await self._http_client.get(url)
            r.raise_for_status()

            img = Image.open(io.BytesIO(r.content)).convert("RGBA")
            img = img.resize((size, size), Image.Resampling.LANCZOS)

            mask = self._circle_masks.get(size)
            if mask is None:
                mask = Image.new("L", (size, size), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
                self._circle_masks[size] = mask

            out = Image.new("RGBA", (size, size))
            out.paste(img, (0, 0), mask)
            
            out_arr = np.array(out)
            
            if len(self._icon_cache) >= self._icon_cache_max_size:
                self._icon_cache.popitem(last=False)
            self._icon_cache[cache_key] = (out_arr, current_time)
            
            return out_arr
        except Exception:
            return None
    
    async def close(self):
        """Closes HTTP client (call on application shutdown)"""
        await self._http_client.aclose()

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
        """Async wrapper: loads icon, then renders chart in thread"""
        icon = await self._load_icon(coin_icon_url, size=256)
        return await asyncio.to_thread(
            self._render_chart_sync,
            coin_symbol, coin_name, current_price, percent_change_24h,
            chart_data, days, icon, market_cap, volume_24h,
            high_24h, low_24h, base_image_type
        )

    def _render_chart_sync(
        self,
        coin_symbol: str,
        coin_name: str,
        current_price: float,
        percent_change_24h: float,
        chart_data: List[Dict[str, Any]],
        days: int,
        icon: Optional[np.ndarray],
        market_cap: Optional[float],
        volume_24h: Optional[float],
        high_24h: Optional[float],
        low_24h: Optional[float],
        base_image_type: Optional[str],
    ) -> Optional[bytes]:
        """Synchronous chart rendering (runs in thread)"""
        try:
            if base_image_type == "take-profit":
                base_img_array = self._tp_img_array
            elif base_image_type == "stop-loss":
                base_img_array = self._sl_img_array
            else:
                base_img_array = self._base_img_array

            prices = np.array([p["price"] for p in chart_data], dtype=np.float64)
            timestamps = np.array([p["timestamp"] for p in chart_data], dtype=np.float64) / 1000.0
            # Convert Unix timestamps (seconds) to matplotlib date numbers
            # Matplotlib uses days since 0001-01-01, Unix epoch is 1970-01-01
            # Difference: 719163 days
            x_dates = timestamps / 86400.0 + 719163.0

            if base_image_type == "stop-loss":
                color = self.PRICE_DOWN
            elif base_image_type == "take-profit":
                color = self.PRICE_UP
            else:
                color = self.PRICE_UP if percent_change_24h >= 0 else self.PRICE_DOWN

            DPI = 120
            fig = Figure(
                figsize=(self.WIDTH_PX / DPI, self.HEIGHT_PX / DPI),
                dpi=DPI,
                facecolor='none'
            )
            canvas = FigureCanvas(fig)

            # ===== BACKGROUND =====
            ax_bg = fig.add_axes([0, 0, 1, 1])
            ax_bg.imshow(base_img_array)
            ax_bg.axis("off")

            card_left = self._card_left
            card_bottom = self._card_bottom
            card_width = self._card_width
            card_height = self._card_height

            # ===== GRAPH =====
            ax = fig.add_axes([
                card_left + 0.025,
                card_bottom + 0.065,
                card_width - 0.09,
                card_height - 0.28
            ])
            ax.set_facecolor("none")

            ax.set_xlim(x_dates[0], x_dates[-1])
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
            ax.tick_params(axis="x", pad=8)

            y_min = float(np.min(prices))
            y_max = float(np.max(prices))
            y_range = y_max - y_min
            ax.set_ylim(
                y_min - y_range * 0.05,
                y_max + y_range * 0.05
            )

            y_axis_min, _ = ax.get_ylim()

            ax.plot(x_dates, prices, color=color, linewidth=2.6)
            ax.fill_between(x_dates, prices, y_axis_min, color=color, alpha=0.30)
            
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
                x_dates[-1],
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

            header_y = self._header_y
            HEADER_LEFT = 0.115

            if icon is not None:
                ax_ui.add_artist(
                    AnnotationBbox(
                        OffsetImage(icon, zoom=0.2),
                        (HEADER_LEFT, header_y + 0.004),
                        frameon=False
                    )
                )

            header_x = HEADER_LEFT + self._icon_width_norm + self._icon_gap_norm

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

            bot_text = ax_ui.text(
                card_left + 0.73,
                card_bottom - 0.045,
                f"@CryptoWatcherr_bot",
                fontsize=10,
                color=self.TEXT_COLOR_SECONDARY,
                alpha=0.8
            )

            canvas.draw()
            renderer = canvas.get_renderer()
            ticker_bbox = ticker_text.get_window_extent(renderer=renderer)
            ticker_width_norm = ticker_bbox.width / self.WIDTH_PX
            bot_bbox = bot_text.get_window_extent(renderer=renderer)
            bot_text_width_norm = bot_bbox.width / self.WIDTH_PX

            # --- FULL NAME ---
            ax_ui.text(
                header_x + ticker_width_norm + self._icon_gap_norm,
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
            METRICS_PADDING_PX = 40

            metrics_left = card_left + METRICS_PADDING_PX / self.WIDTH_PX
            metrics_right = card_left + card_width - METRICS_PADDING_PX / self.WIDTH_PX
            metrics_width = metrics_right - metrics_left

            metrics_step = metrics_width / METRICS_COUNT
            xs = [metrics_left + (i + 0.5) * metrics_step for i in range(METRICS_COUNT)]

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

            ax_ui.text(
                card_left + 0.01,
                card_bottom - 0.045,
                f"{coin_symbol}/USD — {days} day chart",
                fontsize=10,
                color=self.TEXT_COLOR_SECONDARY,
                alpha=0.8
            )

            if self._cryptowatcher_img_array is not None:
                icon_x = card_left + 0.73 + bot_text_width_norm + 0.016
                icon_y = card_bottom - 0.04
                
                ax_ui.add_artist(
                    AnnotationBbox(
                        OffsetImage(self._cryptowatcher_img_array, zoom=self._cryptowatcher_zoom),
                        (icon_x, icon_y),
                        frameon=False
                    )
                )

            buf = io.BytesIO()
            # Use higher DPI for saving to get larger resolution (2126x1282 instead of 1701x1026)
            SAVE_DPI = 187.5  # 150 * 1.25 = 187.5 (gives 2126x1282 from 1701x1026)
            canvas.print_figure(
                buf,
                format="png",
                dpi=SAVE_DPI,
                bbox_inches=None,
                pad_inches=0
            )

            buf.seek(0)
            return buf.read()

        except Exception as e:
            logger.error("Chart render failed", exc_info=e)
            return None


chart_generator = ChartGenerator()