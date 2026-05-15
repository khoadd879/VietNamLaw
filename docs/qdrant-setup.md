# Qdrant Cloud Setup

This project uses Qdrant Cloud for vector storage. No local container required.

## Getting Started

### 1. Create Qdrant Cloud Account

1. Go to [cloud.qdrant.io](https://cloud.qdrant.io)
2. Sign up / log in
3. Create a new cluster (free tier available)

### 2. Get Credentials

From your cluster dashboard, copy:
- **Cluster URL**: Something like `https://xxxxxxx.cloud.qdrant.io`
- **API Key**: Found in cluster settings

### 3. Configure Backend

Add to `backend/.env`:

```
QDRANT_URL=https://xxxxxxx.cloud.qdrant.io
QDRANT_API_KEY=your_api_key_here
```

### 4. Create Collection

The backend will create the collection automatically on first run via the Qdrant API. Collection name: `vietnam_laws`

### Verify Connection

```bash
cd backend
python -c "from qdrant_client import QdrantClient; c = QdrantClient(url='YOUR_URL', api_key='YOUR_KEY'); print(c.get_collections())"
```

Replace `YOUR_URL` and `YOUR_KEY` with your actual credentials.