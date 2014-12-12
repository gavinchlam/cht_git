#!/usr/bin/python2.6

import argparse
import sys
import json
import requests
from ordereddict import OrderedDict
from requests.auth import HTTPBasicAuth
from requests import Request, Session
import pprint
import time
import datetime
import shelve
#import com.cisco.mateapi
import gettun
import os
import getpass
import subprocess
from tabulate import tabulate
import l2vpn_lib

###########################################################################################################
''''Class Definitions'''

class QueryRequest:
	def __init__(self, getTunnelReply):
		self.incAffinGrp = getTunnelReply["includeAffinityGroup"]
		self.incAnyAffinGrp = getTunnelReply["includeAnyAffinityGroup"]
		self.excAffinGrp = getTunnelReply["excludeAffinityGroup"]
		self.frrEnabled = getTunnelReply["frrEnabled"]
		self.holdPri = getTunnelReply["holdPri"]
		self.setupPri = getTunnelReply["setupPri"]

	def action(self, wae, source, tunnel_name, bandwidth):		
		return tunnelQuery(wae, src, tname, bw, self)

class AdmitRequest:
	def __init__(self, rawQueryReply):		
		getQueryReply = rawQueryReply
		self.holdPri = getQueryReply["lspAttribs"]["holdPriority"]
		self.setupPri = getQueryReply["lspAttribs"]["setupPriority"]
		self.lspPathName = getQueryReply["primary"]["namedPath"]["name"]

	def action(self, wae, source, tunnel_name, bandwidth):
		return tunnelAdmit(wae, src, tname, bw, self)

###########################################################################################################
''' Argument parser for the entire program '''

parser = argparse.ArgumentParser(prog='PCEP', description='#A small demo on creating PCEP tunnels and traffic steering#')
parser.add_argument('--add', '-a', nargs=7, metavar=('<customer name>', '<source node>', '<source interface>',
												'<destination node>', '<destination interface>',
												'<bw constraint>', '<realtime>'),
									  dest='add_info')
parser.add_argument('--delete', '-d', nargs=1, metavar=('<requestID>'))
parser.add_argument('--showdb', action='store_true')
#parser.add_argument('--testdel', action='store_true')
#parser.add_argument('--status', '-s', action='store_true')
parser.add_argument('--list', '-l', action='store_true')

# What to do with the arguments
args = parser.parse_args()

#host = args.host
host = "10.75.158.171"
wae = "http://"+host+":7777"
ncs = "http://10.75.158.173:8080"

###########################################################################################################
''' Program main body '''

customers = {"ford_PE1":"192.168.1.6", "ford_PE2":"192.168.1.7",
             "GM_PE1":"192.168.2.6", "GM_PE2":"192.168.2.7"}

# If '--add' flag is used
if(args.add_info):
	
	cname = args.add_info[0]
	src = args.add_info[1]
	src_int = args.add_info[2]
	dest = args.add_info[3]
	dest_int = args.add_info[4]
	bw = args.add_info[5]
	realtime = 	args.add_info[6]
	request_id = "1"

	try:
		db = shelve.open('db.dat', 'c')
		if(len(db)>0):
			requestID = str(int(db.keys()[0]) + 1)
	finally:
		db.close()

	tname = "tunnel_%s_%s" % (cname, requestID)
	pwid = "pw_%s_%s" % (cname, requestID)

	response_src = l2vpn_lib.createBasic(wae, tname, src, dest)
	response_dst = l2vpn_lib.createBasic(wae, tname, dest, src)
	timeLeft = 10
	if(l2vpn_lib.isDone(wae, response_src["jobId"]["id"], timeLeft) && 
		l2vpn_lib.isDone(wae, response_dst["jobId"]["id"], timeLeft)):
		writeLog(cname, requestID, "CREATE", "tunnel %s from %s to %s is created" % (tname, src, dest))
		
		db = shelve.open('db.dat', 'w')
		db[requestID] = {"tunnel_name":tname,"tunnel_ID":"","customer_name":cname, 
							"source":src,"destination":dest, "mapping":"", "pw_ID":"",
							"pw_bandwith":"", "te_bandwidth":"", "path":"",
							"bi_direction":bi_dir,"state":"TCREATE"}
		db.close()


		'''qrequest = QueryRequest(getTunnel(wae, src, tname))
		qresponse = qrequest.action(wae, src, tname, bw)
		
		path_list = []
		for hop in qresponse["primary"]["namedPath"]["path"]["hop"]:
			path_list.append(hop["iface"]["node"]["name"])

		l2vpn_lib.writeLog(cname, requestID, "QUERY", "tunnel %s from %s to %s is queried, suggested path: " % (tname, src, dest)+path_list)
		dbUpdate(0, requestID, "state", "QUERY")
		dbUpdate(0, requestID, "path", path_list)	

		ans = ""
		while(ans != "y" and ans!="n" and ans!="yes" and ans!="no"):
			ans = raw_input("Want to admit? (Y/N) ")
			ans = ans.lower()

		ans = ans[0]
		if(ans == 'y'):
			arequest = l2vpn_lib.AdmitRequest(qresponse)
			aresponse = arequest.action(wae, src, tname, bw)	
			timeLeft = 20
			if(isDone(wae, aresponse, timeLeft)):
				l2vpn_lib.writeLog(cname, requestID, "ADMIT", "tunnel %s from %s to %s is admitted, path: " % (tname, src, dest) + path_list)
				dbUpdate(0, requestID, "state", "ADMIT")
				print "MESSAGE: Success! 'tunnel admit' executed"
				print "MESSAGE: Going to do a manual snapshot to update the plan file and get the tunnel reference"
				#time.sleep(3)
				subprocess.call('./snap1.sh')
			else:
				l2vpn_lib.writeLog(cname, requestID, "ADMIT", "tunnel admit failed")
				print "ERROR: Something went wrong when doing 'tunnel admit'..."

			# Te tunnel get and steering here #	
			tID = "tunnel-te" + gettun.getTunnelID(src, tname)
			l2vpn_lib.dbUpdate(0, requestID, "tunnel_ID", tID)
			if(tID == ""):
				print "ERROR: cannot get the required information for traffic steering, rolling back and deleting tunnel..."
				l2vpn_lib.rollBack(wae, src, tname, requestID)
			else:
				print "MESSAGE: preparing for traffic steering by creating static route..."
				prefix = customers.get(cname + "_" + dest)
				if(trafficSteer(ncs, "add", src, prefix+"/32", tID)):
					l2vpn_lib.writeLog(cname, requestID, "TRAFFIC STEER", "traffic steering done, static route created for prefix %s with outgoing interface %s (%s in the server)" % (prefix, tID, tname))
					print "MESSAGE: traffic steering done, static route created for prefix %s with outgoing interface %s (%s in the server)" % (prefix, tID, tname)
				else:
					l2vpn_lib.writeLog(cname, requestID, "TRAFFIC STEER", "traffic steering failed")
					print "ERROR: static route creation failed, rolling back..."
					l2vpn_lib.rollBack(wae, src, tname, requestID)

		elif(ans == 'n'):
			print "MESSAGE: deleting tunnel now..."
			l2vpn_lib.rollBack(wae, src, tname, requestID)
			l2vpn_lib.writeLog(cname, requestID, "DELETE", "tunnel is deleted")'''
	else:
		dbUpdate(1, requestID)
		print "ERROR: something went wrong when creating tunnel..."
		l2vpn_lib.writeLog(cname, requestID, "CREATE", "tunnel creation failed")



	#arequest = AdmitRequest(qresponse)
	#aresponse = arequest.action(wae, src, tname, bw)


# If '--delete' flag is used 
elif(args.delete):
	#src = args.delete[0]
	#tname = args.delete[1]

	requestID = args.delete[0]
	src = ""
	dest = ""
	tname = ""
	tID = ""

	try:
		db = shelve.open('db.dat', 'r')
		src = db[requestID]["source"]
		dest = db[requestID]["destination"]
		tname = db[requestID]["tunnel_name"]
		tID = db[requestID]["tunnel_ID"]
		cname = db[requestID]["customer_name"]
	finally:
		db.close()
	#print tname.split("_")[1]
	prefix = customers.get(tname.split("_")[1] + "_" + dest)
	#print prefix
	#print src
	#print dest
	#print tID
	#tID = "tunnel-te" + getTunnelID(src, tname, True)	
	#tID = tID.strip("tunnel-te")
	#print tID
	l2vpn_lib.trafficSteer(ncs, "delete", src, prefix+"/32", tID)

	response = l2vpn_lib.deleteTunByName(wae, src, tname)
	timeLeft = 5
	if(l2vpn_lib.isItDone(wae, response, timeLeft)):
		l2vpn_lib.writeLog(cname, requestID, "DELETE", "tunnel is deleted")
		l2vpn_lib.dbUpdate(1, requestID)
		print "MESSAGE: tunnel deleted"
	else:
		l2vpn_lib.writeLog(cname, requestID, "DELETE", "tunnel deletion failed")
		print "ERROR: something went wrong when doing tunnel deletion..."

# If '--test' flag is used 
elif(args.showdb):
	try:
		db = shelve.open('db.dat', 'r')
		table = []
		header = ["ID", "Customer", "Source", "Dest", "Path", "State", "Tunnel ID", "Tunnel Name", "BW Const", "Bi-dir"]
		for item in db:
			i = []
			path = db[item]["path"]
			i.extend((item, db[item]["customer_name"], db[item]["source"], db[item]["destination"], path, db[item]["state"], db[item]["tunnel_ID"], db[item]["tunnel_name"], db[item]["bandwidth_constraint"], db[item]["bi_direction"]))
			table.append(i)
		print tabulate(table, headers=header, tablefmt="orgtbl")
		db.close()
	except:
		print "ERROR: problems opening the persistent storage file, either file does not exist or there are problems with the file"

# If "--list" flag is used
elif(args.list):
	#writeLog("ford", "1", "CREATE", "ok google")	
	l2vpn_lib.getAllTunnel(wae)
else:
	pass

###########################################################################################################	