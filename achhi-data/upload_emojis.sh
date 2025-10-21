#!/bin/bash

DISCORD_TOKEN="your_token_here"
APPLICATION_ID="your_application_id_here"
API_URL="https://discord.com/api/v10"
OUTPUT_FILE="emoji_ids.json"
BASE_URL="https://raw.githubusercontent.com/AllRoundJonU/AchievementHunterInitiativeBot/main/images/thumbnails"

# Clear or create JSON output
echo "{" > "$OUTPUT_FILE"
first_digit=true

# Loop through 0 to 9 for digits
for digit in {0..9}; do
  dir="emoji-processing/$digit"
  original="$dir/${digit}.png"
  resized="$dir/${digit}_resized.png"
  split_prefix="$dir/${digit}_part"

  mkdir -p "$dir"

  # For this script, we assume you have digit images (0.png - 9.png)
  # You can modify this to download from your source
  echo "🌐 Processing digit $digit..."
  
  # If you need to download, uncomment and modify:
  # curl -s -L -o "$original" "$BASE_URL/$digit.png"

  if [ ! -f "$original" ]; then
    echo "⚠️  Image for digit $digit not found at $original - skipping"
    continue
  fi

  echo "🖼 Resizing $original to 256x256..."
  magick convert "$original" -resize 256x256! "$resized"

  echo "🔪 Splitting into 4 quadrants..."
  magick "$resized" -crop 2x2@ +repage +adjoin "${split_prefix}_%d.png"

  # Start digit entry in JSON
  if [ "$first_digit" = true ]; then
    first_digit=false
  else
    echo "," >> "$OUTPUT_FILE"
  fi
  echo "  \"$digit\": {" >> "$OUTPUT_FILE"

  # Upload each part (TL, TR, BL, BR)
  part_names=("TL" "TR" "BL" "BR")
  first_part=true
  
  for part_idx in {0..3}; do
    split_img="${split_prefix}_${part_idx}.png"
    part_name="${part_names[$part_idx]}"
    emoji_name="${digit}_${part_name}"

    echo "⬆️  Uploading $emoji_name..."

    if [[ "$OSTYPE" == "darwin"* ]]; then
      b64image=$(base64 -i "$split_img")
    else
      b64image=$(base64 -w 0 "$split_img")
    fi

    json_payload=$(jq -n \
      --arg name "$emoji_name" \
      --arg image "data:image/png;base64,$b64image" \
      '{name: $name, image: $image}')

    response=$(curl -s -X POST "$API_URL/applications/$APPLICATION_ID/emojis" \
      -H "Authorization: Bot $DISCORD_TOKEN" \
      -H "Content-Type: application/json" \
      -d "$json_payload")

    emoji_id=$(echo "$response" | jq -r '.id // empty')

    if [ -n "$emoji_id" ]; then
      echo "✅ Uploaded $emoji_name with ID $emoji_id"
      if [ "$first_part" = true ]; then
        first_part=false
      else
        echo "," >> "$OUTPUT_FILE"
      fi
      echo "    \"$part_name\": \"$emoji_id\"" >> "$OUTPUT_FILE"
    else
      echo "❌ Failed to upload $emoji_name"
      echo "Response: $response"
    fi
  done
  
  echo "  }" >> "$OUTPUT_FILE"
done

echo "" >> "$OUTPUT_FILE"
echo "}" >> "$OUTPUT_FILE"

echo "🎉 Finished uploading all emojis. Mapping saved to $OUTPUT_FILE"
