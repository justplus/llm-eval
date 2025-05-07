from flask import current_app
from app import db
from app.models import AIModel, User
from app.utils.encryption import encrypt_data, decrypt_data
from flask_login import current_user
import requests
from datetime import datetime, timezone, timedelta

# --- System Models Cache ---
_system_models_cache = {"data": None, "last_fetched_utc": None}
CACHE_DURATION_SECONDS = 3600  # 1 小时

# --- System Models Configuration ---
# SYSTEM_PROVIDER_BASE_URL is now fetched from app.config
SYSTEM_PROVIDER_API_KEY = None # Cached after first fetch from app.config

def _get_system_provider_api_key():
    global SYSTEM_PROVIDER_API_KEY
    if SYSTEM_PROVIDER_API_KEY is None:
        SYSTEM_PROVIDER_API_KEY = current_app.config.get('SYSTEM_PROVIDER_API_KEY')
        # Warning for missing API key is handled in sync_system_models if needed
    return SYSTEM_PROVIDER_API_KEY

def _get_system_provider_base_url():
    base_url = current_app.config.get('SYSTEM_PROVIDER_BASE_URL')
    if not base_url:
        current_app.logger.warning(
            "SYSTEM_PROVIDER_BASE_URL is not configured. System models may not be synced or usable."
        )
    return base_url

def _fetch_system_models_from_provider_with_cache(models_url: str, headers: dict):
    """
    从系统提供商获取模型数据，使用1小时缓存策略。
    如果获取失败，但存在（即使已过期的）缓存，则返回旧缓存。
    """
    global _system_models_cache
    app_logger = current_app.logger # 在函数开始时获取logger

    now_utc = datetime.now(timezone.utc)

    # 检查缓存是否仍然有效
    if _system_models_cache["data"] is not None and _system_models_cache["last_fetched_utc"] is not None:
        age_seconds = (now_utc - _system_models_cache["last_fetched_utc"]).total_seconds()
        if age_seconds < CACHE_DURATION_SECONDS:
            app_logger.info("Returning system models from active cache.")
            return _system_models_cache["data"]
        else:
            app_logger.info("System models cache expired, will attempt to refresh.")

    # 缓存无效或已过期，尝试获取新数据
    try:
        app_logger.info(f"Fetching system models from provider: {models_url}")
        response = requests.get(models_url, headers=headers, timeout=15)
        response.raise_for_status()
        provider_models_data = response.json()
        
        # 更新缓存
        _system_models_cache["data"] = provider_models_data
        _system_models_cache["last_fetched_utc"] = now_utc
        app_logger.info("Successfully fetched and cached new system models.")
        return provider_models_data
    except requests.exceptions.RequestException as e:
        app_logger.error(f"Failed to fetch models from system provider: {e}")
        # 如果获取失败，但存在旧缓存，则返回旧缓存以提高弹性
        if _system_models_cache["data"] is not None:
            app_logger.warning("Returning stale system models from cache due to fetch failure.")
            return _system_models_cache["data"]
        return None # 获取失败且无任何缓存
    except ValueError as e: # 包括 JSONDecodeError
        app_logger.error(f"Failed to parse JSON response from system provider: {e}")
        if _system_models_cache["data"] is not None:
            app_logger.warning("Returning stale system models from cache due to JSON parse failure.")
            return _system_models_cache["data"]
        return None # 解析失败且无任何缓存

def sync_system_models():
    """Fetches models from the system provider and syncs them to the database."""
    api_key = _get_system_provider_api_key()
    system_provider_base_url = _get_system_provider_base_url()

    if not api_key or not system_provider_base_url:
        current_app.logger.error(
            "Cannot sync system models: System Provider API Key or Base URL is not configured."
        )
        return

    models_url = f"{system_provider_base_url.rstrip('/')}/models"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    provider_models_data = _fetch_system_models_from_provider_with_cache(models_url, headers)

    if provider_models_data is None:
        current_app.logger.error("Failed to obtain system models data (from provider or cache). Sync aborted.")
        return

    fetched_model_identifiers = set()

    if isinstance(provider_models_data, dict) and 'data' in provider_models_data:
        models_list = provider_models_data['data']
    elif isinstance(provider_models_data, list):
        # Some /models endpoints return a list directly
        models_list = provider_models_data
    else:
        current_app.logger.error("Unexpected format for models data from system provider.")
        return

    for model_data in models_list:
        if not isinstance(model_data, dict) or 'id' not in model_data or 'owned_by' not in model_data:
            current_app.logger.warning(f"Skipping malformed model data from provider: {model_data}")
            continue

        model_identifier = model_data['id']
        provider_name = model_data['owned_by']
        display_name = f"{provider_name}: {model_identifier}" # Auto-generate display name
        
        fetched_model_identifiers.add(model_identifier)

        exists = AIModel.query.filter_by(
            model_identifier=model_identifier,
            api_base_url=system_provider_base_url, # Use URL from config
            is_system_model=True
        ).first()

        if not exists:
            new_model = AIModel(
                display_name=display_name,
                model_identifier=model_identifier,
                provider_name=provider_name,
                api_base_url=system_provider_base_url, # Use URL from config
                model_type="openai_compatible", # As specified by user for this provider
                system_prompt=model_data.get("system_prompt", "You are a helpful AI assistant."), # Use provider's or default
                default_temperature=model_data.get("default_temperature", 0.7),
                is_system_model=True,
                is_validated=True, # System models are now considered validated by default after sync
                user_id=None
            )
            db.session.add(new_model)
            current_app.logger.info(f"Added new system model: {display_name} as validated.")
        else: # Existing system model found, ensure it's marked as validated
            if not exists.is_validated:
                exists.is_validated = True
                db.session.add(exists)
                current_app.logger.info(f"Marked existing system model as validated: {exists.display_name}")
            # Optionally, update other details if they can change, e.g., display_name if logic changes
            if exists.provider_name != provider_name or \
               (exists.system_prompt != model_data.get("system_prompt", "You are a helpful AI assistant.")) or \
               (exists.display_name != display_name): # if display name generation logic can change
                exists.provider_name = provider_name
                exists.system_prompt = model_data.get("system_prompt", "You are a helpful AI assistant.")
                exists.display_name = display_name
                db.session.add(exists)
                current_app.logger.info(f"Updated details for existing system model: {exists.display_name}")

    current_db_system_models = AIModel.query.filter_by(is_system_model=True, api_base_url=system_provider_base_url).all()
    for db_model in current_db_system_models:
        if db_model.model_identifier not in fetched_model_identifiers:
            current_app.logger.info(f"System model {db_model.display_name} no longer provided by API. Deleting...")
            db.session.delete(db_model) # Or mark as inactive

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error committing system model changes to database: {e}")

def get_all_models_for_user(user):
    """Returns all models, with user-defined models listed first, then system models."""
    sync_system_models() # Ensure system models are up-to-date before fetching
    
    query = AIModel.query.order_by(AIModel.is_system_model.asc(), AIModel.display_name.asc())
    
    # If user is not authenticated, they should only see system models.
    # However, the current requirement is that custom models are tied to users.
    # If an unauthenticated user scenario for viewing custom models arises, this logic needs revisit.
    if user.is_authenticated:
        # Show user's custom models and all system models.
        # The query above already fetches all, but we might filter if user should not see other users' models (already handled by user_id).
        # The main sorting logic (custom first, then system) is handled by order_by is_system_model.asc().
        all_models = query.all()
        # Separate them for clarity or if specific per-type processing was needed, though order_by handles it.
        user_models = [m for m in all_models if not m.is_system_model and m.user_id == user.id]
        system_models = [m for m in all_models if m.is_system_model]
        # The query already sorts custom models before system models due to `is_system_model.asc()`
        # and then by display_name within each group.
        # So, direct result of query.all() might be sufficient if no other user-specific filtering is needed beyond ownership.
        # Let's re-verify the query logic for showing ONLY the current user's models + all system models.

        # Correct approach: Fetch user models and system models separately and combine, or use a more complex query.
        # For simplicity here and direct control:
        user_custom_models = AIModel.query.filter_by(user_id=user.id, is_system_model=False).order_by(AIModel.display_name.asc()).all()
        all_system_models = AIModel.query.filter_by(is_system_model=True).order_by(AIModel.display_name.asc()).all()
        
        return user_custom_models + all_system_models
    else:
        # Unauthenticated users only see system models
        return AIModel.query.filter_by(is_system_model=True).order_by(AIModel.display_name.asc()).all()

def get_model_by_id_for_user(model_id, user):
    """Gets a model by ID, ensuring it's either a system model or owned by the user."""
    model = AIModel.query.get(model_id)
    if model:
        if model.is_system_model or (user.is_authenticated and model.user_id == user.id):
            return model
    return None

def create_user_model(data, user):
    """Creates a new model for the given user."""
    api_key = data.pop('api_key', None)
    encrypted_api_key = encrypt_data(api_key) if api_key else None
    
    new_model = AIModel(
        user_id=user.id,
        display_name=data['display_name'],
        api_base_url=data['api_base_url'],
        model_identifier=data['model_identifier'],
        encrypted_api_key=encrypted_api_key,
        provider_name=data.get('provider_name'),
        model_type=data.get('model_type', 'openai_compatible'), # Defaulting to openai_compatible for user models too
        system_prompt=data.get('system_prompt'),
        default_temperature=data.get('default_temperature'),
        notes=data.get('notes'),
        is_system_model=False,
        is_validated=False # Validate separately
    )
    db.session.add(new_model)
    try:
        db.session.commit()
        return new_model
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating user model: {e}")
        return None

def update_user_model(model, data):
    """Updates an existing user model."""
    if model.is_system_model:
        return False 

    model.display_name = data['display_name']
    model.api_base_url = data['api_base_url']
    model.model_identifier = data['model_identifier']
    model.provider_name = data.get('provider_name')
    model.model_type = data.get('model_type', 'openai_compatible')
    model.system_prompt = data.get('system_prompt')
    model.default_temperature = data.get('default_temperature')
    model.notes = data.get('notes')

    if 'api_key' in data and data['api_key']:
        model.encrypted_api_key = encrypt_data(data['api_key'])
        model.is_validated = False
    
    db.session.add(model)
    try:
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating user model {model.id}: {e}")
        return False

def delete_user_model(model):
    """Deletes a user-owned model."""
    if model.is_system_model or not current_user.is_authenticated or model.user_id != current_user.id:
        return False
    
    db.session.delete(model)
    try:
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting user model {model.id}: {e}")
        return False

def validate_model_connectivity(model):
    """Tries to connect to the model provider to validate settings."""
    api_key_to_use = None
    base_url_to_use = model.api_base_url # This will be from config for system models

    if model.is_system_model:
        api_key_to_use = _get_system_provider_api_key()
    elif model.encrypted_api_key:
        decrypted_key = decrypt_data(model.encrypted_api_key)
        if decrypted_key == "[decryption_error]":
             return False, "API Key decryption failed. Check encryption key configuration."
        api_key_to_use = decrypted_key

    if model.model_type == 'openai_compatible':
        headers = {"Authorization": f"Bearer {api_key_to_use}"}
        validation_url = f"{base_url_to_use.rstrip('/')}/models"
        
        try:
            response = requests.get(validation_url, headers=headers, timeout=10)
            current_validation_status = False
            if response.status_code == 200:
                try:
                    models_data = response.json()
                    current_validation_status = True
                    status_message = "Model validated successfully and found at provider."
                except ValueError: 
                    current_validation_status = True # Connected, but couldn't parse/confirm specific ID.
                    status_message = "Model connected successfully, but could not confirm specific model ID from provider's list."
            else:
                status_message = f"Validation failed. Status: {response.status_code}, Response: {response.text[:200]}"
            
            # Update is_validated only for user models based on this live check.
            # System models' is_validated status is managed by sync_system_models as per requirement.
            if not model.is_system_model:
                model.is_validated = current_validation_status
                db.session.add(model)
                db.session.commit()
            return current_validation_status, status_message
        except requests.exceptions.RequestException as e:
            if not model.is_system_model:
                model.is_validated = False
                db.session.add(model)
                db.session.commit()
            return False, f"Validation request failed: {e}"
    else:
        # For non-OpenAI compatible types, only update if it's a user model
        if not model.is_system_model:
            model.is_validated = False # Or True, based on policy
            db.session.add(model)
            db.session.commit()
        return False, "Validation for this model type is not yet implemented."

def get_decrypted_api_key(model):
    if not model:
        return None
    if model.is_system_model:
        return _get_system_provider_api_key()
    if model.encrypted_api_key:
        try:
            return decrypt_data(model.encrypted_api_key)
        except Exception as e:
            current_app.logger.error(f"Failed to decrypt API key for model {model.id}: {e}")
            return "[decryption_error]"
    return None 