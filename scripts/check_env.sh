#!/usr/bin/env bash
# Validate required keys exist and are non-empty in backend/.env
set -euo pipefail

ENV_FILE="backend/.env"
REQUIRED=(SUPABASE_URL SUPABASE_SECRET_KEY DATABASE_URL VAPI_API_KEY)

if [ ! -f "$ENV_FILE" ]; then
  echo ""
  echo "❌  $ENV_FILE not found."
  echo "   Copy the template and fill in your keys:"
  echo "   cp .env.template $ENV_FILE"
  echo ""
  exit 1
fi

missing=()
while IFS= read -r line || [[ -n "$line" ]]; do
  # Strip comments and blank lines
  [[ "$line" =~ ^#.*$ || -z "$line" ]] && continue
  # Export key=value pairs
  export "${line?}" 2>/dev/null || true
done < "$ENV_FILE"

for key in "${REQUIRED[@]}"; do
  val="${!key:-}"
  # Treat placeholder values as missing
  if [[ -z "$val" || "$val" == *"YOUR"* || "$val" == *"your-"* || "$val" == *"PROJECT_REF"* ]]; then
    missing+=("$key")
  fi
done

if [ ${#missing[@]} -gt 0 ]; then
  echo ""
  echo "❌  Missing or unset keys in $ENV_FILE:"
  for k in "${missing[@]}"; do
    echo "   $k"
  done
  echo ""
  exit 1
fi

echo "✓  Environment looks good"
