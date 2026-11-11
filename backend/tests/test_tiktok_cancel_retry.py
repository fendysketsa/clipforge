import pytest
from automatic_retry import tiktok_retry_reason
from tiktok_dialogs import is_cancel_upload_confirmation


TEXT='Sure you want to cancel your upload? Any edits to your current upload will not be saved. No Yes'
ERROR=f'Dialog TikTok menghalangi form upload: {TEXT}. Video belum diposting.'


def test_observed_cancel_prompt_is_retryable_only_before_post():
    assert is_cancel_upload_confirmation(TEXT)
    assert tiktok_retry_reason(ERROR,[])=='upload_cancel_dialog_before_post'
    for kwargs in ({'started':True},{'accepted':True}):
        assert tiktok_retry_reason(ERROR,[],**kwargs)==''
    assert tiktok_retry_reason(ERROR,['POST_SUBMIT_INTENT: issued'])==''
    assert tiktok_retry_reason(ERROR,['POST_API_ACCEPTED: accepted'])==''
    assert tiktok_retry_reason(ERROR,['VIDEO_URL:https://example.test/posted'])==''


@pytest.mark.parametrize('text',['Sure you want to delete this post? No Yes',
    'Content may be restricted. No Yes',TEXT+' CAPTCHA',TEXT.replace('No Yes','Yes No'),
    TEXT.replace('cancel your upload','post your upload')])
def test_other_confirmations_are_not_automatic_retry_permission(text):
    assert not is_cancel_upload_confirmation(text)
    assert tiktok_retry_reason(f'Dialog TikTok menghalangi form upload: {text}. Video belum diposting.',[])==''
