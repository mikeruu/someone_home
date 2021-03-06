
#!/usr/bin/env python
"""
#this should ssh into the aP and try to match the userlist to the mac addresses
# in the ap mca-dump json response

This should work as presence detection to disable zoneminder

"""
import paramiko
import json
import logging
import subprocess
from time import sleep
from threading import Thread
import configparser
import requests

import userdb
from userdb import usersdata

config = configparser.ConfigParser()
config.read('config.ini')


ap_host = config['DEFAULT']['ap_host']
#get a list of hosts of the access poits
ap_host = ap_host.split(',')
port = config['DEFAULT']['port']
username = config['DEFAULT']['username']
username = str(username)
password = config['DEFAULT']['password']
userlist = config['DEFAULT']['userlist'] 
state_command = config['DEFAULT']['state_command']
POLL_INTERVAL = config['DEFAULT']['POLL_INTERVAL']

logging.basicConfig(
    filename="/var/log/someone_home/someone-home.log",
    level=logging.ERROR,
    format="%(asctime)s:%(levelname)s:%(message)s"
    )
    
logging.getLogger(__name__)

logger = logging.getLogger('LOG')



last_known = []




def getMacid(userlist):
    macids = []

    for user in userlist:
        macids.append(user['macid'])
    
    return macids



def userNotify(userlist,message,relay='prowl'):

    for user in userlist:
        userinfo = find_user('macid',user)
    
        if  not userinfo:
            logging.debug('Could not find user to notify')
        
        else:
            if relay == 'prowl':
                payload = {'apikey': userinfo['prowl_apikey'] ,'application':'Ecksy', 'event':'Status','description': message,'priority':'-1' }
                resp = requests.get('http://www.prowlapp.com/publicapi/add', params=payload)
                logging.debug('Sending notification to: %s', userinfo['username'] )
    



def find_user(key,value):
    for user in usersdata:
        if user[key] == value:
            return user
    
    return False


#get json dump from ubiquiti AP
def getDump(hostname,port,username,password):
    s = paramiko.SSHClient()
    s.load_system_host_keys()
    output = {}
    json_dump = {}
     
    try:
        hostname
        s.connect(hostname, port, username, password)
        stdin, stdout, stderr = s.exec_command('mca-dump')
        output = stdout.read()
        s.close()
        output = output.replace(" ","") 
        logging.debug('getDump.output = %s',output)
    except:
        output = None
        logging.error('Failed on getting host list from AP in getDump function')
    
    json_dump = json.loads(output)
    
    logging.debug('json from AP:     %s',json_dump)
    return json_dump


def cam_state(state):
    subprocess.call([state_command + ' '+ state], shell=True)
    logging.info("Changed State to: %s",state)


#Returns someone_home = True|False if it matches a user from userlist to the found mac ids.
def scan_clients(json_dump,macids):
    users_home = []
	# there are mutliple channels in the wifi, must scan all if them for mac address
    ch_list = json_dump['vap_table']
    
    #The AP will return a list of channels

    
    if not ch_list:
        users_home = None
    
    else:
		for ch in ch_list:
			cl_list = ch['sta_table']
			#The sta table contains the list of clients connected to the channel
			for cl in cl_list:
				logging.info('Wifi Clients found: %s', cl['mac'])
				if cl['mac'] in macids:
					#Only add to the list if it doesnt exist.
					if cl['mac'] not in users_home:
						users_home.append(cl['mac'])
							   
					logging.info('Matched this user: %s', cl['mac'])
					
    # logging.debug('users_home: %s',users_home)
					
    return users_home



	
def change_state(users_home):
    global last_known
    logging.info('users_home: %s',users_home)
    # if we have matched ids in the list it means someone is home
    if not users_home:
        someone_home = False
 
    else:
        last_known = users_home
        someone_home = True

        
    logging.info('Someone home: %s', someone_home )
    logging.debug('last known user at home: %s' , last_known )
    
#Check current state in file
    with open("state.txt") as f:
        current_state = f.read()
        logging.info('current state: %s', current_state)

    if someone_home == True and current_state == 'All-Detect':
        logging.info('Someone is home, DISABLING Cams')
        cam_state('All-Monitor')
        message = 'DISABLED CAMS'
        userNotify(users_home,message)
        with open('state.txt', 'w') as the_file:
             the_file.write('All-Monitor')

        return True
    elif someone_home == False and current_state == 'All-Monitor':
        logging.info('Nobody is home, ENABLING Cams')
        cam_state('All-Detect')
        message = 'ENABLED CAMS'
        userNotify(last_known,message)
        with open('state.txt', 'w') as the_file:
            the_file.write('All-Detect')
            
        return True
    return False
		


while True:
	
	users_home = ''
	logger.info('starting a new check')
	userlist = []
	macids = getMacid(usersdata)
	
	for ap in ap_host:
	    json_dump = getDump(str(ap),int(port),str(username),str(password))
	    logger.debug('json_dump = %s', json_dump)
	
	    if json_dump != None:
	        users_home = scan_clients(json_dump,macids)

            userlist = userlist + users_home	    
            logging.info('users found userlist %s',userlist)
	
	change_state(userlist)
	# Wait POLL_INTERVAL seconds between scans
	sleep(int(POLL_INTERVAL))

# except KeyboardInterrupt:
#     # On a keyboard interrupt signal threads to exit
#     stop = True
#     exit()
