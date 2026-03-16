# lab_data_acq

Windows-based lab data acquisition workspace for controlling a Sciencetech monochromator, filter wheel, and lamp power supply, while capturing camera frames and spectrometer data.

## Repository Layout

- `Scripts/`
  - Main working scripts for acquisition, device control, and validation.
  - `data_acq_copilot_vimba.py` is the primary end-to-end acquisition workflow.
  - `apalo_frame_capture.py` is a standalone Allied Vision FITS capture utility.
- `Python_Example/`
  - Vendor example scripts for the Sciencetech COM API.
- `Operating Instructions/`
  - Vendor manuals and operating documentation.
- `QC Documentation/`
  - Vendor QC and acceptance-test documentation.

## Main Scripts

- `Scripts/data_acq_copilot_vimba.py`
  - Initializes Sciencetech COM devices.
  - Homes the monochromator and filter wheel.
  - Controls lamp power state and output percentage.
  - Acquires dark frames from the camera and spectrometer.
  - Sweeps wavelength and lamp power.
  - Saves FITS, PNG, and NumPy outputs for each acquisition point.

- `Scripts/apalo_frame_capture.py`
  - Captures one or more frames from an Allied Vision camera using `vmbpy`.
  - Supports free-run and software-trigger modes.
  - Writes FITS files with metadata headers.
  - Includes optional interactive capture and live view.

- `Scripts/simple_wavelength_select.py`
  - Manual wavelength selection and homing script for the monochromator and filter wheel.

- `Scripts/spectrometer_darks.py`
  - Simple spectrometer dark-frame collection and plotting utility.

- `Scripts/grab_single_frame.py`
  - Basic single-frame capture example for a Thorlabs camera.

## Environment Notes

This repository is intended for a Windows lab environment with vendor software installed locally. The scripts assume access to:

- Sciencetech COM components via `win32com.client`
- Allied Vision Vimba X Python API via `vmbpy`
- Ocean Insight spectrometer access via `seabreeze`
- FITS handling via `astropy`
- Plotting and array tools such as `matplotlib`, `numpy`, and `opencv-python`

Some scripts also assume fixed local installation paths such as:

- `C:\Program Files (x86)\Sciencetech\SciencetechCOM\...`
- `C:\ProgramData\Sciencetech\SciencetechCOM\...`

## Version Control Notes

- Vendor manuals and example scripts are kept in this repository for reference.
- Large installer bundles under `Software/` are intentionally excluded by `.gitignore`.
- Generated acquisition outputs such as FITS, NumPy arrays, plots, and run directories are also ignored.
