# Run Streamlit App on Server

## Quick Start

### Option 1: Using Docker (Recommended)

**SSH to server:**
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
```

**On the server:**
```bash
cd /opt/aris-rag

# Make sure .env file exists with your API keys
nano .env  # Add OPENAI_API_KEY=your_key_here

# Build and start with Docker
docker-compose -f docker-compose.prod.direct.yml up -d

# Check status
docker ps

# View logs
docker logs -f aris-rag-app
```

**Access at:** `http://35.175.133.235:8501`

---

### Option 2: Direct Python/Streamlit

**SSH to server:**
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
```

**On the server:**
```bash
cd /opt/aris-rag

# Install dependencies (if not already installed)
pip3 install streamlit python-dotenv
pip3 install -r config/requirements.txt

# Create .env file with your API keys
nano .env  # Add OPENAI_API_KEY=your_key_here

# Run Streamlit
streamlit run app.py --server.port=8501 --server.address=0.0.0.0
```

**Or run in background:**
```bash
nohup streamlit run app.py --server.port=8501 --server.address=0.0.0.0 > streamlit.log 2>&1 &
```

**View logs:**
```bash
tail -f streamlit.log
```

**Access at:** `http://35.175.133.235:8501`

---

## Using the Automated Script

If you have the PEM file:

```bash
./scripts/run_on_server.sh
```

This will:
1. Ask you to choose Docker or Direct Python
2. Copy code if needed
3. Start Streamlit on the server
4. Show you the access URL

---

## Important: Open Port 8501

**In AWS Console:**
1. EC2 → Security Groups
2. Select your instance's security group
3. Edit Inbound Rules → Add Rule
4. Type: Custom TCP, Port: 8501, Source: 0.0.0.0/0
5. Save

---

## Final URL

After running and opening the port:
```
http://35.175.133.235:8501
```






