"""Verified frame-3 REFERENCE preview, not a photograph/HDMI hardware result."""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

from reference import check_capture, sealed_samples


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--capture", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    check_capture(args.capture)
    if args.output.exists():
        cli.error("refusing to overwrite preview")
    values, _ = sealed_samples("normal")
    image = Image.new("RGB", (640, 480), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((64, 64, 575, 319), fill=(8, 16, 32))
    draw.line((64, 191, 575, 191), fill=(64, 64, 64))
    for column in range(512):
        points = [v[1] for v in values[4*column:4*column+4]]
        draw.line((64+column, 191-(max(points) >> 16), 64+column,
                   191-(min(points) >> 16)), fill=(0, 224, 255))
    image.save(args.output)
    print("REFERENCE_PREVIEW frame3; black outside mask is NOT original animation", args.output)


if __name__ == "__main__":
    main()
