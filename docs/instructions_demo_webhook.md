# 🚀 SOFIA WhatsApp Assistant — Operation Instructions

## 1. Refreshing the API Token

⚠️ If you’re still using a **temporary token**:

* You must refresh it daily via **Meta Developer Dashboard → Tools → Access Tokens**.

To obtain a permanent access token:

1. Go to **Meta Developer Dashboard → Business Settings → System Users**.
2. Create a **System User** (if not already created).
3. Generate a **permanent access token** tied to that user.
4. Give it the role **WhatsApp Business API → Full Access**.
5. Copy the new token and update your `~/.bashrc`:
   ```bash
   export WHATSAPP_TOKEN=(new permanent token)
   source ~/.bashrc
   ```
6. Restart Flask + ngrok.

---

## 2. Environment Setup

* Make sure your environment variables are set in `~/.bashrc` (or `~/.zshrc`):

  ```bash
  export VERIFY_TOKEN="my_secret_verify" # string with quotes
  export WA_NUMBER_ID=(your phone number ID, no quotes)
  export WA_TOKEN=(long API access token, no quotes)
  
  ```
* Reload the shell to apply changes:

  ```bash
  source ~/.bashrc
  ```
* ✅ Check validity:

  ```bash
  echo $VERIFY_TOKEN
  echo $WA_NUMBER_ID
  echo $WA_TOKEN
  ```

⚠️ If your **WhatsApp API access token** was temporary (1 day), refresh it in the Meta Developer dashboard. Use a **permanent token** when ready.

---

## 3. Start Ngrok

In a new terminal:

```bash
ngrok http 5000
```

* Copy the **HTTPS forwarding URL** from ngrok (e.g. `https://abc123.ngrok-free.app`).

---

## 4. Launch Flask Webhook

Start the Python server:

```bash
python3 demo_webhook.py
```

You should see:

```
 * Running on http://127.0.0.1:5000
```

---

## 5. Configure Meta Webhook

1. Go to **Meta Developer Dashboard → SOFIA → WhatsApp → Configuration**.
2. In **Callback URL**, paste the ngrok URL + `/webhook`, for example:

   ```
   https://abc123.ngrok-free.app/webhook
   ```
3. In **Verify Token**, enter the value you set in your environment (`my_secret_verify`), without the quotes.
4. Click **Verify and Save**.

---

## 6. Subscribe to Webhook Fields

* Under **Webhook Fields**, enable:

  * ✅ `messages`

---

## 7. Testing

* Add your personal WhatsApp number as a **test user** in the app.
* Send a text, image, or text+image to the test number.
* Flask logs will show the incoming JSON.
* Your bot will reply accordingly:

  * Text → *“You sent me a text message.”*
  * Image → *“You sent me an image.”*
  * Text + Image → *“You sent me both a text message and an image.”*
* Files are saved locally with timestamp filenames.

---

## 8. Stopping

* Stop Flask (`Ctrl+C`).
* Stop ngrok (`Ctrl+C`).

---
