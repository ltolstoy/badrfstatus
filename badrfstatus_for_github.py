#!/home/ltolstoy/anaconda3/bin/python
"""
Script that reads file sites.ini (blocks and IPs of CU to check),
requests rfstatus from there, and puts reports with found bad rfstatus info
into /mnt/data_log/bad_rfstatut_reports/, and sends email alerts in case it is found

"""

import subprocess as sp #subprocess32 was for 2.7
import configparser, os, sys
import time, datetime

def mail_notification(subject, text):
    """It sends email to several people with warning
    subject - like "Bad rfstatus found at Canadian_solar_305 at ip=10.8.4.22"
    text - body, like 
            "Canadian_solar_305 at ip=10.8.4.22 :
            datarate: 12001	 freq: 2410001	 tick: 200	 ch: 5	 units: 160
            bunch_size: 16	 utc: 1498885238	 ms: 971	 temp: 2000	 shift: 0
            adcs: false	 power: -1	 mac: 507280000028	 hop: true	 fec: false
            gw_addr: 0	 ed_addr: 0	 sync_word: F0F0	 watchdog: false	 mode: 0
            z_count: 4	 antennas: all"
    example from https://stackoverflow.com/questions/6270782/how-to-send-an-email-with-python
    """
    import smtplib
    from email.mime.text import MIMEText
   
    msg = MIMEText(text)
    me = "ltolstoy@xxxx.com"
    you = ["Badrfstatus@xxxx.com"] 

    msg['Subject'] = subject
    msg['From'] = me
    msg['To'] = ",".join(you)
    s = smtplib.SMTP('smtp.sendgrid.net')
    s.login('apikey', 'hardcoded_current_key') #need to read it from settings.ini file, later
    s.sendmail(me, you, msg.as_string())
    s.quit()


def main():
    """
    Reads /mnt/data_log/scripts/bad_rfstatus_reports/sites.ini,
    site, block, IP address, and requests rfstatus. If some of params there are 0,
    writes report file.
    """

    config = configparser.ConfigParser()
    p2ini = "/home/ltolstoy/scripts/bad_rfstatus_reports/sites.ini"
    p2rf = "/opt/ampt/bin/amptcomm/rfstatus"
    p2rep = "/mnt/data_log/bad_rfstatus_reports/"
    if os.path.exists(p2ini):
        config.read(p2ini)
    else:
        print("{} File sites.ini doesn't exist, can't continue, exiting now.".format( time.strftime("%Y-%m-%d %H:%M:%S")))
        sys.exit()
    #report = []
    print("{} Starting check".format( time.strftime("%Y-%m-%d %H:%M:%S") ))
    pid = str(os.getpid())
    pidfile = "/mnt/data_log/bad_rfstatus_reports/myscriptrun.pid"
    if os.path.isfile(pidfile):
        f = open(pidfile, 'r')
        pid_old = f.read()  #was file(pidfile, 'r').read()
        f.close()
        runtime = sp.check_output(['ps', '-p', pid_old, '-o', 'etimes='], stderr=sp.STDOUT)
        print("myscriptrun.pid file already exists, script didn't finish previous run yet? \
        It was running for {} sec. Killing old script with PID = {}".format(pidfile, runtime,pid_old))
        os.system('kill -9 '+pid_old)
        time.sleep(2)
        while os.path.isfile(pidfile):
            print("removing file ..")
            os.remove(pidfile)
            time.sleep(2)
        #sys.exit()
    f = open(pidfile, 'w')
    f.write(pid)
    try:
        sites = config.sections()
        for site in sites:
            blocks = config.options(site)
            for block in blocks:
                ip = config.get(site, block) #ex. '10.8.2.18'
                try:
                    process = sp.Popen(['ssh','-o', 'ConnectTimeout=20', '-o', 'ConnectionAttempts=3','root@'+ip, p2rf],
                                       stderr=sp.STDOUT, stdout=sp.PIPE)
                    pid = process.pid
                    print("{} Started ssh request for rfstatus has PID: {}".format( time.strftime("%H:%M:%S"),  str(pid))) 
                    out = process.communicate(timeout=60)[0]
                    print("{} Ended  ssh request for rfstatus with PID: {}".format( time.strftime("%H:%M:%S"), str(pid))) 
                except sp.CalledProcessError as e:
                    print("{} rfstatus request PID {} failed for {} {}: {} {}".format(time.strftime("%H:%M:%S"),
                    str(pid),site, block, e.returncode, e.output)) 
                except sp.TimeoutExpired as e1:
                    print("{} TimeoutExpired error for rfstatus request PID {} for {} {}".format( time.strftime("%H:%M:%S"),
                    str(pid), site, block)) 
                else:
                    osp = out.split() #list
                    """
                    ['datarate:', '12001', 'freq:', '2410001',  1,3
                    'tick:', '200', 'ch:', '1',                 5,7
                    'units:', '112', 'bunch_size:', '16',       9,11
                    'utc:', '1494533521', 'ms:', '376',         13,15
                    'temp:', '2000', 'shift:', '0',             17,19
                    'adcs:', 'false', 'power:', '-1',           21,23
                    'mac:', '488280000017', 'hop:', 'true',     25,27
                    'fec:', 'false', 'gw_addr:', '2',           29,31
                    'ed_addr:', '3', 'sync_word:', 'F0F0',      33,35
                    'watchdog:', 'false', 'mode:', '0',         37,39
                    'z_count:', '4', 'antennas:', 'patch']      41,43
                    """
                    try:
                        if len(osp) == 44:  #correct response length
                            if (osp[1] == "0" or osp[3] == "0" or
                                osp[7] == "0" or
                                osp[9] == "0" or osp[11] == "0" or
                                osp[31] == "0" or
                                osp[33] == "0" ):  # osp[27] != "true" hopping - is False for pgg406, so excluded
                                fn = "badrfstatus_"+time.strftime("%y%m%d")+".log"
                                # fn = site + "_" + block + "_"+ time.strftime("%y%m%d")+".log"
                                #print time.strftime("%H:%M:%S") + " ."*10 + site + "_" + block + ": FAIL"
                                print("{} {} {}_{}: FAIL".format(time.strftime("%H:%M:%S"), " ."*10, site, block))
                                with open(p2rep+fn, "a") as f:
                                    f.write(site + "_" + block + " at ip=" +ip +" :\n")
                                    f.write(out)
                                    mail_notification("Bad rfstatus found at " + site + "_" + block + " at ip=" +ip, out)
                            else:
                                print("{} {} {}_{}: \t OK".format(time.strftime("%H:%M:%S"), " ."*10, site, block))
                                #pass
                        else:
                            #print "Incorrect responce length (not 44 elements): " + len(osp), "   ", osp
                            print("{} rfstatus request failed for {}-{} : {}".format( time.strftime("%H:%M:%S"), site,block,out)) 
                    except IndexError as er:
                        print("Something wrong :{}".format(er) )
    finally:
        if os.path.isfile(pidfile):
            os.remove(pidfile)
        print("{} Finishing check, deleting file myscriptrun.pid".format( time.strftime("%Y-%m-%d %H:%M:%S") ))
        print("-" * 10)

    f.close()

if __name__ == "__main__": main()
