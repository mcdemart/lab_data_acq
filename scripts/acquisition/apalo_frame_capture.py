#!/usr/bin/env python3
"""
Capture image(s) from an Allied Vision camera using Vimba X (VmbPy) and save FITS.

Features:
  • Free-run single shots (default) or software trigger (--trigger-software)
  • Interactive free-run (--interactive): Enter to capture; Ctrl-X (or 'x') to exit
  • Save FITS as float32 by default (no BZERO/BSCALE); switch via --dtype
  • Output directory selection with --outdir (created if missing)
  • Optional live viewer (--live) with auto-updating display
  • Camera listing (--list-cameras) and selection via --camera-id or --camera-serial
  • Interval between shots (--interval MILLISECONDS), default 0.0 ms
  • DS9-friendly saving: squeeze H×W×1 → H×W, optional channel-first (C,H,W) for color

Install:
  pip install vmbpy[numpy] numpy astropy matplotlib
"""

import argparse
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
import sys
import os

import numpy as np
from astropy.io import fits
import matplotlib.pyplot as plt

from vmbpy import VmbSystem, PixelFormat  # Vimba X Python API (VmbPy)

# ---------- parsing helpers ----------

def parse_time_to_us(s: str) -> int:
    """Parse '0.2s', '200ms', '50000us' into microseconds (int)."""
    s = s.strip().lower().replace("µ", "u")
    m = re.fullmatch(r"([0-9]*\.?[0-9]+)\s*(s|ms|us)?", s)
    if not m:
        raise ValueError(f"Bad exposure '{s}'. Use 0.2s, 200ms, 50000us")
    val = float(m.group(1))
    unit = m.group(2) or "us"
    return int(round(val * (1_000_000 if unit == "s" else 1_000 if unit == "ms" else 1)))

def parse_binning(s: str) -> tuple[int, int]:
    """Parse '2x2' -> (2, 2)."""
    m = re.fullmatch(r"\s*(\d+)\s*[xX]\s*(\d+)\s*", s)
    if not m:
        raise ValueError(f"Bad binning '{s}'. Use 1x1, 2x2, 4x4, ...")
    return int(m.group(1)), int(m.group(2))

def resolve_pixel_format(name: str | None) -> PixelFormat | None:
    if not name:
        return None
    try:
        return getattr(PixelFormat, name)
    except AttributeError:
        raise ValueError(f"Unknown pixel format '{name}'. Try Mono16, Mono8, BayerRG8, ...")

# ---------- safe feature helpers ----------

def get_feat(cam, name: str):
    try:
        return getattr(cam, name)
    except AttributeError:
        return None

def set_feat(cam, name: str, value) -> bool:
    feat = get_feat(cam, name)
    if feat is None:
        return False
    try:
        feat.set(value)  # VmbPy feature API: .set()
        return True
    except Exception:
        return False

def get_feat_val(cam, name: str, default=None):
    feat = get_feat(cam, name)
    if feat is None:
        return default
    try:
        return feat.get()  # VmbPy feature API: .get()
    except Exception:
        return default

# ---------- FITS helpers ----------

def iso_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

def build_default_filename(obj: str, idx: int | None) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_obj = re.sub(r"[^A-Za-z0-9_.-]+", "_", obj.strip()) or "image"
    return f"{stamp}_{safe_obj}{'' if idx is None else f'_{idx:02d}'}.fits"

def cast_for_fits(arr: np.ndarray, dtype: str) -> np.ndarray:
    """Cast array for desired on-disk FITS dtype."""
    if dtype == "float32":
        return arr.astype(np.float32, copy=False)     # FITS: BITPIX = -32
    elif dtype == "uint16":
        return arr.astype(np.uint16, copy=False)      # FITS: BITPIX = 16 + BZERO/BSCALE
    elif dtype == "int16":
        # Caution: values > 32767 will wrap. Pre-scale/clip yourself if needed.
        return arr.astype(np.int16, copy=False)       # FITS: BITPIX = 16 (signed)
    else:
        return arr

def write_fits(arr: np.ndarray, header_dict: dict, outfile: Path, overwrite: bool):
    hdu = fits.PrimaryHDU(data=arr)
    hdr = hdu.header
    if "OBJECT" in header_dict:
        hdr["OBJECT"] = (header_dict["OBJECT"], "Target / user prompt")
    hdr["DATE-OBS"] = (header_dict.get("DATE-OBS", iso_utc_now()), "UTC time at capture")
    if "EXPTIME" in header_dict:
        hdr["EXPTIME"] = (header_dict["EXPTIME"], "Exposure time [s]")
    if "GAIN" in header_dict:
        hdr["GAIN"] = (header_dict["GAIN"], "Gain (camera units)")
    if "XBINNING" in header_dict:
        hdr["XBINNING"] = (header_dict["XBINNING"], "Binning X")
    if "YBINNING" in header_dict:
        hdr["YBINNING"] = (header_dict["YBINNING"], "Binning Y")
    for k in ("INSTRUME","CAMERA","CAMSER","MODEL","SENSOR","PIXFMT","WIDTH","HEIGHT"):
        if k in header_dict:
            hdr[k] = header_dict[k]
    if header_dict.get("COMMENT"):
        for line in str(header_dict["COMMENT"]).splitlines():
            hdr.add_comment(line)
    hdu.writeto(outfile, overwrite=overwrite)

# ---------- DS9-friendly shape normalization ----------

def normalize_for_fits(arr: np.ndarray, mode: str = "mono") -> np.ndarray:
    """
    Ensure FITS/DS9-friendly shape.
    - 'mono': return 2-D (H, W). Squeezes trailing singleton channels (H,W,1)->(H,W).
             If a true color frame slips in (H,W,3), convert to luminance by averaging.
    - 'rgb' : return channel-first 3-D (C, H, W) for true color saving (DS9 shows 3 planes).
    """
    a = arr
    if a.ndim == 3:
        if mode == "mono":
            if a.shape[-1] == 1:
                a = a[..., 0]
            else:
                a = a.mean(axis=-1)  # simple luminance; replace with debayer if needed
        else:  # 'rgb'
            a = np.moveaxis(a, -1, 0)  # to (C, H, W)
    return np.ascontiguousarray(a)

# ---------- Live viewer ----------

class LivePlotter:
    def __init__(self, title="Vimba X Live View"):
        self.title = title
        self.fig = None
        self.ax = None
        self.im = None

    def _init_fig(self, arr: np.ndarray):
        plt.ion()
        self.fig = plt.figure(self.title)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title(self.title)
        self.im = self.ax.imshow(arr, cmap="gray", origin="upper", interpolation="nearest")
        self.fig.canvas.draw()
        plt.pause(0.001)

    def update(self, arr: np.ndarray):
        if self.im is None:
            self._init_fig(arr)
        else:
            self.im.set_data(arr)
        # Auto-stretch for visibility
        vmin, vmax = np.percentile(arr, (0.5, 99.5))
        if vmax <= vmin:
            vmin, vmax = float(arr.min()), float(arr.max())
        self.im.set_clim(vmin, vmax)
        self.fig.canvas.draw_idle()
        plt.pause(0.001)

# ---------- capture helpers ----------

def request_pixel_format(cam, pixel_format: PixelFormat | None):
    """Try to set camera pixel format before capture (preferred)."""
    if not pixel_format:
        return
    try:
        cam.set_pixel_format(pixel_format)
    except Exception:
        pass  # leave native format if not supported

def frame_to_numpy(frame) -> np.ndarray:
    """Convert VmbPy Frame to NumPy array."""
    return np.ascontiguousarray(frame.as_numpy_ndarray())

# ---------- software-trigger collector (async -> sync handoff) ----------

class TriggerCollector:
    def __init__(self):
        self.event = threading.Event()
        self.lock = threading.Lock()
        self.arr = None
        self.pfmt = None

    def handler(self, cam, stream, frame):
        try:
            # Copy to decouple from streaming buffer
            arr_copy = np.array(frame.as_numpy_ndarray(), copy=True)
            pfmt = frame.get_pixel_format()
            with self.lock:
                self.arr = arr_copy
                self.pfmt = pfmt
            self.event.set()
        finally:
            cam.queue_frame(frame)  # re-queue buffer for next frame

# ---------- cross-platform keypress (for --interactive) ----------

def read_keypress():
    """
    Return a single key as a string without waiting for Enter, cross-platform.
    - Enter returns '\r' or '\n'
    - Ctrl-X returns '\x18'
    """
    if os.name == "nt":
        import msvcrt
        ch = msvcrt.getch()
        try:
            return ch.decode("utf-8", errors="ignore")
        except Exception:
            return ""
    else:
        import termios, tty, select
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            r, _, _ = select.select([fd], [], [], None)
            if r:
                ch = os.read(fd, 1)
                try:
                    return ch.decode("utf-8", errors="ignore")
                except Exception:
                    return ""
            return ""
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(description="Capture FITS via Vimba X (VmbPy) with interactive free-run, DS9-safe shapes, float32 saving, outdir, camera selection, and interval (ms).")
    ap.add_argument("--list-cameras", action="store_true", help="List detected cameras and exit")
    ap.add_argument("--camera-id", type=str, default=None, help="Specific camera ID (exact match)")
    ap.add_argument("--camera-serial", type=str, default=None, help="Select camera by serial (exact match)")
    ap.add_argument("--object", type=str, default=None, help="Target / note saved in FITS header")
    ap.add_argument("--outfile", type=str, default=None, help="Output FITS filename (basename). If --repeat>1, index is appended")
    ap.add_argument("--outdir", type=str, default=".", help="Directory to save FITS files (default: current directory)")
    ap.add_argument("--exposure", type=str, default="50ms", help="Exposure (0.2s, 200ms, 50000us)")
    ap.add_argument("--gain", type=float, default=None, help="Gain (camera units / dB depending on model)")
    ap.add_argument("--binning", type=str, default="1x1", help="Binning as NxM (1x1, 2x2, ...)")
    ap.add_argument("--pixel-format", type=str, default="Mono16", help="Pixel format (Mono16, Mono8, BayerRG8, ...)")
    ap.add_argument("--repeat", type=int, default=1, help="Number of frames to capture (ignored with --interactive)")
    ap.add_argument("--interval", type=float, default=0.0, help="Milliseconds to wait between exposures (default 0.0 ms)")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite output file(s) if they exist")
    ap.add_argument("--trigger-software", action="store_true", help="Use software trigger (default: free-run single shots)")
    ap.add_argument("--interactive", action="store_true", help="Interactive free-run: Enter to capture, Ctrl-X (or 'x') to exit")
    ap.add_argument("--live", action="store_true", help="Show auto-updating live view window")
    ap.add_argument("--dtype", choices=["float32", "uint16", "int16"], default="float32",
                    help="FITS data type (default: float32)")
    args = ap.parse_args()

    outdir = Path(args.outdir).expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    with VmbSystem.get_instance() as vmb:
        cams = vmb.get_all_cameras()
        if args.list_cameras:
            if not cams:
                print("No Allied Vision cameras detected.")
                return
            for c in cams:
                with c:
                    print(f"ID={c.get_id()}  MODEL={c.get_model()}  SERIAL={c.get_serial()}")
            return

        if not cams:
            raise RuntimeError("No Allied Vision cameras detected by VmbPy.")

        # ---- camera selection precedence: --camera-id > --camera-serial > first camera ----
        cam = None
        if args.camera_id:
            cam = vmb.get_camera_by_id(args.camera_id)
        elif args.camera_serial:
            for c in cams:
                with c:
                    if c.get_serial() == args.camera_serial:
                        cam = c
                        break
            if cam is None:
                raise RuntimeError(f"Camera with serial '{args.camera_serial}' not found.")
        else:
            cam = cams[0]

        # Prompt for object if not provided
        obj = args.object
        if not obj:
            try:
                obj = input("Object / note to store in FITS header: ").strip()
            except KeyboardInterrupt:
                print("\nAborted.")
                return
            if not obj:
                obj = "Untitled"

        exp_us = parse_time_to_us(args.exposure)
        bin_x, bin_y = parse_binning(args.binning)
        pixfmt_want = resolve_pixel_format(args.pixel_format)
        viewer = LivePlotter() if args.live else None

        # filename helpers (respect --outdir and optional --outfile)
        def make_outpath(i: int | None) -> Path:
            if args.outfile:
                base = Path(args.outfile).name
                if i is None:
                    return outdir / base
                stem = Path(base).with_suffix("")
                return outdir / f"{stem}_{i:02d}.fits"
            else:
                return outdir / build_default_filename(obj, i)

        with cam:
            # ---- configure features ----
            set_feat(cam, "ExposureAuto", "Off")
            set_feat(cam, "GainAuto", "Off")
            set_feat(cam, "ExposureTime", float(exp_us))  # typically µs
            if args.gain is not None:
                set_feat(cam, "Gain", float(args.gain))
            set_feat(cam, "BinningHorizontal", int(bin_x))
            set_feat(cam, "BinningVertical", int(bin_y))

            set_feat(cam, "TriggerSelector", "FrameStart")
            if args.trigger_software:
                set_feat(cam, "TriggerSource", "Software")
                set_feat(cam, "TriggerMode", "On")
                set_feat(cam, "AcquisitionMode", "Continuous")
            else:
                set_feat(cam, "TriggerMode", "Off")

            # Desired camera pixel format (if supported)
            request_pixel_format(cam, pixfmt_want)

            # Read-back effective values
            exp_us_eff = float(get_feat_val(cam, "ExposureTime", exp_us))
            gain_eff = get_feat_val(cam, "Gain", args.gain)
            bx_eff = int(get_feat_val(cam, "BinningHorizontal", bin_x))
            by_eff = int(get_feat_val(cam, "BinningVertical", bin_y))
            cam_id = cam.get_id()
            model = cam.get_model()
            serial = cam.get_serial()
            sensor = get_feat_val(cam, "SensorName", None)

            def save_one(arr: np.ndarray, pfmt, index_for_name: int | None):
                """Normalize (DS9-safe), cast, write FITS, live view, print."""
                arr_norm = normalize_for_fits(arr, mode="mono")
                if viewer:
                    viewer.update(arr_norm)
                hdr = {
                    "OBJECT": obj,
                    "DATE-OBS": iso_utc_now(),
                    "EXPTIME": exp_us_eff / 1_000_000.0,
                    "GAIN": None if gain_eff is None else float(gain_eff),
                    "XBINNING": bx_eff,
                    "YBINNING": by_eff,
                    "INSTRUME": "Allied Vision",
                    "CAMERA": cam_id,
                    "CAMSER": serial or "",
                    "MODEL": model or "",
                    "SENSOR": sensor or "",
                    "PIXFMT": str(pfmt),
                    "WIDTH": arr_norm.shape[-1] if arr_norm.ndim == 3 else arr_norm.shape[1],
                    "HEIGHT": arr_norm.shape[-2] if arr_norm.ndim == 3 else arr_norm.shape[0],
                    "COMMENT": f"Saved by capture_fits_vmbpy.py; pixel format {pfmt}."
                }
                outfile = make_outpath(index_for_name)
                arr_to_save = cast_for_fits(arr_norm, args.dtype)
                write_fits(arr_to_save, hdr, outfile, overwrite=args.overwrite)
                print(f"Wrote {outfile}  [{arr_to_save.dtype}, shape={arr_to_save.shape}]")

            # ---- capture modes ----
            if args.trigger_software:
                # Software-triggered streaming (non-interactive)
                collector = TriggerCollector()
                cam.start_streaming(collector.handler, buffer_count=5)
                try:
                    for i in range(args.repeat):
                        collector.event.clear()
                        cam.TriggerSoftware.run()
                        if not collector.event.wait(timeout=5):
                            raise TimeoutError("No frame arrived after software trigger.")
                        with collector.lock:
                            arr = collector.arr
                            pfmt = collector.pfmt
                        if arr is None:
                            raise RuntimeError("Collector received no data.")
                        save_one(arr, pfmt, None if args.repeat == 1 else (i + 1))
                        if args.interval > 0.0 and i < args.repeat - 1:
                            time.sleep(args.interval / 1000.0)
                finally:
                    cam.stop_streaming()
            else:
                # Free-run singles (get_frame)
                if args.interactive:
                    print("Interactive free-run mode.")
                    print("Press Enter to capture; press Ctrl-X (or 'x') to exit.")
                    shot_idx = 1
                    while True:
                        key = read_keypress()
                        if key in ("\r", "\n"):   # Enter
                            frame = cam.get_frame()
                            pfmt = frame.get_pixel_format()
                            arr = frame_to_numpy(frame)
                            # CHANGE: always pass an index, even for the first shot
                            save_one(arr, pfmt, shot_idx)
                            shot_idx += 1
                            if args.interval > 0.0:
                                time.sleep(args.interval / 1000.0)
                        elif key in ("\x18", "x", "X"):  # Ctrl-X or 'x'
                            print("Exiting interactive mode.")
                            break
                        else:
                            continue
                else:
                    for i in range(args.repeat):
                        frame = cam.get_frame()  # synchronous single frame
                        pfmt = frame.get_pixel_format()
                        arr = frame_to_numpy(frame)
                        save_one(arr, pfmt, None if args.repeat == 1 else (i + 1))
                        if args.interval > 0.0 and i < args.repeat - 1:
                            time.sleep(args.interval / 1000.0)

    print("Done.")

if __name__ == "__main__":
    main()
