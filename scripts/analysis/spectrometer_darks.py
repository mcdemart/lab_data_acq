# %%
import seabreeze
seabreeze.use('pyseabreeze')
from seabreeze.spectrometers import Spectrometer
import matplotlib.pyplot as plt
import time
import numpy as np

# setup spectrometer
try:
    spec = Spectrometer.from_first_available()
except:
    print("Couldn't find spectrometer, exiting ...")
    exit()

# %%
# take dark frames

exp_s = 5
spec_exposure = 1e6 * exp_s

spec.integration_time_micros(int(spec_exposure))

num_darks = 10
darks = []
for i in range(num_darks):
    spectrum = spec.spectrum()
    darks.append(spectrum)
    time.sleep(exp_s)
darks = np.array(darks)
cal_dark = np.median(darks, axis=0)
plt.figure()
plt.plot(darks[0][0],darks[0][1])
plt.figure()
plt.plot(cal_dark[0], cal_dark[1])
# %%
# collect light
spectrum = spec.spectrum()
cal_spec = spectrum[1] - cal_dark[1]
plt.figure()
plt.plot(spectrum[0], cal_spec)
plt.xlabel("lambda")
plt.ylabel("counts")
plt.title("Dark (x5) Subtracted")

uncal_spec = spectrum[1]
plt.figure()
plt.plot(spectrum[0], uncal_spec)
plt.xlabel("lambda")
plt.ylabel("counts")
plt.title("No Calibration")

# %%
spec.close()


# %%
