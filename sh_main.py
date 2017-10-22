
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

config = configparser.ConfigParser()
config.read('config.ini')




ap_host = config['DEFAULT']['ap_host']
port = config['DEFAULT']['port']
username = config['DEFAULT']['username']
password = config['DEFAULT']['password']
userlist = config['DEFAULT']['userlist'] 
state_command = config['DEFAULT']['state_command']
POLL_INTERVAL = config['DEFAULT']['POLL_INTERVAL']
 

logging.basicConfig(
    filename="someone-home.log",
    level=logging.DEBUG,
    format="%(asctime)s:%(levelname)s:%(message)s"
    )
logging.getLogger("paramiko").setLevel(logging.ERROR)

def getDump(hostname,port,username,password):
    s = paramiko.SSHClient()
    s.load_system_host_keys()
    s.connect(hostname, port, username, password)
    stdin, stdout, stderr = s.exec_command('mca-dump')
    
    output = stdout.read()
    s.close()
    return output


def cam_state(state):
    subprocess.call([state_command + ' '+ state], shell=True)
    logging.info("Changed State to: %s",state)


#Returns someone_home = True|False if it matches a user from userlist to the found mac ids.
def scan_clients(json_dump):
    found_user = []
	# there are mutliple channels in the wifi, must scan all if them for mac address
    ch_list = json_dump['vap_table']
    
    #always start a can with no one home.
    someone_home = False
    #The AP will return a list of channels
    for ch in ch_list:
        cl_list = ch['sta_table']
        #The sta table contains the list of clients connected to the channel
        for cl in cl_list:
            logging.debug('Found these mac ids: %s', cl['mac'])
            if cl['mac'] in userlist:
            #If one of the macids are matched in the list = someone is home
                someone_home = True
					
    return someone_home
	
def change_state(someone_home):
    print someone_home
#Check current state in file
    with open("state.txt") as f:
        current_state = f.read()
        logging.info('current state: %s', current_state)

    if someone_home == True and current_state == 'All-Detect':
        logging.info('Someone is home, DISABLING Cams')
        cam_state('All-Monitor')
        with open('state.txt', 'w') as the_file:
             the_file.write('All-Monitor')

        return True
    elif someone_home == False and current_state == 'All-Monitor':
        logging.info('Nobody is home, ENABLING Cams')
        cam_state('All-Detect')
        with open('state.txt', 'w') as the_file:
            the_file.write('All-Detect')
            
        return True
    return False
		

try:


    while True:
        
        mca_dump = getDump(str(ap_host),int(port),str(username),str(password))
        json_dump = json.loads(mca_dump)
        someone_home = scan_clients(json_dump)
        change_state(someone_home)
        # Wait 30 seconds between scans
        sleep(int(POLL_INTERVAL))

except KeyboardInterrupt:
    # On a keyboard interrupt signal threads to exit
    stop = True
    exit()
