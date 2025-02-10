from flask import Blueprint, request, jsonify
from gitlab_integration.webhook_listener import webhook_listener

git = Blueprint('git', __name__)

@git.route('/webhook', methods=['POST'])
def webhook():
    return webhook_listener.handle_webhook()