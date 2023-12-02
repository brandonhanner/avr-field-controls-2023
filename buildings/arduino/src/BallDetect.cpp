#include "BallDetect.hpp"

BallDetect::BallDetect()
{
}

void BallDetect::ball_init(int pin) {
  this->pin = pin;
  pinMode(pin, INPUT_PULLUP);
  digitalWrite(pin, HIGH); // turn on the pullup
}

int BallDetect::get_pin() {
  return this->pin ;
}

void BallDetect::ball_trigger_interrupt() {
    //Serial.println(F("Ball Triggered true"));
    if (millis()-lasttrigger > MAX_WAIT) 
    {
      //Serial.println(F("XXXXXXXXXXXXXXXX BALL DROP X"));
      //Serial.println("ball.cpp");
      hastriggered = true;
      sensorState = 1;
      lasttrigger = millis();
    } 
    else  
    {
      //Serial.println(F("------ FALSE READING BALL DROP X"));
    }
}


bool BallDetect::ball_detect() 
{
  if (hastriggered == true) 
  {
      hastriggered = false;
      //Serial.println(F("Check ball detect true"));
      return true;
  }
  else
  {
    return false;
  }

}

