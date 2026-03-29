# VPS Deployment (Production, Docker Compose)

This guide deploys the full app on a Linux VPS using production containers:
- Postgres database
- FastAPI backend (ML inference)
- Nginx frontend serving built React assets

## 1) VPS prerequisites

Use Ubuntu 22.04+ and install Docker + Compose plugin:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
```

Log out and back in after adding your user to the `docker` group.

## 2) Prepare project

```bash
git clone <your-repo-url>
cd project
cp .env.vps.example .env.vps
```

Edit `.env.vps` and set real values:
- `POSTGRES_PASSWORD`
- `SECRET_KEY`
- `CORS_ORIGINS` (your public domain)
- `MODEL_WEIGHTS_FILE` (must exist in `./models`)

## 3) Start production stack

```bash
docker compose --env-file .env.vps -f docker-compose.vps.yml up -d --build
```

Check status:

```bash
docker compose --env-file .env.vps -f docker-compose.vps.yml ps
docker compose --env-file .env.vps -f docker-compose.vps.yml logs -f backend
```

## 4) Validate deployment

From the VPS:

```bash
curl http://127.0.0.1:8001/health
curl -I http://127.0.0.1/
```

Expected:
- Backend health returns `{\"status\":\"ok\"}`
- Frontend returns `HTTP/1.1 200 OK`

## 5) Firewall and DNS

Open HTTP and SSH:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw enable
```

Point your domain A record to VPS public IP.

## 6) Update and rollback

Update:

```bash
git pull
docker compose --env-file .env.vps -f docker-compose.vps.yml up -d --build
```

Rollback (to previous git commit):

```bash
git checkout <previous-commit>
docker compose --env-file .env.vps -f docker-compose.vps.yml up -d --build
```

## 7) Notes

- Current production stack serves on port 80.
- Backend port 8001 is bound to localhost only on VPS for diagnostics.
- For HTTPS, place Caddy/Nginx+Certbot in front of port 80 or use Cloudflare proxy.
