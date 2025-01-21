import os
from flask import Flask, jsonify, make_response
from app.gitlab_webhook import git
from utils.args_check import check_config
from utils.logger import log

app = Flask(__name__)
app.config['debug'] = True

# router group
app.register_blueprint(git, url_prefix='/git')

@app.errorhandler(400)
@app.errorhandler(404)
def handle_error(error):
    error_msg = 'Args Error' if error.code == 400 else 'Page Not Found'
    return make_response(jsonify({'code': error.code, 'msg': error_msg}), error.code)


if __name__ == '__main__':
    os.environ['STABILITY_HOST'] = 'grpc.stability.ai:443'
    app.config['JSON_AS_ASCII'] = False
    log.info('Starting args check...')
    check_config()
    log.info('Starting the app...')
    app.run(debug=True, host="0.0.0.0", port=80,use_reloader=False)
