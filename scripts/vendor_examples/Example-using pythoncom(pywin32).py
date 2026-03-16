import win32com.client
import pythoncom
import time
import numpy as np


class FirstEventHandler:
    def OnError(self, errMessage):
        print ("Error = " + errMessage)
        raise RuntimeError(errMessage)
    def OnPropertyChanged(self, propName):
        print ("Prop change = " + propName)

pythoncom.CoInitialize() 

mono = win32com.client.Dispatch("SciencetechCom.SciMono_API")
win32com.client.WithEvents(mono, FirstEventHandler)
mono.SetClassName("Mono9055_StepperMotor.Mono9055", "C:/Program Files (x86)/Sciencetech/SciencetechCOM/SciModules/Mono9055_StepperMotor.dll")
mono.SetConfigFile("C:/ProgramData/Sciencetech/SciencetechCOM/SciModules/Config/StepperMotorMono.config")

fw = win32com.client.Dispatch("SciencetechCom.SciFilterWheel_API")
win32com.client.WithEvents(fw, FirstEventHandler)
print (fw.SetClassName("StepperMotor_FilterWheel.FilterWheel", "C:\Program Files (x86)\Sciencetech\SciencetechCOM\SciModules\StepperMotor_FilterWheel.dll"))
print (fw.SetConfigFile("C:\ProgramData\Sciencetech\SciencetechCOM\SciModules\Config\StepperMotorFilterWheel.config"))


r = mono.Connect()
print("Mono connection success:", r)
mono.Stop()
time.sleep(0.5)
mono.Home()
time.sleep(0.5)
while not mono.IsHomed: # Ideally add a timeout
    time.sleep(1)
    pythoncom.PumpWaitingMessages() 
    print("connected:", mono.IsConnected, 
    "homing:", mono.IsHoming,
    "homed:", mono.IsHomed,
    "moving:", mono.IsMoving)

r = fw.Connect()
print("Filter Wheel connection success:", r)
fw.Stop()
time.sleep(0.5)
fw.Home()
time.sleep(0.5)
while not fw.IsHomed: # Ideally add a timeout
    time.sleep(1)
    pythoncom.PumpWaitingMessages() 
    print("connected:", fw.IsConnected, 
    "homing:", fw.IsHoming,
    "homed:", fw.IsHomed,
    "moving:", fw.IsMoving)
    
def Moveto(wavelength):
    mono.SetWavelength(wavelength)
    time.sleep(0.5)
    fw.MoveToFilterWavelength(wavelength)
    time.sleep(0.5)
    pythoncom.PumpWaitingMessages() 
    time.sleep(0.5)
    while mono.IsMoving: # Ideally add a timeout
        time.sleep(1)
        pythoncom.PumpWaitingMessages() 
        print("moving:", mono.IsMoving)

#wave_test = [200, 470, 480, 625, 745, 755, 1000, 1100]
#wave_test = [300, 800, 900]
#wave_test = [400, 900, 1000]
#wave_test = [500, 600, 700, 800, 900, 1000]
# wave_test = np.arange(550, 561, step = 1)
# print(wave_test)
# print("Starting Wavelength Sweep")
# for i in range(len(wave_test)):
#     Moveto(wave_test[i])
#     print('wavelength = ', wave_test[i], ' nm')
#     time.sleep(30)
wave = 850
Moveto(wave)
fw.MoveToFilterWavelength(wave)

#print("Starting Wavelength Sweep")
#Moveto(400)
#time.sleep(1)
#Moveto(450)
#time.sleep(1)
#Moveto(500)
#time.sleep(1)
#Moveto(550)
#time.sleep(1)
#Moveto(600)
#time.sleep(1)
#Moveto(650)
#time.sleep(1)
#Moveto(700)
#time.sleep(1)
print("Done")