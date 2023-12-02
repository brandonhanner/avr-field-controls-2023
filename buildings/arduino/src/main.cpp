/*
2023 BELL FLIGHT AVR COMPETITION IN PARTNERSHIP WITH REC FOUNDATION
FILE: main.cpp
TARGET: Arduino Mega 2560

This is the main to run in all buildings. designed to me imaged once at the bench. Task is three comunications: 
1. UPLINK - Ball dropped event 
2. UPLINK - Laser hit event 
3. DOWNLINK - Change Apearance on LED Adressable Strip
*/
//change

//---------------------
// IMPORTS
//---------------------
#include <Arduino.h>
#include "config.hpp"
#include "Adafruit_TCS34725.h"
#include "BallDetect.hpp"
#include "LaserDetect.hpp"
#include "LEDAnimations.hpp"
LEDAnimations led_animations; 
BallDetect ball_detect; 
LaserDetect laser_detect;
LEDStrip led_strip;


//---------------------
// Global Veriables
//---------------------
String data;
uint8_t newInstruction = NO;
const int MAX_LEDS = 30; // Maximum number of LEDs
const int RGB_VALUES = 3; // Number of RGB values per LED
uint32_t lastISR_time = 0;


//---------------------
// Instuction Parser
//---------------------
void parseLEDString(const String& inputString, int ledArray[MAX_LEDS][RGB_VALUES], int& numLeds) {
  String ledData;
  int ledIndex = 0;
  int rgbIndex = 0;
  
  for (size_t i = 0; i < inputString.length(); i++) 
  {
    char c = inputString.charAt(i);
    if (c == '/') 
    {
        ledIndex++;
        rgbIndex = 0;
        if (ledIndex >= MAX_LEDS) 
        {
            break;
        }
    }
    else if (c == ',') 
    {
      rgbIndex++;
      if (rgbIndex >= RGB_VALUES) 
      {
        break;
      }
    }
    else if (isdigit(c)) 
    {
      int value = c - '0';
      while (i + 1 < inputString.length() && isdigit(inputString.charAt(i + 1))) 
      {
        value = value * 10 + (inputString.charAt(i + 1) - '0');
        i++;
      }
      ledArray[ledIndex][rgbIndex] = value;
    }/////
  }
  
  numLeds = ledIndex + 1;
}

//---------------------
// Ball Detection Interupt Service Routine
//---------------------
void ballDetectISR()
{
    if((millis() - lastISR_time) > 50)
    {
      Serial.println("ball"); //send to pi via serial 
      lastISR_time = millis(); //reset fire itme. 
    }
    
}

String piInstructionsSerial()
{
    if(Serial.available() > 0) //if > 0 then somthing is in buffer
    {
        //data is a command from pi
        newInstruction = YES;
        data = Serial.readStringUntil('\n'); //read string untll a new line
    }
    else 
    {
      newInstruction = NO;
    }
    return data;
}

//---------------------
// LED Controller
//---------------------
void LEDdisplay(String& inputString)
{
    // MESSAGE PARSING 
    //String inputString = "255,0,0/0,255,0/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/0,0,255/";
    //String inputString = "255,0,0/0,255,0/0,0,255/255,0,0/0,255,0/0,0,255/255,0,0/0,255,0/0,0,255/255,0,0/0,255,0/0,0,255/255,0,0/0,255,0/0,0,255/255,0,0/0,255,0/0,0,255/255,0,0/0,255,0/0,0,255/255,0,0/0,255,0/0,0,255/255,0,0/0,255,0/0,0,255/255,0,0/0,255,0/0,0,255/";
    int ledArray[MAX_LEDS][RGB_VALUES];
    int numLeds = 0;

    parseLEDString(inputString, ledArray, numLeds); //Instruction Parser

    // Print the parsed LED data
    led_animations.strips[0].blackout_strip();
    for (int i = 0; i < numLeds; i++) 
    {  
        CRGB color(ledArray[i][1], ledArray[i][0], ledArray[i][2]); //RED GREEN BLUE order of data stream
        led_animations.strips[0].set_pixel_color(i, color);
    }
    led_animations.draw();    
}

//---------------------
// Setup Loop
//---------------------
void setup()
{
    //Serial Setup 
    //Serial.println(F("Serial Comunication Setup..."));
    Serial.begin(9600); //baudrate, opens serial for USB port and RX/TX. 
    Serial.setTimeout(100); //was 10 //lower it is the higher the risk of not complete reciving or sending. 
    while(!Serial){} //this is for portability. not needed on Arduino Mega. waits for serial to be configured

    //LED Animations Setup
    //Serial.println(F("LED Strip Animations Setup...")); //what pin for Din? 
    led_animations.setup(); 
    led_animations.boot_sequence(1);

    //Ball Detector Setup
    //Serial.println(F("Ball Detector Setup..."));
    ball_detect.ball_init(BallDetectTrigger);
    pinMode(BallDetectTrigger, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(BallDetectTrigger), ballDetectISR, FALLING);
    led_animations.boot_sequence(2);

    //Laser Detector Setup 
    //Serial.println(F("Laser Detector Setup..."));
    laser_detect.laser_init();
    led_animations.boot_sequence(5);

    Serial.println(F("Setup Complete")); //setup complete 
}

//---------------------
// Main Loop
//---------------------
void loop()
{
    //Look for instructions. 
    String instruction = piInstructionsSerial(); //take instuctions from pi 
    if(newInstruction == YES)
    {
        LEDdisplay(instruction);
    }

    //Check for ball drop
    // if(ball_detect.ball_detect()) //look for ball drop
    // {
    //     Serial.println("ball");
    //     ball_detect.ball_trigger_interrupt();
    // }

    //Check for laser detection
    int8_t trigger = laser_detect.laser_detect();
    if (trigger == 1)
    {
        Serial.println("laser");
        trigger = 0;
    }
}
