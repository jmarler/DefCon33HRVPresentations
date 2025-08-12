# Meshtastic DEFCON-33 Offline Web Flasher (Raspberry Pi)

This container packages the Meshtastic DEFCON-33 Web Flasher **and** the DEFCON firmware files into a single Docker container.  
It runs completely **offline**, serving the flasher UI and firmware files from the same Nginx instance.

Tested on Raspberry Pi 4 with **64-bit Raspberry Pi OS** in the Ham Radio Village at DefCon 33.

---

## 📦 Features
- Works **completely offline**
- Bundles [Meshtastic Web Flasher (defcon-33 branch)](https://github.com/meshtastic/web-flasher/tree/defcon-33)
- Bundles DEFCON firmware from [meshtastic.github.io](https://github.com/meshtastic/meshtastic.github.io)
- Uses Nginx to serve UI and firmware in one container

---

## 🛠 Installation (Raspberry Pi 64-bit OS)

### 1. Update & Install Docker

```bash
sudo apt update && sudo apt upgrade -y
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

**Log out and back in** to apply Docker group changes.

Verify Docker works:
```bash
docker run hello-world
```

---

### 2. Clone this Repository

```bash
git clone https://github.com/jmarler/DefCon33HRVPresentations.git
cd DefCon33HRVPresentations/webflasher
```

---

### 3. Build the Docker Image

```bash
docker build -t meshtastic-defcon33-allinone .
```

This will:
- Clone the web flasher (defcon-33 branch)
- Clone meshtastic.github.io firmware files
- Patch the flasher to use **local firmware files**
- Build the web UI
- Bundle everything into an Nginx container

---

### 4. Run the Container

```bash
docker run -d --name meshtastic-flasher --restart unless-stopped -p 8080:80 meshtastic-defcon33-allinone
```

Open Chromium browser and go to:

```
http://localhost:8080
```

You should see the Meshtastic DEFCON flasher.  
Firmware files will be served locally from:

```
http://localhost:8080/event/defcon33/firmware-<version>/
```

## 🛠 Stopping & Restarting

Stop the container:
```bash
docker stop meshtastic-flasher
```

Start it again:
```bash
docker start meshtastic-flasher
```

Remove the container:
```bash
docker rm -f meshtastic-flasher
```

---

## 📂 Project Structure

```
.
├── Dockerfile        # All-in-one build & serve configuration
└── README.md         # This file
```

The Docker build process will automatically:
- Pull `web-flasher` (defcon-33 branch)
- Pull `meshtastic.github.io`
- Patch firmware URL to point to local Nginx server
- Build UI and bundle firmware

---

## ⚠️ Notes
- This container **does not require internet** once built.
- To update to a new firmware release, rebuild the image with:
  ```bash
  docker build --no-cache -t meshtastic-defcon33-allinone .
  ```
- Works with Chromium/Chrome browsers that support Web Serial API.

---

## 📜 License
This project uses:
- Meshtastic Web Flasher ([MIT License](https://github.com/meshtastic/web-flasher/blob/master/LICENSE))
- Meshtastic firmware & assets ([Apache 2.0 License](https://github.com/meshtastic/firmware/blob/master/LICENSE))
