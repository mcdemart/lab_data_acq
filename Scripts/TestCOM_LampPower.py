
import win32com.client

class FirstEventHandler:
    def OnError(self, errMessage):
        print ("Error = " + errMessage)
    def OnPropertyChanged(self, propName):
        print ("Prop change = " + propName)

mo =  win32com.client.Dispatch("SciencetechCom.SciLampPowerSupply_API")
win32com.client.WithEvents(mo, FirstEventHandler)
# print (mo.SetClassName("Sci601LampPower.LampPower", "C:\Program Files (x86)\Sciencetech\SciencetechCOM\SciModules\SciLampPower.dll"))

print (mo.SetClassName("Sci601LampPower.LampPower601", "C:\Program Files (x86)\Sciencetech\SciencetechCOM\SciModules\Sci601LampPower.dll"))

print (mo.SetConfigFile("C:\ProgramData\Sciencetech\SciencetechCOM\SciModules\Config\SciPowerControl_XE.config"))

mo.OpenConfigWindow()
mo.Connect()