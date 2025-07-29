from flask import Blueprint, request, jsonify, current_app, render_template
from flask_login import login_required, current_user
import json
import requests
from app.models import Dataset
from app.services.dataset_service import DatasetService

# 创建API蓝图
bp = Blueprint('api', __name__, url_prefix='/api')

@bp.route('/example')
def api_example():
    """
    API示例页面 - 展示如何使用API接口
    """
    return render_template('datasets/api_example.html', title='API接口示例')

@bp.route('/retrieve', methods=['GET', 'POST'])
def retrieve():
    query = request.args.get('query', '')
    return jsonify({
        'success': True,
        'query': query,
        'results': ["人工智能（Artificial Intelligence，AI）是计算机科学的一个分支，它企图了解智能的实质，并生产出一种新的能以人类智能相似的方式做出反应的智能机器。"]
    })
    
@bp.route('/generate', methods=['GET'])
def generate():
    return jsonify({
        'success': True,
        'response': '人工智能是计算机科学的一个分支，旨在创造能够模拟人类智能的机器。'
    })