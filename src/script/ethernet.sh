
sudo ifconfig docker0 down
sudo ifconfig eno1 down
sudo ifconfig eno1 169.254.1.1 netmask 255.255.0.0 up
sudo route add -host 169.254.1.1 dev eno1

