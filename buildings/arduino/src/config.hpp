/*
2023 BELL FLIGHT AVR COMPETITION IN PARTNERSHIP WITH REC FOUNDATION
FILE: config.hpp
TARGET: Arduino Mega 2560

This header file will contains configurations relevent to the physical IO of the
Arduino Mega 
*/

#ifndef config_h
#define config_h
#include <pins_arduino.h>

//-------------
// PINS - SENSORS 
//-------------
#define ledStripDin ((uint8_t)23)
#define BallDetectTrigger ((uint8_t)2)
#define RGBsensorSCL ((uint32_t)53)
#define RGBsensorSDA ((uint32_t)52)
#define ringLightIn ((uint8_t) 33)

//-------------
// PINS - LIGHTS
//-------------
#define ANIMATION_REFRESH 100
#define HEATER_PIN A4
#define BALL_DROP_PIN 2
#define LED_PIN_STRIP0 23 //changed
#define LED_PIN_STRIP1 A0
#define LED_PIN_STRIP2 39
#define LED_PIN_STRIP3 41
#define LENGTH_STRIPS 30
#define LED_PIN_MOS0 A1
#define LED_PIN_MOS1 A2
#define LED_PIN_MOS2 A3

//-------------
// PINS - Building Peramiters 
//-------------
#define UNDEFINED_BLDG ((uint8_t)32)
#define LASER ((uint8_t)0)
#define TRENCH ((uint8_t)1)
#define BALL ((uint8_t)2)
#define YES ((uint8_t)1)
#define NO ((uint8_t)0)
#define NUM_BUILDINGS 14
#define NUM_SENSORS_TYPES 3

//-------------
// PINS - Serial Connection
//-------------
#endif
