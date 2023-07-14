#2023 BELL FLIGHT AVR COMPETITION IN PARTNERSHIP WITH REC FOUNDATION
#FILE: main.py
#TARGET: Le Potato 
#GAME CONTROLER BY PI 

#--------------------
# Comandline Commands
#--------------------
#ls /dev/tty* <- looking for port (ttyACM0 or tttyUSB0). Disconect USB to finf the port that does missing
#python3 -m pip install pyserial
#sudo adduser pi dialout 
#groups 
#sudo apt install python3-pip
#!/user/bin/env python3 <- info that we are using python3

#--------------------
# IMPORTS
#--------------------
import serial
import time
import phao.mqtt.client as mqtt

#--------------------
# PINS
#--------------------
hitLight = 5          #channel1
firelight1 = 6        #channel2
firelight2 = 13       #channel3 
channel4 = 16         #unused
channel5 = 19         #unused
channel6 = 20         #unused
channel7 = 21         #unused 
hotPlate = 26         #channel8

#--------------------
# LIGHT STATUSUS
#--------------------
fullstrip = "0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255"
halfstrip = "0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255"

def send_to_ardunio(text):
    time.sleep(1) #1 times per second send data. it reads more often then wrte. time.sleep(0.01) #100 times per second listen
    ser_connection.write(text+"\n".encode('utf-8')) #write data. \n to end the readuntil() and encode


def read_from_arduino():
    #check if a read is in. if somthing is there it will wait until and do somthing else
    while ser_connection.in_waiting <= 0:
        time.sleep(0.01)
    datain = ser_connection.readLine().decode('utf-8').rstrip()
    return datain

#--------------------
# Serial Setup
#--------------------
def setup():
    print("Serial Setup...\n")
    #line will fail if connection not made 
    ser_connection = serial.Serial('dev/ttyACM0', 115200, timeout = 1.0) #change port if needed. / change baud rate of needed / timeout
    time.sleep(4) #gives arduino time to setup and start sending. 
    ser_connection.reset_input_buffer() #reset buffer for a clean read. 
    print("Serial Setup ... Done. Ardunio Conected!\n")
    return ser_connection

#--------------------
# Main Loop
#--------------------
def main():
    ser_connection = setup()

    while True:
        event = read_from_arduino()
        if event == "ball":
            # send MQTT for ball event
            pass
        elif event == "laser":
            # send MQTT for laser event
            pass


if __name__ == "__main__":
    main()