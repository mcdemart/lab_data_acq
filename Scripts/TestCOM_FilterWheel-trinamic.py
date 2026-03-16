import win32com.client

class FirstEventHandler:
    def OnError(self, errMessage):
        print ("Error = " + errMessage)
    def OnPropertyChanged(self, propName):
        print ("Prop change = " + propName)
		
fw = win32com.client.Dispatch("SciencetechCom.SciFilterWheel_API")
win32com.client.WithEvents(fw, FirstEventHandler)
print (fw.SetClassName("StepperMotor_FilterWheel.FilterWheel", "C:\Program Files (x86)\Sciencetech\SciencetechCOM\SciModules\StepperMotor_FilterWheel.dll"))
print (fw.SetConfigFile("C:\ProgramData\Sciencetech\SciencetechCOM\SciModules\Config\StepperMotorFilterWheel.config"))
numFilters = fw.NumberOfFilters
print (numFilters)
s = ""  # define a string variable
s=(fw.GetFilterDescription(2, s))
print (s)
print (s[1])                    # should contain the string value for the filter description
minWave = 0.0
minWave = fw.GetMinimumWavelength(3, minWave)
print (minWave)
print (minWave[1])

print (fw.Connect())
print (fw.IsConnected)

fw.OpenConfigWindow()
