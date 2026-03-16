import win32com.client

class FirstEventHandler:
    def OnError(self, errMessage):
        print ("Error = " + errMessage)
    def OnPropertyChanged(self, propName):
        print ("Prop change = " + propName)
         
mo =  win32com.client.Dispatch("SciencetechCom.SciMono_API")
win32com.client.WithEvents(mo, FirstEventHandler)
print (mo.SetClassName("Mono9055_StepperMotor.Mono9055", r"C:\Program Files (x86)\Sciencetech\SciencetechCOM\SciModules\Mono9055_StepperMotor.dll"))
print (mo.SetConfigFile(r"C:\ProgramData\Sciencetech\SciencetechCOM\SciModules\Config\StepperMotorMono.config"))
mo.OpenConfigWindow()

disp = 1.0
disp = mo.GetDispersion(0, disp)
print (disp)
print (disp[1])

mo.Connect()
mo.SetAutoGrating(False)
