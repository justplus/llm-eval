from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, Response, current_app, session as flask_session
from flask_login import login_required, current_user
from app import db
from app.models import AIModel, ChatSession, ChatMessage
from app.services import chat_service, model_service
import json # For SSE data formatting
from datetime import datetime

bp = Blueprint('chat', __name__, url_prefix='/chat')

@bp.route('/new', methods=['GET', 'POST']) # Or specify model_id in POST to start with a model
@login_required
def new_chat_session():
    """开始一个新的聊天会话，可以选择一个模型立即开始，或者先创建会话再选择模型。"""
    if request.method == 'POST':
        # If a model_id is posted, create session and redirect to it with the model
        model_id = request.form.get('model_id')
        session = chat_service.create_chat_session(current_user.id)
        if session:
            if model_id:
                return redirect(url_for('chat.view_chat_session', session_id=session.id, model_id=model_id))
            return redirect(url_for('chat.view_chat_session', session_id=session.id))
        else:
            flash('无法创建新的聊天会话。', 'error')
            return redirect(url_for('main.dashboard')) # Or back to model list
    
    # GET request: Simply create a new session and redirect to it for model selection
    session = chat_service.create_chat_session(current_user.id)
    if session:
        # flash('新对话已创建。', 'success') # Optional: too chatty?
        return redirect(url_for('chat.view_chat_session', session_id=session.id))
    else:
        flash('无法创建新的聊天会话。', 'error')
        return redirect(url_for('main.dashboard'))

@bp.route('/session/<int:session_id>', methods=['GET'])
@login_required
def view_chat_session(session_id):
    session = chat_service.get_chat_session_by_id(session_id, current_user.id)
    if not session:
        flash('聊天会话未找到或您无权访问。', 'error')
        return redirect(url_for('chat.chat_history_list'))

    messages = chat_service.get_messages_for_session(session_id)
    available_models = model_service.get_all_models_for_user(current_user) # For model selection dropdown
    
    # 获取会话的存储配置 (如果有)
    db.session.refresh(session)  # 强制从数据库重新加载session对象
    saved_configs = chat_service.get_session_model_configs(session_id) or []
    
    # Determine current model for this session if any message has model_id or if passed in URL
    current_model_id_from_url = request.args.get('model_id', type=int)
    current_model_id = current_model_id_from_url
    current_model = None

    if not current_model_id and messages:
        # Try to get model_id from the last assistant message or any message with model_id
        for msg in reversed(messages):
            if msg.model_id:
                current_model_id = msg.model_id
                break
    
    if current_model_id:
        current_model = AIModel.query.get(current_model_id)
        if not current_model or (not current_model.is_system_model and current_model.user_id != current_user.id):
            flash('选定的模型无效或您无权使用。', 'warning')
            current_model = None # Unset if invalid
            current_model_id = None
            
    return render_template('chat/chat_interface.html', 
                           session=session, 
                           messages=messages, 
                           available_models=available_models,
                           current_model=current_model,
                           saved_configs=saved_configs,
                           title=f"对话: {session.session_name}")

@bp.route('/session/<int:session_id>/send', methods=['POST'])
@login_required
def send_message(session_id):
    session = chat_service.get_chat_session_by_id(session_id, current_user.id)
    if not session:
        # For non-streaming error, a simple JSON response is fine
        return jsonify({"error": "会话未找到。"}), 404

    data = request.json
    user_message_content = data.get('message')
    model_configs = data.get('models', [])  # 获取模型配置数组，包含多个模型的信息
    
    if not model_configs or len(model_configs) == 0:
        return jsonify({"error": "必须至少选择一个模型。"}), 400

    if not user_message_content: 
        return jsonify({"error": "消息内容不能为空。"}), 400
    
    # 验证所有模型的访问权限
    for model_config in model_configs:
        model_id = model_config.get('id')
        if not model_id:
            return jsonify({"error": "每个模型配置必须包含id。"}), 400
            
        target_model = AIModel.query.get(model_id)
        # 记录详细日志，帮助诊断问题
        current_app.logger.info(f"验证模型访问权限: 用户ID={current_user.id}, 模型ID={model_id}, "
                               f"模型存在={target_model is not None}, "
                               f"系统模型={target_model.is_system_model if target_model else None}, "
                               f"模型所有者ID={target_model.user_id if target_model else None}")
        
        if not target_model:
            return jsonify({"error": f"所选模型 (ID: {model_id}) 不存在。"}), 404
        
        # 修改逻辑：系统模型所有用户都可以访问，自定义模型只有创建者可以访问
        has_access = target_model.is_system_model or target_model.user_id == current_user.id
        
        if not has_access:
            return jsonify({"error": f"您无权访问模型 (ID: {model_id})。"}), 403

    # 1. 保存用户消息
    user_chat_message = chat_service.add_message_to_session(session_id, model_id=None, role='user', content=user_message_content)
    if not user_chat_message:
        return jsonify({"error": "保存用户消息失败。"}), 500

    # 2. 准备对话历史
    db_messages_history = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.timestamp.desc()).limit(20).all()
    api_call_history = []
    for msg in reversed(db_messages_history):
        if msg.role in ['user', 'assistant']:
            api_call_history.append({"role": msg.role, "content": msg.content})

    # 获取应用实例，用于后续的上下文管理
    _app = current_app._get_current_object()

    # 3. 使用SSE流式返回多个模型的响应
    def generate_sse_stream():
        # 为每个模型创建一个响应生成器
        model_generators = {}
        
        # 在应用上下文中初始化所有模型生成器
        with _app.app_context():
            for model_config in model_configs:
                model_id = model_config.get('id')
                model_name = model_config.get('name', f"模型 {model_id}")
                # 创建每个模型的流式响应生成器
                model_generator = chat_service.call_openai_compatible_api(
                    model_id, 
                    api_call_history,
                    system_prompt=model_config.get('system_prompt'),
                    temperature=model_config.get('temperature'),
                    stream=True
                )
                model_generators[model_id] = {
                    'generator': model_generator,
                    'name': model_name,
                    'accumulated_content': [],
                    'error': None,
                    'settings_snapshot': None,
                    'is_done': False,
                    'last_processed': 0  # 添加时间戳，跟踪上次处理时间
                }

        # 跟踪已完成的模型数量
        completed_models = 0
        total_models = len(model_generators)
        current_time = datetime.now().timestamp()

        # 更新所有模型的初始处理时间
        for model_data in model_generators.values():
            model_data['last_processed'] = current_time

        # 轮询所有模型的生成器，直到所有模型都完成
        while completed_models < total_models:
            current_time = datetime.now().timestamp()
            processed_any = False
            
            # 按上次处理时间排序，优先处理等待时间最长的模型
            sorted_models = sorted(
                model_generators.items(), 
                key=lambda x: x[1]['last_processed']
            )
            
            for model_id, model_data in sorted_models:
                if model_data['is_done']:
                    continue  # 跳过已完成的模型

                try:
                    # 尝试获取下一个响应块，设置较短的超时时间避免一个模型阻塞其他模型
                    chunk_data = next(model_data['generator'])
                    processed_any = True
                    model_data['last_processed'] = current_time
                    
                    # 添加模型标识到响应中
                    chunk_data['model_id'] = model_id
                    chunk_data['model_name'] = model_data['name']
                    
                    if chunk_data.get("error"):
                        model_data['error'] = chunk_data
                        model_data['settings_snapshot'] = chunk_data.get("settings_snapshot")
                        model_data['is_done'] = True
                        completed_models += 1
                        
                        # 发送错误事件
                        sse_event = {
                            "model_id": model_id,
                            "model_name": model_data['name'],
                            "error": chunk_data.get("error"),
                            "details": chunk_data.get("details"),
                            "settings_snapshot": chunk_data.get("settings_snapshot")
                        }
                        yield f"data: {json.dumps(sse_event)}\n\n"
                    
                    elif chunk_data.get("is_final_chunk"):
                        model_data['settings_snapshot'] = chunk_data.get("settings_snapshot")
                        model_data['is_done'] = True
                        completed_models += 1
                        
                        final_full_content = chunk_data.get("full_content", "".join(model_data['accumulated_content']))
                        
                        # 发送最终块事件
                        sse_event = {
                            "model_id": model_id,
                            "model_name": model_data['name'],
                            "content_piece": "",
                            "is_final_chunk": True,
                            "full_content": final_full_content,
                            "settings_snapshot": model_data['settings_snapshot']
                        }
                        yield f"data: {json.dumps(sse_event)}\n\n"
                    
                    else:
                        content_piece = chunk_data.get("content_piece", "")
                        if content_piece:
                            model_data['accumulated_content'].append(content_piece)
                        
                        model_data['settings_snapshot'] = chunk_data.get("settings_snapshot")
                        
                        # 发送内容片段事件
                        sse_event = {
                            "model_id": model_id,
                            "model_name": model_data['name'],
                            "content_piece": content_piece,
                            "is_final_chunk": False,
                            "settings_snapshot": model_data['settings_snapshot']
                        }
                        yield f"data: {json.dumps(sse_event)}\n\n"
                
                except StopIteration:
                    # 生成器已经耗尽，但没有接收到最终块标记
                    if not model_data['is_done']:
                        model_data['is_done'] = True
                        completed_models += 1
                        processed_any = True
                        
                        # 发送隐式最终块事件
                        sse_event = {
                            "model_id": model_id,
                            "model_name": model_data['name'],
                            "is_final_chunk": True,
                            "full_content": "".join(model_data['accumulated_content']),
                            "settings_snapshot": model_data['settings_snapshot']
                        }
                        yield f"data: {json.dumps(sse_event)}\n\n"
                
                except Exception as e:
                    # 处理异常
                    _app.logger.error(f"处理模型 {model_id} 响应时发生错误: {e}")
                    if not model_data['is_done']:
                        model_data['is_done'] = True
                        completed_models += 1
                        processed_any = True
                        
                        # 发送错误事件
                        sse_event = {
                            "model_id": model_id,
                            "model_name": model_data['name'],
                            "error": "处理错误",
                            "details": str(e)
                        }
                        yield f"data: {json.dumps(sse_event)}\n\n"
            
            # 如果这次循环没有处理任何模型数据，添加短暂延迟避免CPU空转
            if not processed_any:
                from time import sleep
                sleep(0.01)  # 10毫秒延迟
            
        # 循环结束后，发送所有模型完成的信号（已在循环外）
        yield f"data: {json.dumps({'all_models_completed': True})}\n\n"
        
        # 所有模型已完成，保存所有模型的响应到数据库（只保存一次）
        with _app.app_context():
            for model_id, model_data in model_generators.items():
                if model_data['error']:
                    # 保存错误信息
                    error_details = f"模型API错误: {model_data['error'].get('details', model_data['error'].get('error'))}"
                    chat_service.add_message_to_session(
                        session_id, 
                        model_id=model_id, 
                        role='system', 
                        content=error_details,
                        settings_snapshot=model_data['settings_snapshot']
                    )
                    _app.logger.info(f"已记录模型 {model_id} 的系统错误: {error_details}")
                else:
                    # 保存正常响应
                    full_assistant_response = "".join(model_data['accumulated_content'])
                    if full_assistant_response:
                        chat_service.add_message_to_session(
                            session_id, 
                            model_id=model_id, 
                            role='assistant', 
                            content=full_assistant_response,
                            settings_snapshot=model_data['settings_snapshot']
                        )
                        _app.logger.info(f"已记录模型 {model_id} 的助手消息。长度: {len(full_assistant_response)}")

    return Response(generate_sse_stream(), mimetype='text/event-stream')

@bp.route('/history')
@login_required
def chat_history_list():
    sessions = chat_service.get_user_chat_sessions(current_user.id)
    return render_template('chat/chat_history.html', sessions=sessions, title="对话历史")

@bp.route('/session/<int:session_id>/delete', methods=['POST'])
@login_required
def delete_session_route(session_id):
    session = chat_service.get_chat_session_by_id(session_id, current_user.id)
    if not session:
        flash('无法找到要删除的会话。', 'error')
        return redirect(url_for('chat.chat_history_list'))
    
    if chat_service.delete_chat_session(session):
        flash(f'会话 "{session.session_name}" 已成功删除。', 'success')
    else:
        flash(f'删除会话 "{session.session_name}" 失败。', 'error')
    return redirect(url_for('chat.chat_history_list'))

@bp.route('/session/<int:session_id>/save_configs', methods=['POST'])
@login_required
def save_session_model_configs(session_id):
    """保存会话的模型配置"""
    session = chat_service.get_chat_session_by_id(session_id, current_user.id)
    if not session:
        return jsonify({"error": "会话未找到。"}), 404

    data = request.json
    model_configs = data.get('model_configs', [])
    
    if not model_configs:
        return jsonify({"error": "未提供有效的模型配置。"}), 400
    
    # 验证所有模型的访问权限
    for config in model_configs:
        model_id = config.get('id')
        if model_id:
            target_model = AIModel.query.get(model_id)
            if not target_model or (not target_model.is_system_model and target_model.user_id != current_user.id):
                return jsonify({"error": f"您无权访问模型 (ID: {model_id})。"}), 403
    
    # 保存配置
    success = chat_service.save_session_model_configs(session_id, model_configs)
    if success:
        return jsonify({"message": "模型配置已保存"}), 200
    else:
        return jsonify({"error": "保存模型配置失败"}), 500 