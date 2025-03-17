from flask import Blueprint, request, jsonify
from gitlab_integration.webhook_listener import webhook_listener

webhook_api= Blueprint('git', __name__)

@webhook_api.route('/webhook', methods=['POST'])
def webhook():
    return webhook_listener.handle_webhook()