#!/usr/bin/python2.6

import argparse
import sys
import json
import requests
from ordereddict import OrderedDict
from requests.auth import HTTPBasicAuth
#from requests import Request, Session
#import pprint
import time
import datetime
import shelve
#import com.cisco.mateapi
import gettun
import os
import getpass
import subprocess
from tabulate import tabulate

try:
  import MATE_libs as mod_MATE_libs
except:
  print "[ERROR] - Cisco Mate Design Python Libraries not found - \"MATE-libs.py\""
  sys.exit(2)

###########################################################################################################
''' Classes Definitions '''

class PlanFile:
	def __init__(self, wae):
		self.wae = wae
		self.plan = ""                         # An empty plan file
	    self.stage_id = ""                      # The stage ID of the working plan file
	    self.plan_type = "binary"               # Either "text" or default "binary"
	    self.is_loaded = False                  # Boolean, is the plan loaded in the WAE Stage ID?
 
	def setStageID(self, stage_id):
		"""
		---------------------------------------------------------
		Sets the Stage ID for the WAE Server
		"""		
		self.stage_id = str(stage_id)
		return 1 # EXIT_SUCCESS

	def getStageIDNew(self):
	    """
	    ---------------------------------------------------------
	    Gets a new Staging ID from the WAE Server for association
	    with the plan file.
	    """	    
	       
	    payload = { "mergePolicy" : "STRICT", "fromWorking" : False }	    	   
	    resource = "/wae/network/modeled/stage-manager/create"

	    data = waeApiCall(self.wae, resource, "post", "json", payload)
	
	  	try:  		
	    	return data.get("stage_id").get("id")
	  	except:
	    	return 0 # EXIT_FAILED

	  def fnDoCopyPlan(self, plan):
	    """
	    ---------------------------------------------------------
	    Copies an input plan file to the current plan file object
	    """	    
	    self.plan = plan
	    return 1 # EXIT_SUCCESS

	  def getWaePlan(self, stage_id=""):
	    """
	    ---------------------------------------------------------
	    Gets a Wae Plan file from the server and places it into
	    the object.

	    Optional:
	      svStageId : If provided get the file from the Stage ID.
	                  Defaults to "", meaning download the WAE Current Model
	    Returns: 0|1
	      1         : Success, plan file retrived
	      0         : Failed, plan file not retrived
	    """	    
	    data_type = "json"
	    if (stage_id != ""):
	      self.stage_id = stage_id
	      resource = "/wae/network/modeled/plan-manager/stage/get-current-model"	      
	      method = "post"	      
	      payload = { "stageId" : { "id" : self.stage_id } }	      	      
	    else:
	      resource = "/wae/network/modeled/plan-manager/get-current-model"
	      method = "get"
	      payload = {}

	    # Step 1 - Check if there is a plan file loaded
	    if (self.getWaePlanIsLoaded(stage_id) != True):
	      print "[WARNING] - fnGetWaePlan - Plan not currently loaded!"
	      return 0 # EXIT_FAILED

	    # Step 2 - Get the plan file
		
		#planFile = fnDoWaeApiSubmit(self.svWaeUrl,svNameSpace,svMethod,dicPayLoad,svPayloadType,bvDebug)
		planFile = waeApiCall(self.wae, resource, method, data_type, payload)
		# May need to adjust this error handling in the future
		if (planFile is None):
			return 0 # EXIT_FAILED
		else:
			self.plan = planFile
			return 1 # EXIT_SUCCESS
	    

	  def getWaePlanIsLoaded(self, stage_id=""):
	    """
	    ---------------------------------------------------------
	    Confirms if the Wae Plan file is loaded onto the WAE server

	    Optional:
	      svStageId: If provided push the file to a Stage ID.
	                 Defaults to "", meaning uplaod to the WAE Current Model
	    """	    

	    data_type = "json"
	    if (stage_id != ""):
	      # The Query returns a json response
	      self.stage_id = stage_id
	      resource = "/wae/network/modeled/plan-manager/stage/is-model-loaded"
	      method = "post"
	      payload = { "stageId" : { "id" : self.stage_id } }	      
	    else:
	      # The Query returns a boolean response
	      resource = "/wae/network/modeled/plan-manager/is-model-loaded"
	      method = "get"
	      payload ={}

		  #response = fnDoWaeApiSubmit(self.svWaeUrl,svNameSpace,svMethod,dicPayLoad,svPayloadType,bvDebug)
		  response = waeApiCall(self.wae, resource, method, data_type, payload)
		  if (stage_id != ""):                        # Handler for Staged Plan "Is loaded" response
		    if ("planLoaded" in response):
		      self.is_loaded = response.get("planLoaded")		      
		      return 1 # EXIT_SUCCESS
		    else:		      
		      return 0 # EXIT_FAILED
		  else:                                        # Handler for Current Plan "Is loaded" response
		    if (response in (True,False)):
		      self.is_loaded = response
		      if (response == True):		        
		        return 1 # EXIT_SUCCESS
		      else:		        
		        return 0 # EXIT_FAILED
		    else:
		      print "[ERROR] - getWaePlanIsLoaded - Unexpected response"
		      sys.exit(2) # EXIT_FAILED
	    

	  def putWaePlan(self, stage_id=""):
	    """
	    ---------------------------------------------------------
	    Pushes the Object's Plan file into the WAE server

	    Optional:
	      svStageId: If provided push the file to a Stage ID.
	                 Defaults to "", meaning uplaod to the WAE Current Model
	    """	   

	    if (stage_id != ""):
	      self.stage_id = stage_id
	      resource = "/wae/network/modeled/plan-manager/stage/process-new/"
	      resource = resource + self.stage_id
	    else:
	      resource = "/wae/network/modeled/plan-manager/process-new-from-file/"

	    # THIS MAY BE AN ISSUE #
	    # <ADD version check for ruquests here via WAE_supports.py>
	    # The requests module needs to be updated to version +2.4.x
	    # The requests library need to support multipart file upload of a binary file.
	    # A files payload requires a "File" type object
	    # We use StringIO.StringIO() to turn the file content binary string into a file object type.
	    # Requests will take the tuple {filename,filehandle,content-header} and run filehandle.read()
	    fileContents = StringIO.StringIO(self.plan)
	    payload = {'bin': ('planfile.pln', fileContents, {'Expires': '0'})}	    
	    method = "put"
	    data_type = "files"

	    
		#svResponse = fnDoWaeApiSubmit(self.svWaeUrl,svNameSpace,svMethod,dicPayload,svPayloadType,bvDebug)
		response = waeApiCall(self.wae, resource, method, data_type, payload)
		if (self.getWaePlanIsLoaded(stage_id)):	       
			if (self.is_loaded):
		  		return 1 # EXIT_SUCCESS
			else:
		  		return 0 # EXIT_FAILED
		else:
			return 0 # EXIT_FAILED


###########################################################################################################

''' Functions Declarations '''

def writeLog(customer_name, id, action, line):
	log_file = open(os.path.basename(__file__)[:-3] + ".log", "a") 
	ft = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
	log_file.write(ft + "\t%s\t%s\t[%s]%s\n" % (customer_name, id, action, line))
	log_file.close()
	

def responsePrint(content, funcname):
	print ("----------------'%s' Response --------------------") % funcname
	print json.dumps(content, indent=2)
	print ("---------------- End of '%s' Response -----------------") % funcname

def isDone(wae, job_id, max_sleep_time):
	sleep_time = 5
	while(sleep_time <= max_sleep_time):
		print "MESSAGE: sleep for %d seconds" % sleep_time

		time.sleep(sleep_time)
		job_state = checkJobState(wae, job_id)
		if(job_state == 1):
			print "MESSAGE: job %s executed successfully" % job_id
			return True
		elif(job_state == -1):
			print "ERROR: getJobState - unexpected response from server"
			return False
		else:
			sleep_time = sleep_time + 5

	return False 

def dbUpdate(option, request_id, target_field="", target_value=""):
	db = shelve.open('db.dat', writeback=True)
	if(option==0):
		db[requestid][target_field] = target_value
		db.close()
	elif(option==1):
		del db[request_id]
	db.close()


'''def getTunnelID(source, tunnel_name, delete=False):
	conn = com.cisco.mateapi.ServiceConnectionManager.newService()
	plan = conn.getPlanManager().newPlanFromFilesystem("/opt/cariden/work/pce-test.txt")
	sleepTime = 20
	sleep = False

	while(True): 
		file_mod_time = os.stat("/opt/cariden/work/pce-test.txt").st_mtime
		timeDiff = (time.time() - file_mod_time)/60
		print "MESSAGE: there is %d time difference between current time and last modified time of the snapshot file" % timeDiff

		if (timeDiff < 420 or delete == True):
			try:
				nodeKey = com.cisco.mateapi.pln.net.NodeKey(source)
				lspKey = com.cisco.mateapi.pln.net.LSPKey(nodeKey, tunnel_name)
				output = plan.getNetwork().getLSPManager().getLSP(lspKey).getAllUserProperties()
			except:
				print "MESSAGE: LSP not found, wait for snapshot to be updated"
				if(sleep == True):
					sleepTime = sleepTime - 5
					if(sleepTime < 0):
						print "ERROR: timeout reached, starting to roll back..."
						break

				print "MESSAGE: sleep for %d seconds" % sleepTime
				sleep = True
				time.sleep(sleepTime)
				continue

			if (output.has_key("USR::TunnelInterfaceId")):
				return str(output.get("USR::TunnelInterfaceId"))
			else:
				return ""
		else:
			print "MESSAGE: sleep for %d seconds" % sleepTime
			time.sleep(sleepTime)
	return ""
'''

def waeApiCall(wae, resource, method, data_type, payload=""):
	
	q = wae + resource	
	if(data_type == "json")
		p = json.dumps(payload)
		h = {"content-type":"application/json"}
	if(data_type == "files")
		para = {"planType" : "binary"}
	try:
		
		if(method == "post"):
			r = requests.post(q, data=p, headers=h)
		if(method == "get"):
			r = requests.get(q)
		if(method == "put"):
			if(data_type == "files"):
				r = requests.put(q, params=para, files=payload)			
			r = requests.put(q, data=p, headers=h)		
		reply = r.json()
		return(reply)
	except:
		print "ERROR: problems connecting to WAE server"
		sys.exit(2)

def ncsApiCall(ncs, resource, method, payload=""):
	p = json.dumps(payload)
	#pprint.pprint(p)
	q = ncs + resource
	h_pull = {'Accept':'application/vnd.yang.data+json'}
	h_push = {'Content-Type':'application/vnd.yang.data+json'}
	a = HTTPBasicAuth('admin', 'admin')

	#print p, q, h, a

	#try:
	if(method == 'post'):	
		r = requests.post(q, auth=a, data=p, headers=h_push)
	if(method == 'get'):
		r = requests.get(q, auth=a, headers=h_pull)
	if(method == 'delete'):
		r = requests.delete(q, auth=a, headers=h_pull)
	if(method == 'put'):
		r = requests.put(q, auth=a, data=p, headers=h_push) 
	#reply = r.json()
	return(r)
	#except:
		#print "ERROR: Problems connecting to NCS server"
		#sys.exit(2)

def checkJobState(wae, job_id):
	payload = {
	 	"jobId":{
	 		"id":job_id
	 	}
	}
	resource = "/wae/network/deployer/job/jobState"
	method = "post"
	data_type = "json"

	try:
		data = waeApiCall(wae, resource, method, data_type, payload)
		responsePrint(data, "checkJobState")
		if(data.get("jobState")=="SUCCESS"):
			return 1
		else:
			return 0
	except:
		return -1

def rollBack(wae, source, tunnel_name, request_id):
	response = deleteTunByName(wae, src, tname)
	timeLeft = 5
	if(isDone(wae, response, timeLeft)):
		dbUpdate(1, request_id)
		print "MESSAGE: Tunnel deleted, initial status restored"
	else:
		print "ERROR: Something went wrong when doing tunnel deletion..."

def createBasic(wae, tunnel_name, source, destination):
	payload = { 
		"teTunnel": {
			"name":tunnel_name,
			"source":source,
			"destination":destination,
			"type":"RSVP"
		}
	}
	resource = "/wae/network/modeled/entities/tunnel/pcep/new/create-basic"
	method = "post"
	data_type = "json"

	data = waeApiCall(wae, resource, method, data_type, payload)
	responsePrint(data, "createBasic")
	print "MESSAGE: PCEP tunnel ready to be created, here are the details:"
	for tunnelPath in data["teTunnelPaths"]["TeTunnelPathWithSize"]:
		#print "\tSize %s of tunnel path %s, hops passed through are %s and it is %s" % (tunnelPath["size"], tunnelPath["TETunnelPath"]["name"], tunnelPath["TETunnelPath"]["hops"], tunnelPath["TETunnelPath"]["standBy"])
		print "\tSize " + tunnelPath["size"] + " of tunnel path " + tunnelPath["TETunnelPath"]["name"] + ", hops passed through are",
		for hop in tunnelPath["TETunnelPath"]["hops"]:
			print hop,
		print "and it is " + tunnelPath["TETunnelPath"]["standBy"]
		
	return data
def createPW (wae, action, source, class_id, tunnel_ref, dst_ip, pw_id):
	
	resource = "/api/running/services"
	method = "post"
	if(action == "add"):
		#payload = {"routes":OrderedDict([("net","2.2.2.2/32"), ("interface","10.10.10.10")])}
		#payload = {"static:static":OrderedDict([("node",host),("prefix",staticPrefix), ("out",tunnelRef)])}
		payload = {"pw:pw":
			OrderedDict([("node", source), ("classid", class_id), ("tunnelnum", tunnel_ref), ("peeraddr", dst_ip), ("pwid":pw_id)])
		}
		#print payload
		data = ncsApiCall(ncs, resource, method, payload)
		#print data.status_code
		if data.status_code == 201:
			return 1 # EXIT_SUCCESS
		elif data.status_code == 409:
			print "MESSAGE: PW class already exists"
			print data.text
			return 0 # EXIT_FAILED
		else:
			print "ERROR: something went wrong with the ncs..."
			return 0 # EXIT_FAILED
 	elif(action == "delete"):
		#api = api + "/static:static/%s\%2C\%22%s/32\%22\%2C%s" % (staticPrefix, tunnelRef)
		resource = resource + "/pw:pw/" + source + "%2C" + class_id + "%2C" + tunnel_ref + "%2C" + dst_ip + "%2C" + pw_id
		#print api
		data = ncsApiCall(ncs, resource, method) 
		#print data.status_code
		if data.status_code == 204:
			return 1 # EXIT_SUCCESS
		elif data.status_code == 404:
			print "MESSAGE: PW class/xconnect cannot be found"
			return 0 # EXIT_FAILED
		else:
			print "ERROR: something went wrong with the ncs..."
			return 0 # EXIT_FAILED

def deleteTunByName(wae, source, tunnel_name):
	payload = {
		"srcNode":source,
		"tunnelName":tunnel_name,
		"removeEros":"false"
	}
	method = "post"
	data_type = "json"
	resource = "/wae/network/modeled/entities/tunnel/delete/byName"
	data = waeApiCall(wae, resource, method, data_type, payload)
	responsePrint(data, "deleteTunByName")
	return data["jobId"]["id"]

def getTunnel(wae, source, tunnel_name):
	payload = {
		"srcNode":source,
		"name":tunnel_name
	}
	method = "post"
	data_type = "json"
	resource = "/wae/network/modeled/entities/tunnel/from-model/get-tunnel"
	data = waeApiCall(wae, resource, method, data_type, payload)
	#responsePrint(data, "getTunnel")
	return data["lsp"]

def getAllTunnel(wae):
	method = "get"
	data_type = "json"
	resource = "/wae/network/modeled/entities/tunnel/from-model/get-all-tunnels"
	data = waeApiCall(wae, resource, method, data_type)
	print "MESSAGE: here are the existing tunnels:"
	num = 1
	for tunnel in data["lsps"]:
		print "\tTunnel name is %s, sourcing from %s" % (tunnel["name"], tunnel["source"]["name"])
		print "\t\tTunnel is",
		if(tunnel.get("active")==True):
			print "active"
		else:
			print "inactive"
		if(tunnel.has_key("lspPaths")):
			print "\t\tThere are %d paths" % len(tunnel["lspPaths"])
			for path in tunnel["lspPaths"]:				
				if(path.has_key("lspPathHops")):
					print "\t\t" + path["pathName"] + " takes the intermediate hops",
					for hop in path["lspPathHops"]:
						print hop["nodeKey"]["name"],
					print ""
		num += 1

def tunnelQuery(wae, source, tunnel_name, bandwidth, query_request):
	lspclass = "Default"
	payload = {
		"lspIdentifier":{ 
			"source":{"name":source}, 
			"name":tunnel_name},
			"lspModifiableFields":{ 
				"setupBW":bandwidth,
				"includeAffinityGroup":query_request.incAffinGrp, 
				"includeAnyAffinityGroup":query_request.incAnyAffinGrp, 
				"excludeAffinityGroup":query_request.excAffinGrp, 
				"frrEnabled":query_request.frrEnabled, 
				"holdPri":query_request.holdPri, 
				"setupPri":query_request.setupPri,
				"lspClass" : lspclass
			},
			"optimizationParameters" : {}
	}
	method = "post"
	resource = "/wae/optimization/path-optimization/modify-optimized/tunnel/query"
	data_type = "jason"
	data = waeApiCall(wae, resource, method, data_type, payload)
	#responsePrint(data, "tunnelQuery")
	extracted_data = data["deployPlan"]["step"][0]["to"]["lsp"]

	print "MESSAGE: Query was done, here are the details:"
	print "\tThe tunnel is from node %s(%s) to node %s(%s)" % (extractedData["lspKey"]["uniDirConnection"]["sourceNode"]["name"],
																extractedData["lspKey"]["uniDirConnection"]["sourceNode"]["ipAddress"],
																extractedData["lspKey"]["uniDirConnection"]["destNode"]["name"],
																extractedData["lspKey"]["uniDirConnection"]["destNode"]["ipAddress"])
	print "\tTunnel name is %s" % extractedData["lspKey"]["name"]
	print "\tThe suggested path includes intermediate hops",
	for hop in extractedData["primary"]["namedPath"]["path"]["hop"]:
		print (hop["iface"]["node"]["name"] + "(" + hop["iface"]["node"]["ipAddress"] + ")"),
	print ""	

	return (extracted_data)

def tunnelAdmit(wae, source, tunnel_name, bandwidth, admit_request):
	lspclass = "Default"
	payload = {
		"lspIdentifier":{ 
			"source":{"name":source}, 
			"name":tunnel_name},
			"lspModifiableFields":{ 
				"setupBW":bandwidth,
				"includeAffinityGroup":"", 
				"includeAnyAffinityGroup":"", 
				"excludeAffinityGroup":"", 
				"frrEnabled":"false", 
				"holdPri":admit_request.holdPri, 
				"setupPri":admit_request.setupPri,
				"lspClass" : lspclass,
				"lspPathsModifiable":[{
					"lspPathName":admit_request.lspPathName,
					"setupBw":bandwidth
				}]
			},
			"optimizationParameters" : {}
	}

	#pprint.pprint(payload)
	method = "put"
	resource = "/wae/optimization/path-optimization/modify-optimized/tunnel/admit"
	data_type = "json"
	data = waeApiCall(wae, resource, method, data_type, payload)
	#responsePrint(data, "tunnelAdmit")

	extractedData = data["deployPlan"]["step"][0]["to"]["lsp"]

	print "MESSAGE: Admit ready to be executed, here are the details:"
	print "\tThe tunnel is from node %s(%s) to node %s(%s)" % (extractedData["lspKey"]["uniDirConnection"]["sourceNode"]["name"],
																extractedData["lspKey"]["uniDirConnection"]["sourceNode"]["ipAddress"],
																extractedData["lspKey"]["uniDirConnection"]["destNode"]["name"],
																extractedData["lspKey"]["uniDirConnection"]["destNode"]["ipAddress"])
	print "\tTunnel name is %s" % extractedData["lspKey"]["name"]
	print "\tThe path includes intermediate hops",
	for hop in extractedData["primary"]["namedPath"]["path"]["hop"]:
		print (hop["iface"]["node"]["name"] + "(" + hop["iface"]["node"]["ipAddress"] + ")"),
	print ""

	return data["deployJobId"]["id"]

def doWaeBWMod(wae, src="", bw="", stage_id=""):
  	  
  # Step 1 - create a WAE Plan object instance in order to get the contents of a Mate Plan
  waePlan = PlanFile(wae)                     # Create a new Stage Plan file object	  

  # Step 2 - try to create a Mate Plan object instance from the Mate Design APIs
  try:
    matePlanManager = mod_MATE_libs.classMatePlanManager()   # Creates a Mate Plan file object
  except:
    print "[ERROR] - fnDoWaeIntMod - Could not open MATE_libs Mate Plan Manager"
    return 0 # EXIT_FAILED

  # Step 3 - Get the contents of the plan file from the WAE Server
  waePlan.setStageID(stage_id)

  if waePlan.getWaePlan(stage_id):
    print "[INFO] - fnDoWaeIntMod - Plan file contents passed download from the WAE server"
  else:
    print "[ERROR] - fnDoWaeIntMod - Plan file contents failed download from the WAE server"
    return 0 # EXIT_FAILED

  # Step 4 - Store WAE Plan File contents in the Mate Plan Manager object
  if matePlanManager.fnGetMatePlanFromBytes(waePlan.svPlanContents, True):
    objApiMatePlan = objMatePlanManager.objApiMatePlan
  else:
    print "[ERROR] - fnDoWaeIntMod - Could not store Plan File in Mate Plan Manager API"
    return 0 # EXIT_FAILED

  # Step 5 - Process the modifications on the Plan file. (this part should be modified to sth else)
  if objMatePlanManager.fnSetMatePropertyInt(svProp,svVal,[svSrc],[svIntName],bvDebug):
    if (bvDebug):
      print "[INFO] - fnDoWaeIntMod - Plan file Interface property modifications passed"
  else:
    print "[ERROR] - fnDoWaeIntMod - Plan file Interface property modifications failed"
    return 0 # EXIT_FAILED

  # Step 6 - Put the contents of the plan file back into the WAE Server (no need to push back the plan file)
  '''if objWaePlan.fnPutWaePlan(svStageId,bvDebug):
    print "[INFO] - fnDoWaeIntMod - Plan file contents passed upload to the WAE server"
  else:
    print "[ERROR] - fnDoWaeIntMod - Plan file contents failed upload to the WAE server"
    return 0 # EXIT_FAILED'''

  return 1 # EXIT_SUCCESS
