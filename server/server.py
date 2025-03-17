import os
from flask import Flask, jsonify, make_response
from server.gitlab_webhook.webhook_api import webhook_api
from server.webserver.web_api import web_api
from utils.args_check import check_config
from utils.logger import log

app = Flask(__name__)
app.config['debug'] = True

# 注册两个不同的路由组
app.register_blueprint(webhook_api, url_prefix='/git')  
app.register_blueprint(web_api, url_prefix='/web')


@app.errorhandler(400)
@app.errorhandler(404)
def handle_error(error):
    error_msg = 'Args Error' if error.code == 400 else 'Page Not Found'
    return make_response(jsonify({'code': error.code, 'msg': error_msg}), error.code)

def run():
    os.environ['STABILITY_HOST'] = 'grpc.stability.ai:443'
    app.config['JSON_AS_ASCII'] = False

    log.info('Starting the app...')
    app.run(debug=True, host="0.0.0.0", port=80, use_reloader=False)
