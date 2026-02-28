import os
from dotenv import load_dotenv
from arkon_messenger import send_telegram_message

def main():
    load_dotenv()
    msg = "🔱 Arkon Local Test: Connection Successful!"
    ok = send_telegram_message(msg)
    print("OK" if ok else "FAIL")

if __name__ == "__main__":
    main()
