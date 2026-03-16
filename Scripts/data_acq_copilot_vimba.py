"""
    data_acq_copilot_vimba.py

    Cleaned and modularized data acquisition script using Vimba SDK: acquires spectrometer and camera darks,
    performs wavelength and power sweep, saves images, spectra, and plots.
"""
import argparse
import time
import logging
from pathlib import Path
from datetime import date

import numpy as np
import cv2
import matplotlib.pyplot as plt
import pythoncom
import win32com.client
from seabreeze.spectrometers import Spectrometer
import vmbpy
from astropy.io import fits

# --- Event handler for COM errors and property changes ---
class FirstEventHandler:
    def OnError(self, errMessage):
        logging.error(f"COM Error: {errMessage}")
        raise RuntimeError(errMessage)
    def OnPropertyChanged(self, propName):
        logging.info(f"Property changed: {propName}")

# --- Device initialization ---
def init_monochromator():
    logging.info("Initializing monochromator...")
    pythoncom.CoInitialize()
    mono = win32com.client.Dispatch("SciencetechCom.SciMono_API")
    win32com.client.WithEvents(mono, FirstEventHandler)
    mono.SetClassName(
        "Mono9055_StepperMotor.Mono9055",
        r"C:\Program Files (x86)\Sciencetech\SciencetechCOM\SciModules\Mono9055_StepperMotor.dll"
    )
    mono.SetConfigFile(
        r"C:\ProgramData\Sciencetech\SciencetechCOM\SciModules\Config\StepperMotorMono.config"
    )
    mono.Connect()
    mono.Stop()
    mono.Home()
    while not mono.IsHomed:
        time.sleep(0.5)
        pythoncom.PumpWaitingMessages()
        logging.info("Homing monochromator...")
    if not mono.IsHomed:
        raise RuntimeError("Monochromator failed to home.")
    logging.info("Monochromator initialized successfully.")
    logging.info("")
    return mono

def init_filter_wheel():
    logging.info("Initializing filter wheel...")
    fw = win32com.client.Dispatch("SciencetechCom.SciFilterWheel_API")
    win32com.client.WithEvents(fw, FirstEventHandler)
    fw.SetClassName(
        "StepperMotor_FilterWheel.FilterWheel",
        r"C:\Program Files (x86)\Sciencetech\SciencetechCOM\SciModules\StepperMotor_FilterWheel.dll"
    )
    fw.SetConfigFile(
        r"C:\ProgramData\Sciencetech\SciencetechCOM\SciModules\Config\StepperMotorFilterWheel.config"
    )
    fw.Connect()
    fw.Stop()
    fw.Home()
    while not fw.IsHomed:
        time.sleep(0.5)
        pythoncom.PumpWaitingMessages()
        logging.info("Homing filter wheel...")
    if not fw.IsHomed:
        raise RuntimeError("Filter wheel failed to home.")
    logging.info("Filter wheel initialized successfully.")
    logging.info("")
    return fw

def init_lamp():
    logging.info("Initializing lamp power supply...")
    mo = win32com.client.Dispatch("SciencetechCom.SciLampPowerSupply_API")
    win32com.client.WithEvents(mo, FirstEventHandler)
    mo.SetClassName(
        "Sci601LampPower.LampPower601",
        r"C:\Program Files (x86)\Sciencetech\SciencetechCOM\SciModules\Sci601LampPower.dll"
    )
    mo.SetConfigFile(
        r"C:\ProgramData\Sciencetech\SciencetechCOM\SciModules\Config\SciPowerControl_XE.config"
    )
    while not mo.Connect():
        logging.info("Connecting to lamp...")
        time.sleep(0.5)

    # Ensure lamp is ready to accept power changes
    while mo.IsLampOn:
        logging.info("Lamp is on, trying to turn it off...")
        mo.PowerLamp(False)
        time.sleep(10)
    logging.info("Lamp power supply connected successfully.")

    while not mo.IsLampOn:
        logging.info("Turning lamp on...")
        mo.PowerLamp(True)
        time.sleep(10)
    
    # Set initial lamp power
    logging.info("Setting initial lamp power to 70%...")
    mo.SetOutputPercentage(70.0)
    time.sleep(10)
    
    if not mo.IsConnected:
        raise RuntimeError("Lamp power supply failed to connect.")
    logging.info("Lamp power supply initialized successfully.")
    logging.info("")
    return mo
# --- Move to wavelength ---
def moveto(mono, fw, wavelength, timeout=30):
    mono.SetWavelength(wavelength)
    fw.MoveToFilterWavelength(wavelength)
    start = time.time()
    while mono.IsMoving or (time.time() - start) < timeout:
        time.sleep(0.2)
        pythoncom.PumpWaitingMessages()
    logging.info(f"Moved to {wavelength} nm")

# --- Spectrometer dark frames ---
def acquire_spec_darks(num_darks, exposure_s):
    spec = Spectrometer.from_first_available()
    spec.integration_time_micros(int(exposure_s * 1e6))
    time.sleep(0.5)
    darks = [spec.spectrum() for _ in range(num_darks)]
    spec.close()
    return np.median(darks, axis=0)

# --- Camera dark frames using Vimba ---
def acquire_cam_darks(cam, num_darks, save_dir=None):
    frames = []
    for i in range(num_darks):
        frame = cam.get_frame(timeout_ms=5000)
        # Use the frame in its native format without conversion
        dark_frame = np.copy(frame.as_numpy_ndarray())
        frames.append(dark_frame)
        # Optionally save individual dark frames
        if save_dir:
            fits.writeto(save_dir / f"dark_frame_{i}.fits", dark_frame.astype(np.float32), overwrite=True)
    return np.median(frames, axis=0) if frames else None

# --- Main acquisition loop ---
def run_acquisition(args):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    today = date.today()
    out_dir = Path(args.output_dir) / f"acq_{today}_{args.tranch}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # make subframe directory
    subframe_dir = out_dir / "subframes"
    subframe_dir.mkdir(parents=True, exist_ok=True)

    mono = init_monochromator()
    fw = init_filter_wheel()
    lamp = init_lamp()

    spec_exp = args.spec_exp_s

    # Initialize Vimba and camera
    with vmbpy.VmbSystem.get_instance() as vmb:
        logging.info("Initializing Vimba camera...")
        cams = vmb.get_all_cameras()
        if not cams:
            logging.error("No camera detected.")
            return
        
        with cams[0] as cam:
            # Configure camera settings
            # Convert exposure time from seconds to microseconds for Vimba
            cam_exp_us = int(args.cam_exp_s * 1e6)
            try:
                # First check if ExposureTime feature exists and its unit
                exposure_feature = cam.get_feature_by_name('ExposureTime')
                logging.info(f"ExposureTime unit: {exposure_feature.get_unit()}")
                cam.ExposureTime.set(cam_exp_us)
            except Exception as e:
                logging.error(f"Failed to set exposure time: {e}")
                # Try alternative exposure time feature names
                try:
                    cam.ExposureTimeAbs.set(cam_exp_us)
                    logging.info("Using ExposureTimeAbs feature")
                except:
                    logging.error("Could not set camera exposure time")
                    raise
            
            try:
                binning_h = cam.get_feature_by_name('BinningHorizontal')
                binning_v = cam.get_feature_by_name('BinningVertical')
                binning_h.set(args.binning)
                binning_v.set(args.binning)
            except Exception as e:
                logging.warning(f"Could not set binning: {e}")
                # Some cameras might use different binning feature names
                try:
                    binning_x = cam.get_feature_by_name('BinningX')
                    binning_y = cam.get_feature_by_name('BinningY')
                    binning_x.set(args.binning)
                    binning_y.set(args.binning)
                except:
                    logging.warning("Binning not supported or uses different feature names")
            
            try:
                trigger_mode = cam.get_feature_by_name('TriggerMode')
                trigger_mode.set('Off')  # Free running mode
            except Exception as e:
                logging.warning(f"Could not set trigger mode: {e}")
            
            try:
                acq_mode = cam.get_feature_by_name('AcquisitionMode')
                acq_mode.set('SingleFrame')
            except Exception as e:
                logging.warning(f"Could not set acquisition mode: {e}")
            
            # Set pixel format to 16-bit mono if available
            try:
                pixel_format_feature = cam.get_feature_by_name('PixelFormat')
                pixel_format_feature.set('Mono16')
                pixel_format = 'Mono16'
            except:
                try:
                    pixel_format_feature = cam.get_feature_by_name('PixelFormat')
                    pixel_format_feature.set('Mono12')
                    pixel_format = 'Mono12'
                except:
                    # Use whatever format the camera supports
                    try:
                        pixel_format_feature = cam.get_feature_by_name('PixelFormat')
                        pixel_format = pixel_format_feature.get()
                    except:
                        pixel_format = "unknown"
                    logging.warning(f"Using camera's default pixel format: {pixel_format}")
            
            logging.info(f"Camera initialized: {cam.get_id()}")
            try:
                actual_exposure = cam.ExposureTime.get()
            except:
                try:
                    actual_exposure = cam.ExposureTimeAbs.get()
                except:
                    actual_exposure = "unknown"
            logging.info(f"Camera exposure time set to {actual_exposure} us")
            try:
                logging.info(f"Camera binning set to {cam.BinningHorizontal.get()}x{cam.BinningVertical.get()}")
            except:
                logging.info("Camera binning: not available or using different feature names")
            logging.info(f"Camera pixel format: {pixel_format}")
            logging.info("")

            # Turn lamp OFF for dark acquisition
            
            logging.info("Turning lamp off for dark acquisition...")
            while lamp.IsLampOn:
                logging.info("Turning lamp off for dark acquisition...")
                lamp.PowerLamp(False)
                time.sleep(10)  # Wait for lamp to fully turn off

            logging.info("Acquiring spectrometer darks...")
            cal_dark = acquire_spec_darks(args.num_darks, spec_exp)
            np.save(out_dir / "spec_dark.npy", cal_dark)

            logging.info("Acquiring camera darks...")
            cam_dark = acquire_cam_darks(cam, args.num_darks, subframe_dir)  # Pass subframe_dir to save individual darks
            if cam_dark is not None:
                cam_dark = cam_dark.astype(np.float32)  # Changed from np.int16 to np.float32
                # save cam dark as a FITS file for compatibility
                fits.writeto(out_dir / "cam_dark.fits", cam_dark, overwrite=True)

            # Turn lamp back ON for science acquisition
            logging.info("Turning lamp on for science acquisition...")
            while not lamp.IsLampOn:
                logging.info("Turning lamp on...")
                lamp.PowerLamp(True)
                time.sleep(10)

            wavelengths = np.arange(args.wave_start, args.wave_stop + 1, args.wave_step)
            powers = np.arange(args.power_start, args.power_stop + 1, args.power_step)
            logging.info(f"Acquiring data for wavelengths: {wavelengths} nm and powers: {powers}%")
            for wl in wavelengths:
                moveto(mono, fw, wl)
                logging.info(f"Wavelength: {wl} nm")
                for pw in powers:
                    if args.power_start != args.power_stop:
                        lamp.SetOutputPercentage(float(pw))  # Ensure it's a float
                        time.sleep(args.lamp_settle)
                        logging.info(f"Lamp power set to {pw}%")
                    else:
                        logging.info(f"Using fixed lamp power: {pw}% (no change)")
                    
                    # capture camera images and median combine them
                    logging.info(f"Capturing {args.num_science} images at {wl} nm and {pw}% power")
                    frames = []
                    for _ in range(args.num_science):
                        frame = cam.get_frame(timeout_ms=5000)
                        # Use the frame in its native format without conversion
                        frames.append(np.copy(frame.as_numpy_ndarray()))
                        time.sleep(0.5)
                    
                    logging.info(f"Captured {len(frames)} frames, shape {frames[0].shape} at {wl} nm and {pw}% power")
                    if len(frames) > 0:
                        # Save individual frames
                        for i, frame in enumerate(frames):
                            fits.writeto(subframe_dir / f"{wl}nm_{pw}_frame_{i}.fits", frame.astype(np.float32), overwrite=True)

                        # median combine the frames
                        logging.info(f"Combining {len(frames)} frames")
                        img = np.median(frames, axis=0)
                    else:
                        logging.warning(f"No frames captured at {wl} nm and {pw}% power")
                        img = None

                    spec = Spectrometer.from_first_available()
                    spec.integration_time_micros(int(spec_exp * 1e6))
                    time.sleep(0.2)
                    spectrum = spec.spectrum()
                    spec.close()

                    spectrum[1] -= cal_dark[1]

                    # subtract camera dark if available
                    if cam_dark is not None and img is not None:
                        img = img.astype(np.float32) - cam_dark  # Changed from np.int16 to np.float32

                    base = f"{wl}nm_{pw}"
                    if img is not None:
                        cv2.imwrite(str(out_dir / f"pl_{base}.png"), img)
                        fits.writeto(out_dir / f"{base}.fits", img.astype(np.float32), overwrite=True)  # Ensure float32
                    else:
                        logging.warning(f"No image captured for {base}")
                    np.save(out_dir / f"{base}_spectrum.npy", spectrum)

                    plt.figure()
                    plt.plot(spectrum[0], spectrum[1])
                    plt.ylim(0,42000)
                    plt.xlim(args.wave_start-100, args.wave_stop+100)
                    plt.title(f"Spectrum {wl}nm @ {pw}%")
                    plt.savefig(out_dir / f"sp_{base}.png")
                    plt.close()

    logging.info("Data acquisition complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lantern data acquisition")
    parser.add_argument("--output-dir", default="./data", help="Base output directory")
    parser.add_argument("--tranch", type=int, default=1, help="Data version (tranch)")
    parser.add_argument("--num-darks", type=int, default=10, help="Number of dark frames")
    parser.add_argument("--num-science", type=int, default=3, help="Number of science frames to median combine")
    parser.add_argument("--spec-exp-s", type=float, default=0.06, help="Spectrometer exposure (s)")
    parser.add_argument("--cam-exp-s", type=float, default=1.0, help="Camera exposure (s)")
    parser.add_argument("--binning", type=int, default=1, help="Camera binning mode")
    parser.add_argument("--lamp-settle", type=float, default=2.0, help="Lamp settle time (s)")
    parser.add_argument("--power-start", type=int, default=100, help="Lamp power start (%)")
    parser.add_argument("--power-stop", type=int, default=100, help="Lamp power stop (%)")
    parser.add_argument("--power-step", type=int, default=2, help="Lamp power step (%)")
    parser.add_argument("--wave-start", type=int, default=1300, help="Wavelength start (nm)")
    parser.add_argument("--wave-stop", type=int, default=1450, help="Wavelength stop (nm)")
    parser.add_argument("--wave-step", type=int, default=1, help="Wavelength step (nm)")
    args = parser.parse_args()
    
    # print parameters out neatly
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logging.info("Starting data acquisition with parameters:")
    for key, value in vars(args).items():
        logging.info(f"{key}: {value}")
    # Run the acquisition
    run_acquisition(args)