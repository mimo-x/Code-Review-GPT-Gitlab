from flask import Blueprint, request, jsonify

web_api = Blueprint('web_api', __name__)


# 检查配置
@web_api.route('/check_config', methods=['GET'])
def check_config():
    return jsonify({'code': 200, 'msg': 'success'})



