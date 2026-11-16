# Remote Access

Use this SSH tunnel from the office computer to reach both the Flask web server and SSH on the device network through `daffy.fel.duke.edu`:

```powershell
ssh -N -L 8080:192.168.16.117:80 -L 2222:192.168.16.117:22 test@daffy.fel.duke.edu
```

Then open:

```text
http://localhost:8080
```

Notes:

- Leave the SSH terminal open while using the web page.
- The Flask app in this project is configured to listen on remote port `80`.
- `test` is the Duke/gateway account and owns the deployed files.
- Use the `agent` device account and its dedicated key for automated updates.
- The `motor_control.service.d/port80.conf` systemd drop-in grants only the network capability needed for the service to bind port `80`.
- If local port `8080` is already in use, choose another local port such as `5000`:

```powershell
ssh -N -L 5000:192.168.16.117:80 test@daffy.fel.duke.edu
```

Then open `http://localhost:5000`.

To open an SSH shell through the tunnel as the maintenance account:

```powershell
ssh -i "C:\Users\elm79\.ssh\flash_agent_ed25519" -p 2222 agent@localhost
```

To connect directly through the gateway without first opening local port `2222`:

```powershell
ssh -i "C:\Users\elm79\.ssh\flash_agent_ed25519" -J test@daffy.fel.duke.edu agent@192.168.16.117
```
