import os
import json
import logging
from flask import Flask, request
from anthropic import Anthropic

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize Anthropic client
client = Anthropic()

# Store conversation history per user
conversations = {}

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

SYSTEM_PROMPT = """You are an impeccable personal AI assistant with perfect memory. You handle all administrative and creative tasks your user delegates, including:

- Managing and drafting email replies (via Gmail)
- Posting and scheduling content across social media platforms
- Creating written content including books, articles, and scripts
- Drafting legal documents and providing general legal information (not formal legal advice)
- Assisting with music platform management and copyright/registration guidance
- Generating image and video prompts and content outlines
- Managing calendars and scheduling
- Writing songs and music
- Building websites and web content
- Scrubbing the web for true information and research
- Planning trips and itineraries

Always act on behalf of the user with their voice and preferences in mind. Be proactive, efficient, and thorough. Ask for clarification only when an action is irreversible or ambiguous. Remember everything the user tells you across conversations."""


def send_telegram_message(chat_id, text):
    """Send a message back to Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        import requests
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logger.info(f"Message sent to {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send message: {e}")


def get_conversation_history(user_id):
    """Get or create conversation history for a user."""
    if user_id not in conversations:
        conversations[user_id] = []
    return conversations[user_id]


def chat_with_claude(user_id, user_message):
    """Send message to Claude and get response."""
    history = get_conversation_history(user_id)
    
    # Add user message to history
    history.append({
        "role": "user",
        "content": user_message
    })
    
    try:
        # Call Claude API with conversation history
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=history
        )
        
        # Extract response text
        assistant_message = response.content[0].text
        
        # Add assistant response to history
        history.append({
            "role": "assistant",
            "content": assistant_message
        })
        
        return assistant_message
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        return f"Error communicating with Claude: {str(e)}"


@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle incoming Telegram webhook updates."""
    try:
        update = request.get_json()
        logger.info(f"Received update: {json.dumps(update)}")
        
        # Check if this is a message update
        if "message" not in update:
            return "ok", 200
        
        message = update["message"]
        chat_id = message["chat"]["id"]
        user_id = message["from"]["id"]
        
        # Handle text messages
        if "text" in message:
            user_text = message["text"]
            logger.info(f"User {user_id} sent: {user_text}")
            
            # Get response from Claude
            response = chat_with_claude(user_id, user_text)
            
            # Send response back to Telegram
            send_telegram_message(chat_id, response)
        
        # Handle document uploads
        elif "document" in message:
            file_id = message["document"]["file_id"]
            file_name = message.get("document", {}).get("file_name", "document")
            logger.info(f"User {user_id} uploaded document: {file_name}")
            
            # Acknowledge receipt
            send_telegram_message(chat_id, f"📄 Received: {file_name}\n\nProcessing with Claude...")
            
            # For now, acknowledge the file
            # Full file download and processing would require additional setup
            response = chat_with_claude(user_id, f"User uploaded a document: {file_name}")
            send_telegram_message(chat_id, response)
        
        return "ok", 200
    
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "error", 500


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return "ok", 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)

