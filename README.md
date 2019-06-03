# applied-cam-demo
Demo for camera tilt & pan using Google PubSub for angle input
Ubuntu 18.4 on Raspberry Pi 3 B+
Servo: https://www.servocity.com/hs-225mg

sudo apt-get install -y python3-pip
sudo apt-get install build-essential libssl-dev libffi-dev python-dev
#virutalenv ..
pip3 install wiringpi
pip3 install google-cloud-pubsub

# for GPIO:
Based on /proc/cpuinfo, create /root/fake-cpuinfo:
processor       : 0
BogoMIPS        : 38.40
Features        : fp asimd evtstrm crc32 cpuid
CPU implementer : 0x41
CPU architecture: 8
CPU variant     : 0x0
CPU part        : 0xd03
CPU revision    : 4

processor       : 1
BogoMIPS        : 38.40
Features        : fp asimd evtstrm crc32 cpuid
CPU implementer : 0x41
CPU architecture: 8
CPU variant     : 0x0
CPU part        : 0xd03
CPU revision    : 4

processor       : 2
BogoMIPS        : 38.40
Features        : fp asimd evtstrm crc32 cpuid
CPU implementer : 0x41
CPU architecture: 8
CPU variant     : 0x0
CPU part        : 0xd03
CPU revision    : 4

processor       : 3
BogoMIPS        : 38.40
Features        : fp asimd evtstrm crc32 cpuid
CPU implementer : 0x41
CPU architecture: 8
CPU variant     : 0x0
CPU part        : 0xd03
CPU revision    : 4

Hardware: BCM2837
Revision: a020d3

sudo mount -v --bind /root/fake-cpuinfo /proc/cpuinfo
#when done:
sudo umount -v /proc/cpuinfo

#@boot, to run:
sudo mount -v --bind /root/fake-cpuinfo /proc/cpuinfo
sudo ~/applied/applied-cam-demo/env/bin/python3 servotest.py

#systemd config:
copy demo.service to /etc/systemd/system, chmod 664
#verify:
sudo systemctl start|stop demo.service
systemctl status demo.service
sudo systemctl enable|disable demo.service