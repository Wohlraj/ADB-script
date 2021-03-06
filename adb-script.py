#!/usr/bin/python

import subprocess, time, re, smtplib, os, platform, zipfile
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

if(platform.system()=="Windows"):
	split_string = "\r\r\n"
	logs_folder_name='\\logs\\'
else:
	split_string = "\r\n"
	logs_folder_name='/logs/'
	
def open_explorer(path):
	if(platform.system()=="Windows"):
		subprocess.Popen('explorer "{0}"'.format(path))
	else:
		subprocess.Popen(["xdg-open",path], stdout=subprocess.PIPE)

def zip_attach(files):
	zip_name=logs_path+device_name+'.zip'
	try:
		import zlib
		compression = zipfile.ZIP_DEFLATED
	except:
		compression = zipfile.ZIP_STORED
		
	print("Zipping logs...")
	zf = zipfile.ZipFile(zip_name, mode='w')
	try:
		for f in files:
			zf.write(f, compress_type=compression)
	finally:
		zf.close()
		return zip_name	

def device_name():
	proc = subprocess.Popen(["adb", "shell", "cat" ,"/system/build.prop"], stdout=subprocess.PIPE)
	(out, err) = proc.communicate()
	out = out.decode("utf-8").split(split_string)
	manufacturer, model, id = "-", "-", "-"
	for line in out:
		if "ro.product.manufacturer" in line:
			manufacturer = line.split("=")[1]
		elif "ro.product.model" in line:
			model = line.split("=")[1]
		elif "ro.build.id" in line:
			id = line.split("=")[1]
	return manufacturer+"_"+model+"_"+id+"_"+time.strftime("%d-%m-%Y_%H-%M-%S")
	
def prompt_email_and_send(files, type):
	with open('credentials.txt', 'r') as f:
		login_email = f.readline().rstrip()
		login_password = f.readline().rstrip()

	msg = MIMEMultipart()
	
	msg['From'] = login_email
	msg['To'] = input("Your email address?")
	msg['Subject'] = "ADB-script Logs - "+device_name+" - "+type
	
	attachment=zip_attach(files)

	msg.attach(MIMEText("Here are your logs."))
	part = MIMEBase('application', 'octet-stream')
	part.set_payload(open(attachment, 'rb').read())
	encoders.encode_base64(part)
	part.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(attachment))
	msg.attach(part)

	try:
		server = smtplib.SMTP('smtp.gmail.com', 587)
		server.ehlo()
		server.starttls()

		server.login(login_email, login_password)
		print("Sending mail... This might take a while.")
		server.sendmail(msg['From'], msg['To'], msg.as_string())
		server.quit()
		print("Successfully sent email.")
	except SMTPException:
		print("Error: unable to send email.")

def device_status():
	proc = subprocess.Popen(["adb", "devices", "-l"], stdout=subprocess.PIPE)
	(out, err) = proc.communicate()
	out=out.decode("utf-8")
	if out.find("device:")!=-1:
		return "detected"
	elif out.find("offline")!=-1:
		return "offline"
	elif out.find("unauthorized")!=-1:
		return "unauthorized"
	else:
		return "no_device"
		
def detect_device():
	if(device_status()=="no_device"):
		print("Please plug a device...")
		while(device_status()=="no_device"):
			time.sleep(1)
	if(device_status()=="unauthorized"):
		print("You need to authorize access on the device.")
		while(device_status()=="unauthorized"):
			time.sleep(1)
	if(device_status()=="offline"):
		print("There is an issue detecting your device.")
		while(device_status()=="offline"):
			time.sleep(1)

def nfc_logs(output):
	found = False
	for line in output:
		if re.search("4e[ ]?46[ ]?43", line, re.IGNORECASE) or re.search("01[ ]?0c[ ]?00", line, re.IGNORECASE) or re.search("4a[ ]?53[ ]?52", line, re.IGNORECASE):
			print(line)
			found = True
	return found

# Difference if script is launch from Python script or .exe
if os.getcwd()[-10:]=="ADB-script":
	logs_path = os.getcwd()+logs_folder_name
else:
	logs_path = os.path.dirname(os.getcwd())+logs_folder_name

# Creating logs folder
if not os.path.exists(logs_path): os.makedirs(logs_path)
# Creating credentials.txt
if not os.path.isfile("credentials.txt"): 
	print("Please create credentials file before continuing.")
	input("Press Enter to continue.")

# Detecting device
detect_device()

# Adding device name for log files
device_name = device_name()
print(device_name)

print("Available options:\n")
print("[1] build.prop: ro.product vars")
print("[2] main + radio logs [buffer] (with NFC API check)")
print("[3] main logs [live]")
print("[4] Orange Update config.cfg")
print("")
nb = str(input('Choose option: '))
print("")


if nb=="1":
	proc = subprocess.Popen(["adb", "shell", "cat" ,"/system/build.prop"], stdout=subprocess.PIPE)
	(out, err) = proc.communicate()
	out = out.decode("utf-8").split(split_string)
	for line in out:
		if "ro.product.model" in line or "ro.product.manufacturer" in line:
			print(line)
			
elif nb=="2":
	proc = subprocess.Popen(["adb", "logcat", "-v" ,"time", "-d"], stdout=open(logs_path+device_name+"_main.txt", 'w'))
	(out, err) = proc.communicate()
	out_main = open(logs_path+device_name+"_main.txt", 'r')
	proc = subprocess.Popen(["adb", "logcat", "-b", "radio", "-v" ,"time", "-d"], stdout=open(logs_path+device_name+"_radio.txt", 'w'))
	(out, err) = proc.communicate()
	out_radio = open(logs_path+device_name+"_radio.txt", 'r')
	
	found = nfc_logs(out_main) or nfc_logs(out_radio)
	
	if not(found):
		print("Logs are clean of NFC APDU exchanges.")
	
	email = input("Send logs by email? (y/n)")
	if email=="y":
		prompt_email_and_send([logs_path+device_name+"_main.txt", logs_path+device_name+"_radio.txt"], 'main + radio')
	
	open_explorer(logs_path)
	
elif nb=="3":
	try:
		proc = subprocess.Popen(["adb", "logcat", "-v" ,"time"], stdout=open(logs_path+device_name+"_main.txt", 'w'))
		print("Press CTRL+C to stop log capture.")
		proc.wait()
	except KeyboardInterrupt:
		proc.terminate()	
	email = input("Send logs by email? (y/n)")
	if email=="y":
		prompt_email_and_send([logs_path+device_name+"_main.txt"], 'main')
		
	open_explorer(logs_path)

elif nb=="4":
	proc = subprocess.Popen(["adb", "shell", "mkdir" ,"/sdcard/apks/"], stdout=subprocess.PIPE)
	(out, err) = proc.communicate()
	proc = subprocess.Popen(["adb", "shell", "mkdir" ,"/sdcard/apks/config"], stdout=subprocess.PIPE)
	(out, err) = proc.communicate()
	proc = subprocess.Popen(["adb", "shell", "touch" ,"/sdcard/apks/config/OU_qualif.cfg"], stdout=subprocess.PIPE)
	(out, err) = proc.communicate()
	print("File /sdcard/apks/config/OU_qualif.cfg created.")
		
else:
	print("Invalid choice.")

input("\nPress Enter to exit.")