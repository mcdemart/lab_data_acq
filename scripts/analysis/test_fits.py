import argparse
from pathlib import Path

from astropy.io import fits
import numpy as np
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description="Inspect and display a FITS image.")
    parser.add_argument("fits_path", type=Path, help="Path to the FITS file to inspect")
    args = parser.parse_args()

    with fits.open(args.fits_path) as hdul:
        hdul.info()
        image_data = hdul[0].data

    print("Saturation level:", np.max(image_data))

    plt.figure(figsize=(10, 8))
    plt.imshow(image_data, cmap="gray", origin="upper")
    plt.colorbar(label="Pixel Value")
    plt.title(f"FITS Image: {args.fits_path.name}")
    plt.xlabel("X (pixels)")
    plt.ylabel("Y (pixels)")
    plt.show()


if __name__ == "__main__":
    main()
