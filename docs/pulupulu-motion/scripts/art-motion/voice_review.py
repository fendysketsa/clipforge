"""读取安装目录外的模型检查记录；不联网、不更换默认模型。"""
import json
from datetime import datetime, timezone
from pathlib import Path


def perform_review_status(provider, model, config_file_value=None, now=None):
    if config_file_value is None:
        from capabilities import config_path
        config_file_value = config_path()
    target_path = Path(config_file_value).expanduser().resolve().parent / 'voice-model-review.json'
    outcome_payload = {'provider': provider, 'selected_model': model,
              'last_checked_at': None, 'needs_check': True, 'record': str(target_path)}
    try:
        record = json.loads(target_path.read_text()).get('providers', {}).get(provider, {})
        selection = record.get('selection', {})
        outcome_payload['selected_model'] = model or selection.get('model')
        outcome_payload['user_selection'] = selection
        checked_value = record.get('checked_at')
        stamp_value = datetime.fromisoformat(checked_value)
        if stamp_value.tzinfo is None:
            raise ValueError('检查时间需要时区')
        age_value = ((now or datetime.now(timezone.utc)) - stamp_value).total_seconds()
        outcome_payload.update(last_checked_at=checked_value, needs_check=not 0 <= age_value < 7 * 86400,
                      candidates=record.get('models', []), findings=record.get('findings', ''))
    except (OSError, ValueError, TypeError, AttributeError):
        outcome_payload['record_status'] = 'missing_or_invalid'
    return outcome_payload


if __name__ == '__main__':
    import argparse
    input_path = argparse.ArgumentParser(description=__doc__)
    input_path.add_argument('--provider', choices=['volcengine', 'qwen'], default='volcengine')
    input_path.add_argument('--model')
    input_path.add_argument('--config')
    alpha_channel = input_path.parse_args()
    from capabilities import effective
    model = alpha_channel.model
    if not model and alpha_channel.provider == 'volcengine':
        model = effective(alpha_channel.config)[0]['provider_options']['volcengine']['model']
    print(json.dumps(perform_review_status(alpha_channel.provider, model, alpha_channel.config), ensure_ascii=False, indent=2))
