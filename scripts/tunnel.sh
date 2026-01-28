#!/bin/bash

# Configuration
NETLIFY_TOKEN="${NETLIFY_TOKEN:-}"  # Set as environment variable
DOMAIN="kvasilopoulos.com"
SUBDOMAIN="demo"
LOCAL_PORT="${LOCAL_PORT:-8000}"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting Cloudflare tunnel...${NC}"

# Start cloudflared and capture output
cloudflared tunnel --url http://localhost:$LOCAL_PORT 2>&1 | while read -r line; do
    echo "$line"
    
    # Look for the tunnel URL in the output
    if [[ $line =~ https://[a-z0-9-]+\.trycloudflare\.com ]]; then
        TUNNEL_URL="${BASH_REMATCH[0]}"
        TUNNEL_HOST=$(echo "$TUNNEL_URL" | sed 's|https://||')
        
        echo -e "${GREEN}Tunnel URL detected: $TUNNEL_URL${NC}"
        
        # Update Netlify DNS if token is provided
        if [ -n "$NETLIFY_TOKEN" ]; then
            echo -e "${BLUE}Updating Netlify DNS for ${SUBDOMAIN}.${DOMAIN}...${NC}"
            
            # Get DNS zone ID
            ZONE_ID=$(curl -s -H "Authorization: Bearer $NETLIFY_TOKEN" \
                "https://api.netlify.com/api/v1/dns_zones?account_slug=$(curl -s -H "Authorization: Bearer $NETLIFY_TOKEN" https://api.netlify.com/api/v1/accounts | jq -r '.[0].slug')" | \
                jq -r ".[] | select(.name==\"${DOMAIN}\") | .id")
            
            if [ -z "$ZONE_ID" ]; then
                echo -e "${RED}Error: Could not find DNS zone for $DOMAIN${NC}"
            else
                # Check if record exists
                EXISTING_RECORD=$(curl -s -H "Authorization: Bearer $NETLIFY_TOKEN" \
                    "https://api.netlify.com/api/v1/dns_zones/$ZONE_ID/dns_records" | \
                    jq -r ".[] | select(.hostname==\"${SUBDOMAIN}.${DOMAIN}\") | .id")
                
                if [ -n "$EXISTING_RECORD" ]; then
                    # Update existing record
                    curl -s -X DELETE -H "Authorization: Bearer $NETLIFY_TOKEN" \
                        "https://api.netlify.com/api/v1/dns_zones/$ZONE_ID/dns_records/$EXISTING_RECORD" > /dev/null
                fi
                
                # Create new CNAME record
                RESPONSE=$(curl -s -X POST -H "Authorization: Bearer $NETLIFY_TOKEN" \
                    -H "Content-Type: application/json" \
                    -d "{\"type\":\"CNAME\",\"hostname\":\"${SUBDOMAIN}\",\"value\":\"${TUNNEL_HOST}\",\"ttl\":60}" \
                    "https://api.netlify.com/api/v1/dns_zones/$ZONE_ID/dns_records")
                
                if echo "$RESPONSE" | jq -e '.id' > /dev/null 2>&1; then
                    echo -e "${GREEN}✓ DNS updated successfully!${NC}"
                    echo -e "${GREEN}Your API is now available at: https://${SUBDOMAIN}.${DOMAIN}${NC}"
                else
                    echo -e "${RED}Error updating DNS: $RESPONSE${NC}"
                fi
            fi
        else
            echo -e "${BLUE}Tip: Set NETLIFY_TOKEN environment variable to auto-update DNS${NC}"
            echo -e "${BLUE}Access your API at: $TUNNEL_URL${NC}"
        fi
    fi
done 