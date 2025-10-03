int sensorPin1 = A3;    // Blue signal = A3 (inside of arm) // select the input pin for the potentiometer
int sensorPin2 = A5;    // Red signal = A5 (outside of arm)
int sensorPin3 = A6;    // Idk (back of arm)
// int sensorPin4 = A7;    // Idk (front of arm)
int sensorValue1 = 0;  // variable to store the value coming from the sensor
int sensorValue2 = 0;
int sensorValue3 = 0;
// int sensorValue4 = 0;

void setup() {
  // declare the ledPin as an OUTPUT:
  Serial.begin(115200);
  // Serial.begin(9600);
}


void loop() {
  // read the value from the sensor:
  sensorValue1 = analogRead(sensorPin1);
  sensorValue2 = analogRead(sensorPin2);
  sensorValue3 = analogRead(sensorPin3);
  // sensorValue4 = analogRead(sensorPin4);
  
  Serial.print(sensorValue1);
  Serial.print(" ");  // Space separation (important for Serial Plotter)
  Serial.println(sensorValue2);
  Serial.print(" ")
  Serial.println(sensorValue3);
  // Serial.print(" ")
  // Serial.println(sensorValue4);
  
  //delay(10);
  delay(1);
}
