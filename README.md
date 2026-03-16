# lab_data_acq

Windows-based lab data acquisition workspace for Sciencetech hardware control, Allied Vision camera capture, and spectrometer measurements.

## Repository Layout

- `scripts/acquisition/`
  - Main data-taking workflows.
- `scripts/device_tests/`
  - Hardware bring-up, COM connection checks, and manual control utilities.
- `scripts/analysis/`
  - Small analysis and validation scripts for saved data or logs.
- `scripts/vendor_examples/`
  - Vendor-provided Sciencetech example scripts kept for reference.
- `docs/manuals/`
  - Vendor operating manuals.
- `docs/qc/`
  - Vendor QC and acceptance-test documents.
- `Software/`
  - Local installer bundle and vendor binaries.
  - Excluded from Git by `.gitignore`.

## Custom Scripts

- `scripts/acquisition/data_acq_copilot_vimba.py`
  - End-to-end acquisition sweep across wavelength and lamp power.
  - Uses Sciencetech COM APIs, `vmbpy`, and `seabreeze`.
- `scripts/acquisition/apalo_frame_capture.py`
  - Allied Vision FITS capture utility with CLI options, triggering modes, and live view.
- `scripts/device_tests/simple_wavelength_select.py`
  - Manual homing and wavelength selection for the monochromator and filter wheel.
- `scripts/analysis/spectrometer_darks.py`
  - Spectrometer dark-frame collection and plotting.
- `scripts/analysis/lamp_power_tests.py`
  - Plotter for lamp power monitor CSV output.
- `scripts/analysis/test_fits.py`
  - Quick FITS inspection utility.

## Vendor Scripts

- `scripts/vendor_examples/Example-using pythoncom(pywin32).py`
- `scripts/vendor_examples/TestCOM_FilterWheel-trinamic.py`
- `scripts/vendor_examples/TestCOM_LampPower.py`
- `scripts/vendor_examples/TestCOM_Mono9055.py`
- `scripts/device_tests/grab_single_frame.py`
- `scripts/device_tests/windows_setup.py`

## Required Hardware And Software

Hardware:

- Sciencetech monochromator
- Sciencetech filter wheel
- Sciencetech lamp power supply
- Allied Vision camera
- Compatible spectrometer supported by `seabreeze`

Software:

- Windows with Sciencetech COM components installed
- Python with `pywin32`, `vmbpy`, `seabreeze`, `astropy`, `numpy`, `matplotlib`, `opencv-python`
- Optional `pandas` for lamp power CSV plotting

Several scripts assume local Sciencetech install paths such as:

- `C:\Program Files (x86)\Sciencetech\SciencetechCOM\...`
- `C:\ProgramData\Sciencetech\SciencetechCOM\...`

## Which Script To Run

- Full acquisition sweep:
  - `python scripts/acquisition/data_acq_copilot_vimba.py --help`
- Camera-only FITS capture:
  - `python scripts/acquisition/apalo_frame_capture.py --help`
- Manual wavelength move and homing:
  - `python scripts/device_tests/simple_wavelength_select.py`
- Lamp COM check:
  - `python scripts/device_tests/TestCOM_LampPower.py`
- Monochromator COM check:
  - `python scripts/device_tests/TestCOM_Mono9055.py`
- Filter wheel COM check:
  - `python scripts/device_tests/TestCOM_FilterWheel-trinamic.py`
- Spectrometer darks:
  - `python scripts/analysis/spectrometer_darks.py`
- Lamp power CSV plots:
  - `python scripts/analysis/lamp_power_tests.py`
- Inspect a FITS file:
  - `python scripts/analysis/test_fits.py path/to/file.fits`

## Version Control Notes

- Manuals, QC docs, and vendor example scripts are kept in the repository for reference.
- `Software/` is ignored to avoid committing large installer binaries.
- Generated acquisition outputs such as FITS files, NumPy arrays, plots, and run directories are ignored.
