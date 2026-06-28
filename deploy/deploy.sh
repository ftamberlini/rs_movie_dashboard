#!/bin/bash
set -e

# ── Configuração ──────────────────────────────────────────────────────────────
PROJECT_ID="rssimulator"
REGION="us-central1"
REPO="cinemap-dashboard"
SERVICE="cinemap-dashboard"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/app:latest"
WALLET_BUCKET="rs-movie-oracle-wallet"

echo "▶ Projeto       : $PROJECT_ID"
echo "▶ Região        : $REGION"
echo "▶ Imagem        : $IMAGE"
echo "▶ Wallet bucket : gs://$WALLET_BUCKET"
echo ""

# ── 1. Garante que o repositório Artifact Registry existe ────────────────────
echo "▶ Verificando Artifact Registry..."
if ! gcloud artifacts repositories describe "$REPO" \
    --project "$PROJECT_ID" --location "$REGION" &>/dev/null; then
  echo "  Criando repositório $REPO..."
  gcloud artifacts repositories create "$REPO" \
    --project "$PROJECT_ID" \
    --location "$REGION" \
    --repository-format docker
fi

# ── 2. Autentica Docker no Artifact Registry ──────────────────────────────────
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# ── 3. Build da imagem (a partir da raiz do projeto) ─────────────────────────
echo "▶ Build da imagem Docker..."
docker build -t "$IMAGE" "$(dirname "$0")/.."

# ── 4. Push para o Artifact Registry ─────────────────────────────────────────
echo "▶ Push para Artifact Registry..."
docker push "$IMAGE"

# ── 5. Deploy no Cloud Run ────────────────────────────────────────────────────
echo "▶ Deploy no Cloud Run..."
gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 1 \
  --min-instances 1 \
  --max-instances 5 \
  --concurrency 80 \
  --execution-environment gen2 \
  --cpu-boost \
  --timeout 120 \
  --add-volume "name=oracle-wallet,type=cloud-storage,bucket=${WALLET_BUCKET},readonly=true" \
  --add-volume-mount "volume=oracle-wallet,mount-path=/app/oracle" \
  --set-env-vars "ORACLE_USER=rslake_user,\
ORACLE_PASSWORD=ciNEma3978AbcD,\
ORACLE_DSN=rsdb_medium,\
ORACLE_WALLET_DIR=/app/oracle,\
ORACLE_WALLET_PASSWORD=Carteira3978AbcD"

echo ""
echo "✓ Deploy concluído!"
gcloud run services describe "$SERVICE" \
  --project "$PROJECT_ID" --region "$REGION" --format "value(status.url)"
