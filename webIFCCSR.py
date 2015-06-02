# CCSR web interface
# Usage: python webIFCCSR.py
# access through localhost:8080

import re
import csv
import web
import os
from web import form
#import numpy
#import matplotlib
#from matplotlib import pyplot as plt


ccsrStateDumpFile      = '../../data/ccsrState_dump_full.csv'
ccsrProfileDumpFile    = '../../data/profile_dump.csv'
ccsrStateDumpFileDebug = 'ccsrState_dump.csv'

render = web.template.render('templates/')

urls = (
    '/', 'index',
    '/images/(.*)', 'images'
)

#Web forms
myform = form.Form( 
    form.Checkbox('chkbxListen', value=''), 
    form.Checkbox('chkbxTracking', value=''), 
    form.Checkbox('chkbxProximity', value=''), 
    form.Checkbox('chkbxNavigation', value=''), 
    form.Checkbox('chkbxSonar', value=''), 
    form.Checkbox('chkbxEvasiveAction', value=''), 
    form.Checkbox('chkbxShowEmotion', value=''), 
    form.Textbox('arm_shoulder', value='45'), 
    form.Textbox('arm_elbow', value='5'), 
    form.Textbox('arm_wrist', value='0'), 
    form.Textbox('arm_hand', value='0'), 
    form.Textbox('arm_speed', value='50'), 
    form.Textbox('loc_x', value='0'), 
    form.Textbox('loc_y', value='0'), 
    form.Checkbox('chkbxArmDisable', value='checked'), 
    form.Textbox('pantilt_pan', value='0'), 
    form.Textbox('pantilt_tilt', value='0'), 
    form.Textbox('pantilt_speed', value='50'), 
    form.Checkbox('chkbxPantiltDisable', value='checked'), 
    form.Textbox('command', value=''),
    form.Checkbox('chkbxDebug'), 
    form.Checkbox('chkbxRefreshDump', value='checked'), 
    form.Textbox('heading', value='0'),
#    form.Dropdown('brain', ['CCSR', 'Lucy']),
    form.Dropdown('state', ['SM_REMOTE_CONTROLLED',
                            'SM_ORIENTATION',
                            'SM_EXPLORE'], value='SM_REMOTE_CONTROLLED'),
    form.Dropdown('objectRecogMode', ['colorThreshhold',
                            'shapeDetection'], value='colorThreshhold'),
    form.Dropdown('mission', ['diagnostics', 'findTargetByColor']))


# Telemetry class. Keeps track of CCSR state
class CCSRTelemetry:
   def __init__(self, useFifos):
      self.mapgridX=30
      self.mapgridY=30
      self.mapWidth=300
      self.mapHeight=300
      self.mapRegionX=self.mapWidth/self.mapgridX
      self.mapRegionY=self.mapHeight/self.mapgridY
      
      if useFifos:
         self.wfifo = open('/home/root/ccsr/nlp_fifo_in', 'w')
         self.rfifo = open('/home/root/ccsr/nlp_fifo_out', 'r')
      self.useFifos = useFifos   # If True, we pipe responses to CCSR. False in debg mode
      self.localData = {}
      for item in myform.inputs:
         self.localData[item.name] = item.value
      self.stateMap =  {"SM_REMOTE_CONTROLLED": "9",
                        "SM_ORIENTATION": "2",
                        "SM_EXPLORE": "7"}
      self.csvNameMap =  {"compass": "heading",
                          "proximity": "chkbxProximity",
                          "TrackObject": "chkbxTracking",
                          "navigationOn": "chkbxNavigation",
                          "sonarSensorsOn": "chkbxSonar",
                          "temperature": "temperature"}
      self.csvfile = {}
      self.telemetryDump = []
      self.responseQueue = []
      if self.useFifos:
         self.ip_addr = '192.168.1.129'
      else:
         self.ip_addr = 'localhost'
         
   # Read CSV dump file from CCSR
   def importTelemetry(self):
      if os.path.isfile(ccsrStateDumpFile): 
         statusDump = open(ccsrStateDumpFile, 'r')
      else:
         print "Can't open " + ccsrStateDumpFile + ", using static debug file"
         statusDump = open(ccsrStateDumpFileDebug, 'r')
      csvfile = csv.reader(statusDump)
      self.telemetryDump = []
      for el in csvfile:
         self.telemetryDump.append(el)

   # Sync local data with CSV dump from CCSR
   def updateLocalData(self):
      for item in ccsr.telemetryDump :
         if item[0] in self.csvNameMap:
            el = self.csvNameMap[item[0]]
            if el in self.localData:
               if self.isCheckbox(el):
                  if item[1] == '1':
                     self.localData[el] = 'checked'
                  else:
                     self.localData[el] = ''
               else:
                  self.localData[el] = item[1]

   # Return True if 'name' is an HTML checkbox
   def isCheckbox(self, name):
      return re.match('chkbx.+', name)

   # Translate HTML form entry (by 'id') into an CCSR command and store in list
   def createCommand(self, el):
      # If HTML form entry is of format <prefix>_<command>, extract the
      # <prefix>. E.g. arm_shoulder, translates to set arm <all fields>
      cmdTypeRaw = el
      cmdType = re.match('[a-zA-Z]+', el)
      if cmdType:
         cmdType = cmdType.group(0)
      if cmdType == 'command':
         self.responseQueue.append(self.localData['command'])
      elif cmdType == 'mission':
         # Missions not implemented yet
         print self.localData['mission']
      elif cmdType == 'state':
         self.responseQueue.append('set state ' + self.stateMap[self.localData['state']])
      elif cmdType == 'chkbxRefreshDump':
         self.responseQueue.append('dump disk')
      elif cmdType == 'chkbxListen':
         if self.localData['chkbxListen'] == 'checked':
            self.responseQueue.append('listen')
         else:
            self.responseQueue.append('listen 0')
      elif cmdType == 'chkbxTracking':
         if self.localData['chkbxTracking'] == 'checked':
            if self.localData['objectRecogMode'] == 'colorThreshhold':
               self.responseQueue.append('set track 1')
            elif self.localData['objectRecogMode'] == 'shapeDetection':
               self.responseQueue.append('set track 2')
         else:
            self.responseQueue.append('set track 0')
      elif cmdType == 'chkbxProximity':
         if self.localData['chkbxProximity'] == 'checked':
            self.responseQueue.append('set prox 1')
         else:
            self.responseQueue.append('set prox 0')
      elif cmdType == 'chkbxNavigation':
         if self.localData['chkbxNavigation'] == 'checked':
            self.responseQueue.append('set nav 1')
         else:
            self.responseQueue.append('set nav 0')
      elif cmdType == 'chkbxShowEmotion':
         if self.localData['chkbxShowEmotion'] == 'checked':
            self.responseQueue.append('set mood 1')
         else:
            self.responseQueue.append('set mood 0')
      elif cmdType == 'chkbxSonar':
         if self.localData['chkbxSonar'] == 'checked':
            self.responseQueue.append('set sonar 1')
         else:
            self.responseQueue.append('set sonar 0')
      elif cmdType == 'chkbxArmDisable':
         if self.localData['chkbxArmDisable'] == 'checked':
            self.responseQueue.append('set arm 0')
         else:
            self.responseQueue.append('set arm 1')
      elif cmdType == 'chkbxPantiltDisable':
         if self.localData['chkbxPantiltDisable'] == 'checked':
            self.responseQueue.append('set pantilt 0')
         else:
            self.responseQueue.append('set pantilt 1')
      elif cmdType == 'arm':
         self.responseQueue.append('set arm ' + self.localData['arm_shoulder'] + ' ' 
                                  + self.localData['arm_elbow'] + ' '
                                  + self.localData['arm_wrist'] + ' '
                                  + self.localData['arm_hand'] + ' '
                                  + self.localData['arm_speed'])
      elif cmdType == 'loc':
         self.responseQueue.append('goto ' + self.localData['loc_x'] + ' ' 
                                  + self.localData['loc_y'])
      elif cmdType == 'pantilt':
         self.responseQueue.append('set pantilt ' + self.localData['pantilt_pan'] + ' ' 
                                      + self.localData['pantilt_tilt'] + ' '
                                      + self.localData['pantilt_speed'])
      elif cmdType == 'heading':
         self.responseQueue.append('turnto ' + self.localData['heading'])
      elif cmdTypeRaw == 'motion_arrowUp':
         if self.localData['chkbxEvasiveAction'] == 'checked':
            self.responseQueue.append('move 4')
         else:
            self.responseQueue.append('move 3')
      elif cmdTypeRaw == 'motion_arrowDown':
         self.responseQueue.append('move 2 1000000')
      elif cmdTypeRaw == 'motion_arrowRight':
         self.responseQueue.append('turn 2 90')
      elif cmdTypeRaw == 'motion_arrowLeft':
         self.responseQueue.append('turn 2 -90')
      elif cmdTypeRaw == 'motion_stop':
         self.responseQueue.append('move 0')
      elif cmdTypeRaw == 'action_analyzeObject':
         self.responseQueue.append('obj analyze')
      elif cmdTypeRaw == 'action_calibrateCompass':
         self.responseQueue.append('calcomp')
      elif cmdTypeRaw == 'action_triangulate':
         self.responseQueue.append('triangulate')
      elif cmdTypeRaw == 'action_findObject':
         self.responseQueue.append('obj find')
      elif cmdTypeRaw == 'action_giveObject':
         self.responseQueue.append('obj give')
      elif cmdTypeRaw == 'action_pickupObject':
         self.responseQueue.append('obj pickup')
      elif cmdTypeRaw == 'action_dropObject':
         self.responseQueue.append('obj drop')
      elif cmdTypeRaw == 'action_orientationFull':
         self.responseQueue.append('orient full')
      elif cmdTypeRaw == 'action_orientationFwd':
         self.responseQueue.append('orient fwd')
      else:
         print 'unknown command'

   # Send command to CCSR through fifos      
   def response(self, s=''):
      m = s + '*'
      print s
      if self.useFifos:
         self.wfifo.write(m)
         self.wfifo.flush()
         # This should block untill cmd response is received. Used to sync.
         self.cmdResponse = self.rfifo.readline();  

   # send all accumulated commands to CCSR
   def sendCommands(self):
      # remove duplicates
      r = list(set(self.responseQueue))
      for el in r:
         self.response(el)


# Webpy image class, makes web images available
class images:
    def GET(self,name):
        ext = name.split(".")[-1] # Gather extension
        cType = {
            "png":"images/png",
            "jpg":"images/jpeg",
            "gif":"images/gif",
            "ico":"images/x-icon",
            "svg":"image/svg+xml"}

        if name in os.listdir('images'):  # Security
            web.header("Content-Type", cType[ext]) # Set the Header
            return open('images/%s'%name,"rb").read() # Notice 'rb' for reading images
        else:
            raise web.notfound()

# Main webpy class
class index:

   def GET(self):
      ccsr.importTelemetry()  
      ccsr.responseQueue = []
      ccsr.updateLocalData()
      user_data = web.input()  # Get parameters passed through html link
      form = myform()          # prepare HTML form
      for el in user_data:
        if (el=='locX'):
           ccsr.localData['loc_x'] = user_data[el]
        elif (el=='locY'):
           ccsr.localData['loc_y'] = user_data[el]
        elif(el=='id'):
           ccsr.createCommand(user_data[el])  # Create CCSR commands from web input
      ccsr.sendCommands()
      return render.webIFCCSR(ccsr, ccsr.telemetryDump)

   def POST(self): 
      cmdQueue = []
      ccsr.responseQueue = []
      form = myform() 
      formdata = web.input()
      # Find out if any HTML form data has changed by comparing to localdata
      # If changed, update localdata and add it to cmdQueue 
      for el in ccsr.localData:
         if el in formdata:
            if el == 'mission':
               if formdata[el] != 'none':
                  cmdQueue.append(el)
                  ccsr.localData[el] = formdata[el]
            elif el == 'command':
               if formdata[el] != '':
                  cmdQueue.append(el)
                  ccsr.localData[el] = formdata[el]
            elif ccsr.isCheckbox(el):
               if ccsr.localData[el] != 'checked':
                  ccsr.localData[el] = 'checked'
                  cmdQueue.append(el)
            else:      
               if ccsr.localData[el] != formdata[el]:
                  ccsr.localData[el] = formdata[el]
                  cmdQueue.append(el)
         else:
            if ccsr.isCheckbox(el):
               if ccsr.localData[el] == 'checked':
                  ccsr.localData[el] = ''
                  cmdQueue.append(el)
            else:
               print 'shouldnothappen'
      # Create CCSR commands from all entries in command queue 
      for el in cmdQueue:
        ccsr.createCommand(el) 
      # If refresh checkbox is checked, tell CCSR to dump telemetry,
      # import this telemetry and re-generate any pictures/graphs
      if 'chkbxRefreshDump' in formdata:
         ccsr.createCommand('chkbxRefreshDump') 
         ccsr.importTelemetry()
         ccsr.updateLocalData()
#         data=numpy.loadtxt(ccsrProfileDumpFile,skiprows=1,delimiter=',')
#         y=data[:,1]
#         x=data[:,0]
#         plt.plot(x,y)
#         plt.savefig('images/sonarProfile.png',dpi=100)
      ccsr.sendCommands()
      if not form.validates(): 
         return render.webIFCCSR(ccsr, ccsr.telemetryDump)
      else:
         return render.webIFCCSR(ccsr, ccsr.telemetryDump)

useFifos = False     # Only set True if integrated with CCSR robot platform
ccsr = CCSRTelemetry(useFifos);

if __name__ == "__main__":
    app = web.application(urls, globals())
    app.run()
