const char index_html[] PROGMEM = R"rawliteral(
<!DOCTYPE HTML><html>
<head>
  <title>STEPPER DASHBOARD</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <style>
    html {font-family: Arial; display: inline-block; text-align: center;}
    p {  font-size: 1.2rem;}
    body {  margin: 0;}
    a:visited { color: inherit; }
    .topnav { overflow: hidden; background-color: #2f4468; color: white; font-size: 1.7rem; }
    .content { padding: 20px; }
    .bottomnav { overflow: hidden; background-color: #2f4468; color: white; font-size: 1.7rem; }
  </style>
</head>
<body>
  <div class="content">
    <div>
      <h4>MAC ADDRESS <span id="macAddress">%macAddress%</span></h4>
    </div> 
    <div>%whichStepper=0%
      <h4>STEPPER %stepperLabel%</h4>
    </div>
    <div>
      <h4>STATUS: <span id="running0">%running%</span></h4>
    </div>
    <div>
      <h4>SPEED: <span id="speed0">%speed%</span></h4>
    </div>
    <div>
      <h4>POSITION: <span id="currentPosition0">%currentPosition%</span></h4>
    </div>
    <div>%whichStepper=1%
      <h4>STEPPER %stepperLabel%</h4>
    </div>
    <div>
      <h4>STATUS: <span id="running1">%running%</span></h4>
    </div>
    <div>
      <h4>SPEED: <span id="speed1">%speed%</span></h4>
    </div>
    <div>
      <h4>POSITION: <span id="currentPosition1">%currentPosition%</span></h4>
    </div>
    <div>      
      <h4>
      <form action="/" method="post">
      <input type="hidden" id="whichStepper" name="whichStepper" value="0">
      <input type="hidden" id="stop" name="stop" value="true">
      <input type="submit" value="STOP">
      </form>
      </h4>
    </div>
    <div>      
      <h4>
      <form action="/" method="post">
      <input type="hidden" id="whichStepper" name="whichStepper" value="0">
      <label for="move">MOVE RELATIVE POSITION: </label><input type="number" id="move" name="move" placeholder = %distanceToGo%>
      <input type="submit" value="move">
      </form>
      </h4>
    </div>
    <div>      
      <h4>
      <form action="/" method="post">
      <input type="hidden" id="whichStepper" name="whichStepper" value="0">
      <label for="moveTo">MOVE ABSOLUTE POSITION: </label><input type="number" id="moveTo" name="moveTo" placeholder = %targetPosition%>
      <input type="submit" value="moveTo">
      </form>
      </h4>
    </div>
    <div>      
      <h4>
      <form action="/" method="post">
      <input type="hidden" id="whichStepper" name="whichStepper" value="0">
      <label for="setAcceleration">ACCELERATION: </label><input type="number" id="acceleration" name="setAcceleration" placeholder = %acceleration%>
      <input type="submit" value="setAcceleration">
      </form>
      </h4>
    </div>
    <div>      
      <h4>
      <form action="/" method="post">
      <input type="hidden" id="whichStepper" name="whichStepper" value="0">
      <label for="setMaxSpeed">MAXIMUM SPEED: </label><input type="number" id="maxSpeed" name="setMaxSpeed" placeholder = %maxSpeed%>
      <input type="submit" value="setMaxSpeed">
      </form>
      </h4>
    </div>
    <div>      
      <h4>
      <form action="/" method="post">
      <input type="hidden" id="whichStepper" name="whichStepper" value="0">
      <label for="setCurrentPosition">SET CURRENT POSITION: </label><input type="number" id="setCurrentPosition" name="setCurrentPosition" placeholder = %currentPosition%>
      <input type="submit" value="setCurrentPosition">
      </form>
      </h4>
    </div>
    <div>      
      <h4>
      <form action="/" method="post">
      <input type="hidden" id="whichStepper" name="whichStepper" value="0">
      <input type="hidden" id="setOutputEnabled" name="setOutputEnabled" value="true">
      <input type="submit" value="ENABLE OUTPUTS">
      </form>
      <form action="/" method="post">
      <input type="hidden" id="whichStepper" name="whichStepper" value="0">
      <input type="hidden" id="setOutputEnabled" name="setOutputEnabled" value="false">
      <input type="submit" value="DISABLE OUTPUTS">
      </form>
      </h4>
    </div>
</body>
<script>
  if (!!window.EventSource) {
    var source = new EventSource("/events");
    
    source.addEventListener("open", function(e) {
      console.log("Events Connected");
    }, false);
    source.addEventListener("error", function(e) {
      if (e.target.readyState != EventSource.OPEN) {
        console.log("Events Disconnected");
      }
    }, false);
    source.addEventListener("message", function(e) {
      console.log("message", e.data);
    }, false);
  
    source.addEventListener("data", function(e) {
     console.log("data", e.data);
     let arro = e.data.split(";");
     for (let i = 0; i < arro.length; i++) {
       let arri = arro[i].split("=");
       document.getElementById(arri[0]).innerHTML = arri[1];
     }
    }, false);     }
</script>
</html>)rawliteral";
