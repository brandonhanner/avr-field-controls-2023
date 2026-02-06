import random

options = ["ON", "OFF"]

on = 0
off = 0

for i in range(0,100000):
    choice = random.choice(options)
    if choice == "ON":
        on+=1
    elif choice == "OFF":
        off +=1

print(f"The distrrbution is {on} {off}")