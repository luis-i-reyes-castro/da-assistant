# 📱 WhatsApp Cloud API Setup

## 1. Setup Credentials File

In our `.env` file:
```bash
# WhatsApp Cloud API
WA_BA_NUM=1300095675231214 # WhatsApp Business Account ID (WABA ID)
WA_TOKEN=EAAB...           # WhatsApp Access Token
```

Load the env vars:
```bash
source .env
```

## 2. Get Phone Number ID from WABA ID

Each WhatsApp Business Account (WABA) can have one or more phone numbers.
To fetch them:
```bash
curl -i -X GET \
  "https://graph.facebook.com/v23.0/$WA_BA_NUM/phone_numbers" \
  -H "Authorization: Bearer $WA_TOKEN"
```

Example response:
```json
{
  "data": [
    {
      "verified_name": "Reyes Castro Drones",
      "display_phone_number": "+593 98 304 2146",
      "id": "770358066161429"
    }
  ]
}
```

Take note of the `"id"` field because this is your **Phone Number ID**.
Add it to your `.env` file:
```bash
WA_NUMBER_ID_PROD=770358066161429
WA_NUMBER_PIN_PROD=123456 # Example of 6-digit PIN you chose for registration
```

Reload:
```bash
source .env
```

## 3. Registration Flow

After adding the phone number in **WhatsApp Manager**, it shows as **Pending**.
Complete registration via API:
```bash
curl -i -X POST \
  "https://graph.facebook.com/v23.0/$WA_NUMBER_ID_PROD/register" \
  -H "Authorization: Bearer $WA_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"messaging_product\": \"whatsapp\",
    \"pin\": \"$WA_NUMBER_PIN_PROD\"
  }"
```

* ⚠️ Use **double quotes** for the JSON (the part after `-d`)
  * Necessary so that Bash expands `$WA_NUMBER_PIN_PROD`
  * Bash **cannot expand** variables inside single quotes!
* On success: `{"success":true}`
* Number status flips to **Connected**.

### De-registration

If we later need to get rid of that phone number:
```bash
curl -i -X POST \
  "https://graph.facebook.com/v23.0/$WA_NUMBER_ID_PROD/deregister" \
  -H "Authorization: Bearer $WA_TOKEN"
```

* On success: `{"success":true}`
* Number status flips to **Offline**.

## 4. Messaging Rules

* **First message to a user:** Must be a **template** (e.g. `hello_world`).
* **After user replies (24-hour window):** You can send **free-form text**.

### Example: template

```bash
curl -i -X POST \
  "https://graph.facebook.com/v23.0/$WA_NUMBER_ID_PROD/messages" \
  -H "Authorization: Bearer $WA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "messaging_product": "whatsapp",
    "to": "593995341161",
    "type": "template",
    "template": {
      "name": "hello_world",
      "language": { "code": "en_US" }
    }
  }'
```

### Example: free-form text

```bash
curl -i -X POST \
  "https://graph.facebook.com/v23.0/$WA_NUMBER_ID_PROD/messages" \
  -H "Authorization: Bearer $WA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "messaging_product": "whatsapp",
    "to": "593995341161",
    "type": "text",
    "text": { "body": "Hello World!" }
  }'
```

## 5. Limits & Quotas

* Registration API: **10 attempts per 72 hours**.
* Messaging tier: default is **250 customers / 24 hours**.

## 6. ⚡ Quick Troubleshooting Guide

**If dashboard won’t let you enable PIN:**
* Dumb, but totally normal.
* PIN is set during registration (see above).

**If registration fails:**
* Check quotes after `-d`. Use double quotes.
  * In `curl`, single quotes prevent variable expansion!
  * Use double quotes for vars like `$WA_NUMBER_PIN_PROD`.
* Confirm PIN is 6 digits.
* Ensure you didn’t exceed **10 register attempts / 72h**.

**If message not delivered (API returned 200):**
* Ensure recipient phone number's in E.164 format (no `+` prefix).
* Did the user message your number first? (if not, use a template).
* Are you within the 24-hour session window?

**If escalation is needed:**
* Support category → *Dev: Phone Number & Registration*.
* Request Type → *Registration Issues*.
* Provide your last failing `curl` call + raw API response.
