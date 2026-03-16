# %% 
from astropy.io import fits
import numpy as np

import matplotlib.pyplot as plt

# Open the FITS file
path = "C:\\Users\\photonics\\Documents\\Lantern\\Scripts\\full_acq_test\\acq_2025-08-21_1\\"
hdul = fits.open(path + '1300nm_100.fits')

# Display info about the file
hdul.info()

# Get the image data (usually in the primary HDU or first extension)
image_data = hdul[0].data

# check for saturation
print("Saturation level:", np.max(image_data))

# Close the FITS file
hdul.close()

# Display the image
plt.figure(figsize=(10, 8))
plt.imshow(image_data, cmap='gray', origin='upper')
plt.colorbar(label='Pixel Value')
plt.title('FITS Image')
plt.xlabel('X (pixels)')
plt.ylabel('Y (pixels)')
plt.show()
# %%
